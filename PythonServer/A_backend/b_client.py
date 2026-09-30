"""저장 일정 상세 조회 시 B의 실시간 관광정보를 부르는 클라이언트"""

from __future__ import annotations

import httpx

from shared.schemas import Place

from . import config


class BServiceError(Exception):
    pass


async def get_place_details(content_ids: list[str]) -> dict[str, Place]:
    """저장 일정 장소들을 B에서 한 번에 조회 (content_id -> Place)"""

    if not content_ids:
        return {}
    async with httpx.AsyncClient(base_url=config.B_BASE_URL, timeout=config.B_TIMEOUT_SECONDS) as client:
        try:
            resp = await client.post("/internal/places/details", json={"content_ids": content_ids})
        except httpx.HTTPError as exc:
            raise BServiceError(f"B 서비스 호출 실패: {exc}") from exc

    if resp.status_code >= 400:
        raise BServiceError(f"B 서비스 오류: {resp.status_code}")
    return {p["content_id"]: Place(**p) for p in resp.json()}
