"""B 호출 모듈 (좌표는 로그에 남기지 않음)"""

from __future__ import annotations

from .. import config
from . import _http


async def regions() -> list[dict]:
    resp = await _http.request("B", config.B_BASE_URL, "GET", "/internal/regions")
    return resp.json()


async def nearby(map_x: float, map_y: float, radius: int | None = None) -> list[dict]:
    """radius가 None이면 생략해 공통 계약 기본 반경 사용"""
    body: dict = {"map_x": map_x, "map_y": map_y}
    if radius is not None:
        body["radius"] = radius
    resp = await _http.request(
        "B", config.B_BASE_URL, "POST", "/internal/places/nearby", json=body,
    )
    return resp.json()


async def congestion(targets, area_cd: str = "50", l_dong_signgu_cd: str = "110") -> dict:
    """targets: CongestionTarget 목록, 이름이 있으면 B가 상세조회 생략"""

    resp = await _http.request(
        "B", config.B_BASE_URL, "POST", "/internal/congestion",
        json={
            "targets": [
                t if isinstance(t, dict) else {"content_id": t.content_id, "name": t.name}
                for t in targets
            ],
            "area_cd": area_cd,
            "l_dong_signgu_cd": l_dong_signgu_cd,
        },
    )
    return resp.json()
