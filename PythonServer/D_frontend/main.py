"""D 서비스 진입점 (BFF): 화면용 JSON API, 실제 호출은 A/B/C로 프록시"""

from __future__ import annotations

import hmac

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from shared.schemas import (
    CongestionTarget,
    LocationReq,
    PlanRequest,
    ReplanRequest,
    SavePlanRequest,
)

from . import config, view_logic
from .api_client import auth as auth_client
from .api_client import places as places_client
from .api_client import plans as plans_client
from .api_client.errors import UpstreamRejectedError, UpstreamUnavailableError

app = FastAPI(title="D - 프론트엔드 비즈니스 로직 서버 (BFF)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def _require_gateway_token(request: Request, call_next):
    """화면을 거친 요청만 통과 (BFF_GATEWAY_TOKEN이 비면 검사 안 함)"""

    if config.GATEWAY_TOKEN and request.url.path.startswith("/ui/"):
        supplied = request.headers.get(config.GATEWAY_HEADER, "")
        if not hmac.compare_digest(supplied, config.GATEWAY_TOKEN):
            return JSONResponse(
                status_code=403,
                content=view_logic.status_envelope(
                    "error",
                    data={"message": "허용되지 않은 요청입니다.", "retryable": False, "code": "FORBIDDEN"},
                ),
            )
    return await call_next(request)


def _session_token(request: Request) -> str | None:
    return request.cookies.get(config.SESSION_COOKIE_NAME)


def _handle(context_key: str, exc: Exception) -> dict:
    return view_logic.status_envelope("error", data=view_logic.error_context(context_key, exc))


# --- 인증 (A로 프록시) ---


class CredentialsBody(BaseModel):
    """필드 누락 시 500 대신 422가 되도록 모델로 수신"""

    username: str
    password: str


@app.post("/ui/auth/register")
async def register(body: CredentialsBody):
    try:
        user = await auth_client.register(body.username, body.password)
        return view_logic.status_envelope("success", data=user)
    except (UpstreamUnavailableError, UpstreamRejectedError) as exc:
        return _handle("register", exc)


@app.post("/ui/auth/login")
async def login(body: CredentialsBody, response: Response):
    try:
        user, token = await auth_client.login(body.username, body.password)
    except (UpstreamUnavailableError, UpstreamRejectedError) as exc:
        return _handle("auth", exc)

    if token:
        # max_age가 없으면 브라우저를 닫을 때 로그아웃됨
        response.set_cookie(
            key=config.SESSION_COOKIE_NAME,
            value=token,
            max_age=config.SESSION_COOKIE_MAX_AGE,
            httponly=True,
            secure=config.COOKIE_SECURE,
            samesite=config.COOKIE_SAMESITE,
            path="/",
        )
    return view_logic.status_envelope("success", data=user)


@app.post("/ui/auth/logout")
async def logout(request: Request, response: Response):
    # A 장애 시에도 브라우저 세션은 해제
    try:
        await auth_client.logout(_session_token(request))
    except (UpstreamUnavailableError, UpstreamRejectedError):
        pass
    response.delete_cookie(config.SESSION_COOKIE_NAME, path="/")
    return view_logic.status_envelope("success")


@app.get("/ui/auth/me")
async def me(request: Request):
    # 화면 진입 시 첫 API라 오류도 반드시 envelope로 반환
    try:
        user = await auth_client.me(_session_token(request))
    except (UpstreamUnavailableError, UpstreamRejectedError) as exc:
        return _handle("auth", exc)
    return view_logic.status_envelope("success", data=user)


# --- 주변 관광지 / 집중률 (B로 프록시, 좌표는 POST body로만) ---


@app.get("/ui/regions")
async def regions():
    """지역 선택지 (B에서 받아 그대로 전달)"""
    try:
        items = await places_client.regions()
    except (UpstreamUnavailableError, UpstreamRejectedError) as exc:
        return _handle("regions", exc)

    if not items:
        return view_logic.status_envelope("empty", empty_message="선택할 수 있는 지역이 없습니다.")
    return view_logic.status_envelope("success", data=items)


@app.post("/ui/places/nearby")
async def places_nearby(req: LocationReq):
    try:
        places = await places_client.nearby(req.map_x, req.map_y, req.radius)
    except (UpstreamUnavailableError, UpstreamRejectedError) as exc:
        return _handle("places_nearby", exc)

    if not places:
        return view_logic.status_envelope("empty", empty_message="주변에 표시할 관광지가 없습니다.")
    return view_logic.status_envelope("success", data=places)


class CongestionBody(BaseModel):
    """targets(이름 포함)를 주면 B가 상세 재조회 생략"""

    travel_date: str
    targets: list[CongestionTarget] = []
    area_cd: str = "50"
    l_dong_signgu_cd: str = "110"


@app.post("/ui/places/congestion")
async def places_congestion(body: CongestionBody):
    travel_date = body.travel_date

    try:
        raw = await places_client.congestion(
            body.targets, body.area_cd, body.l_dong_signgu_cd
        )
    except (UpstreamUnavailableError, UpstreamRejectedError) as exc:
        # 집중률 실패는 일정 생성을 막지 않음
        return _handle("congestion", exc)

    shaped = {}
    for content_id, congestion in raw.items():
        rate = next((d["rate"] for d in congestion["daily"] if d["date"] == travel_date), None)
        shaped[content_id] = {
            "has_data": congestion["has_data"],
            "rate": rate,
            "label": view_logic.congestion_label(rate, congestion["has_data"]),
            "is_high": view_logic.is_high_congestion(rate, congestion["has_data"]),
        }
    return view_logic.status_envelope("success", data=shaped)


# --- AI 일정 생성 / 재추천 (C로 프록시) ---


@app.post("/ui/plan/generate")
async def generate_plan(req: PlanRequest):
    try:
        plan = await plans_client.generate_plan(req.model_dump())
    except (UpstreamUnavailableError, UpstreamRejectedError) as exc:
        return _handle("plan_generate", exc)
    return view_logic.status_envelope("success", data=view_logic.plan_display_context(plan))


@app.post("/ui/plan/replan")
async def replan(req: ReplanRequest):
    try:
        result = await plans_client.replan(req.model_dump())
    except (UpstreamUnavailableError, UpstreamRejectedError) as exc:
        return _handle("plan_replan", exc)
    return view_logic.status_envelope("success", data=view_logic.replan_result_context(result))


# --- 저장 일정 (A로 프록시, 로그인 필요) ---


@app.post("/ui/plans")
async def save_plan(req: SavePlanRequest, request: Request):
    try:
        saved = await plans_client.save_plan(_session_token(request), req.model_dump())
    except (UpstreamUnavailableError, UpstreamRejectedError) as exc:
        return _handle("plan_save", exc)
    return view_logic.status_envelope("success", data=saved)


@app.get("/ui/plans")
async def list_plans(request: Request):
    try:
        plans = await plans_client.list_plans(_session_token(request))
    except (UpstreamUnavailableError, UpstreamRejectedError) as exc:
        return _handle("generic", exc)

    if not plans:
        return view_logic.status_envelope("empty", empty_message="저장된 일정이 없습니다.")
    return view_logic.status_envelope("success", data=plans)


@app.get("/ui/plans/{plan_id}")
async def get_plan_detail(plan_id: int, request: Request):
    try:
        detail = await plans_client.get_plan_detail(_session_token(request), plan_id)
    except (UpstreamUnavailableError, UpstreamRejectedError) as exc:
        return _handle("generic", exc)
    return view_logic.status_envelope("success", data=detail)


@app.delete("/ui/plans/{plan_id}")
async def delete_plan(plan_id: int, request: Request):
    try:
        await plans_client.delete_plan(_session_token(request), plan_id)
    except (UpstreamUnavailableError, UpstreamRejectedError) as exc:
        return _handle("generic", exc)
    return view_logic.status_envelope("success")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=config.HOST, port=config.PORT)
