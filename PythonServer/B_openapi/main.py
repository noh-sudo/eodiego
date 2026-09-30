"""B 서비스 진입점: A/C/D가 호출하는 내부 HTTP API (좌표는 POST body로만)"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from shared.schemas import (
    Congestion,
    CongestionTarget,
    ErrorResponse,
    LocationReq,
    Place,
    PlaceDetailsRequest,
    Region,
)

from . import client, config, metrics, region, service
from .exceptions import InvalidUpstreamPayloadError, UpstreamAPIError, UpstreamTimeoutError

def _wire_logging() -> None:
    """관광공사 호출 INFO 로그가 남도록 uvicorn 핸들러를 앱 로거에 연결"""

    app_logger = logging.getLogger("B_openapi")
    if app_logger.handlers:
        return
    uvicorn_logger = logging.getLogger("uvicorn.error")
    for handler in uvicorn_logger.handlers:
        app_logger.addHandler(handler)
    if not app_logger.handlers:
        app_logger.addHandler(logging.StreamHandler())
    app_logger.setLevel(logging.INFO)
    app_logger.propagate = False


@asynccontextmanager
async def _lifespan(app: FastAPI):
    _wire_logging()
    yield
    await client.close_client()  # 공유 HTTP 연결 정리


app = FastAPI(title="B - 한국관광공사 OpenAPI 연동 서비스", lifespan=_lifespan)


def _to_error_response(exc: Exception) -> ErrorResponse:
    if isinstance(exc, UpstreamTimeoutError):
        return ErrorResponse(error={"code": "UPSTREAM_TIMEOUT", "message": "관광공사 API 응답이 지연되고 있습니다."})
    if isinstance(exc, UpstreamAPIError):
        return ErrorResponse(error={"code": "UPSTREAM_ERROR", "message": "관광공사 API 호출에 실패했습니다."})
    if isinstance(exc, InvalidUpstreamPayloadError):
        return ErrorResponse(error={"code": "UPSTREAM_ERROR", "message": "관광공사 API 응답 형식이 올바르지 않습니다."})
    return ErrorResponse(error={"code": "INTERNAL_ERROR", "message": "내부 오류가 발생했습니다."})


@app.get("/internal/regions", response_model=list[Region])
async def regions():
    """지역 선택지와 대표 좌표"""
    return region.list_regions()


@app.post("/internal/places/nearby", response_model=list[Place])
async def places_nearby(req: LocationReq):
    """좌표는 요청 처리에만 쓰고 로그에 남기지 않음"""
    try:
        return await service.get_places(req)
    except (UpstreamTimeoutError, UpstreamAPIError, InvalidUpstreamPayloadError) as exc:
        raise HTTPException(status_code=502, detail=_to_error_response(exc).model_dump()) from exc


@app.post("/internal/places/details", response_model=list[Place])
async def place_details(req: PlaceDetailsRequest):
    """최종 일정 장소들의 상세정보 병렬 조회 (실패한 장소는 제외)"""
    return await service.get_place_details(req.content_ids)


class CongestionBatchRequest(BaseModel):
    """이름을 함께 주면 상세조회 생략"""

    targets: list[CongestionTarget] = []
    area_cd: str = "50"
    l_dong_signgu_cd: str = "110"


@app.post("/internal/congestion", response_model=dict[str, Congestion])
async def congestion_batch(req: CongestionBatchRequest):
    try:
        return await service.get_congestion_for_targets(
            req.targets, req.area_cd, req.l_dong_signgu_cd
        )
    except (UpstreamTimeoutError, UpstreamAPIError) as exc:
        raise HTTPException(status_code=502, detail=_to_error_response(exc).model_dump()) from exc


@app.get("/internal/metrics")
async def kto_metrics(days: int = 7):
    """오늘 관광공사 API 호출 수와 한도 소진율, 최근 이력"""
    return metrics.snapshot(days)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=config.HOST, port=config.PORT)
