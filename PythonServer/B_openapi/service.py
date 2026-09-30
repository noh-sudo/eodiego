"""B service 계층 (USE_MOCK으로 mock/실제 API 전환, 반환 타입은 동일)"""

from __future__ import annotations

import asyncio
import html
import re

from shared.schemas import Congestion, CongestionTarget, DayRate, LocationReq, Place

from . import config, mock_data
from .client import (
    fetch_congestion_candidates,
    fetch_location_based_list,
    fetch_place_detail,
    fetch_place_intro,
)
from .exceptions import InvalidUpstreamPayloadError, UpstreamAPIError, UpstreamTimeoutError
from .matching import build_signgu_cd, extract_base_name, match_congestion_candidate

_TAG_RE = re.compile(r"<[^>]+>")


def _normalize_place(raw: dict) -> Place | None:
    try:
        return Place(
            content_id=str(raw["contentid"]),
            name=extract_base_name(raw["title"]),
            addr=raw.get("addr1", ""),
            map_x=float(raw["mapx"]),
            map_y=float(raw["mapy"]),
            dist=float(raw.get("dist", 0.0)),
            image=raw.get("firstimage") or None,
            content_type_id=raw.get("contenttypeid"),
        )
    except (KeyError, TypeError, ValueError):
        return None


async def get_places(req: LocationReq) -> list[Place]:
    """위치기반 주변 관광지 조회 (좌표는 로그에 남기지 않음)"""

    if config.USE_MOCK:
        return mock_data.mock_places()

    raw_items = await fetch_location_based_list(req.map_x, req.map_y, req.radius)
    places = [p for p in (_normalize_place(r) for r in raw_items) if p is not None]
    return places


async def get_place_detail(content_id: str) -> Place | None:
    """공통정보/소개정보 실시간 재조회"""

    if config.USE_MOCK:
        return mock_data.mock_place_detail(content_id)

    try:
        raw = await fetch_place_detail(content_id)
    except InvalidUpstreamPayloadError:
        return None

    content_type_id = raw.get("contenttypeid")
    intro: dict = {}
    if content_type_id:
        # 소개정보가 실패해도 공통정보만으로 반환
        try:
            intro = await fetch_place_intro(content_id, str(content_type_id))
        except (UpstreamTimeoutError, UpstreamAPIError, InvalidUpstreamPayloadError):
            intro = {}

    return Place(
        content_id=str(raw.get("contentid", content_id)),
        name=extract_base_name(raw.get("title", "")),
        addr=raw.get("addr1", ""),
        map_x=float(raw.get("mapx", 0.0) or 0.0),
        map_y=float(raw.get("mapy", 0.0) or 0.0),
        dist=0.0,
        image=raw.get("firstimage") or None,
        content_type_id=content_type_id,
        overview=_clean_text(raw.get("overview")),
        use_time=_intro_field(intro, ("usetime", "opentime", "playtime")),
        rest_date=_intro_field(intro, ("restdate",)),
    )


def _clean_text(value) -> str | None:
    """<br> 등 태그와 HTML 엔티티 정리"""

    if not value:
        return None
    text = html.unescape(_TAG_RE.sub(" ", str(value)))
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def _intro_field(intro: dict, prefixes: tuple[str, ...]) -> str | None:
    """소개정보 필드를 접두사로 탐색 (유형마다 이름이 다름)"""

    for key, value in intro.items():
        if key.lower().startswith(prefixes):
            cleaned = _clean_text(value)
            if cleaned:
                return cleaned
    return None


async def get_place_details(content_ids: list[str]) -> list[Place]:
    """최종 일정 장소들의 상세정보 병렬 조회 (상한 적용, 요청 순서 유지)"""

    unique_ids = list(dict.fromkeys(content_ids))[: config.MAX_DETAIL_BATCH]
    results = await asyncio.gather(
        *[get_place_detail(cid) for cid in unique_ids], return_exceptions=True
    )
    return [r for r in results if isinstance(r, Place)]


async def get_congestion_by_name(
    content_id: str, name: str, area_cd: str, l_dong_signgu_cd: str
) -> Congestion:
    """이름으로 집중률 조회 후 날짜별 행을 묶어 매칭 규칙 적용"""

    if config.USE_MOCK:
        return mock_data.mock_congestion(content_id)

    signgu_cd = build_signgu_cd(area_cd, l_dong_signgu_cd)
    raw_rows = await fetch_congestion_candidates(name, area_cd, signgu_cd)

    grouped: dict[str, list[dict]] = {}
    for row in raw_rows:
        name = extract_base_name(row.get("tAtsNm", ""))
        grouped.setdefault(name, []).append(row)
    candidates = [{"name": name, "daily": rows} for name, rows in grouped.items()]

    matched = match_congestion_candidate(candidates, name)
    if matched is None:
        return Congestion(content_id=content_id, name=name, daily=[], has_data=False)

    daily = [
        DayRate(date=row["baseYmd"], rate=float(row["cnctrRate"])) for row in matched["daily"]
    ]
    return Congestion(
        content_id=content_id,
        name=name,
        daily=daily,
        has_data=bool(daily),
    )


async def resolve_target_names(targets: list[CongestionTarget]) -> list[tuple[str, str]]:
    """이름 없는 대상만 상세조회로 채우고 실패한 대상은 제외"""

    unknown = [t for t in targets if not t.name]
    resolved: dict[str, str] = {}
    if unknown:
        details = await asyncio.gather(
            *[get_place_detail(t.content_id) for t in unknown], return_exceptions=True
        )
        for target, detail in zip(unknown, details):
            if isinstance(detail, Place):
                resolved[target.content_id] = detail.name

    pairs = []
    for t in targets:
        name = t.name or resolved.get(t.content_id)
        if name:
            pairs.append((t.content_id, name))
    return pairs


async def get_congestion_for_targets(
    targets: list[CongestionTarget], area_cd: str, l_dong_signgu_cd: str
) -> dict[str, Congestion]:
    """집중률 배치 조회 (후보 수 제한은 상세조회 전에 적용)"""

    limited = targets[: config.MAX_CANDIDATES_FOR_CONGESTION]
    pairs = await resolve_target_names(limited)
    results = await asyncio.gather(
        *[get_congestion_by_name(cid, name, area_cd, l_dong_signgu_cd) for cid, name in pairs]
    )
    return {c.content_id: c for c in results}
