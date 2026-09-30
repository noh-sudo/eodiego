"""C가 B의 내부 API를 호출하는 클라이언트"""

from __future__ import annotations

import httpx

from shared.schemas import Congestion, LocationReq, Place

from . import config


class BServiceError(Exception):
    pass


async def get_nearby_places(map_x: float, map_y: float, radius: int | None = None) -> list[Place]:
    """radius 미지정 시 공통 계약(LocationReq) 기본 반경 사용"""

    if radius is None:
        req = LocationReq(map_x=map_x, map_y=map_y)
    else:
        req = LocationReq(map_x=map_x, map_y=map_y, radius=radius)
    async with httpx.AsyncClient(base_url=config.B_BASE_URL, timeout=config.REQUEST_TIMEOUT_SECONDS) as client:
        try:
            resp = await client.post("/internal/places/nearby", json=req.model_dump())
        except httpx.HTTPError as exc:
            raise BServiceError(f"B 서비스 호출 실패: {exc}") from exc
    if resp.status_code >= 400:
        raise BServiceError(f"B 서비스 오류: {resp.status_code}")
    return [Place(**item) for item in resp.json()]


async def get_place_details(content_ids: list[str]) -> dict[str, Place]:
    """최종 일정 장소들의 상세정보 (content_id -> Place)"""

    if not content_ids:
        return {}
    async with httpx.AsyncClient(base_url=config.B_BASE_URL, timeout=config.REQUEST_TIMEOUT_SECONDS) as client:
        try:
            resp = await client.post("/internal/places/details", json={"content_ids": content_ids})
        except httpx.HTTPError as exc:
            raise BServiceError(f"B 서비스 호출 실패: {exc}") from exc
    if resp.status_code >= 400:
        raise BServiceError(f"B 서비스 오류: {resp.status_code}")
    return {p["content_id"]: Place(**p) for p in resp.json()}


async def get_congestion_map(
    places: list[Place], area_cd: str = "50", l_dong_signgu_cd: str = "110"
) -> dict[str, Congestion]:
    """이미 조회한 이름을 넘겨 B의 상세 재조회 생략"""

    if not places:
        return {}
    async with httpx.AsyncClient(base_url=config.B_BASE_URL, timeout=config.REQUEST_TIMEOUT_SECONDS) as client:
        try:
            resp = await client.post(
                "/internal/congestion",
                json={
                    "targets": [{"content_id": p.content_id, "name": p.name} for p in places],
                    "area_cd": area_cd,
                    "l_dong_signgu_cd": l_dong_signgu_cd,
                },
            )
        except httpx.HTTPError as exc:
            raise BServiceError(f"B 서비스 호출 실패: {exc}") from exc
    if resp.status_code >= 400:
        raise BServiceError(f"B 서비스 오류: {resp.status_code}")
    return {cid: Congestion(**data) for cid, data in resp.json().items()}
