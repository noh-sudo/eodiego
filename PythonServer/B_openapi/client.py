"""한국관광공사 OpenAPI 호출 (timeout, 제한된 재시도, 오류/데이터없음 구분)"""

from __future__ import annotations

import httpx

from . import config, metrics
from .exceptions import InvalidUpstreamPayloadError, UpstreamAPIError, UpstreamTimeoutError


_shared_client: httpx.AsyncClient | None = None


def _client() -> httpx.AsyncClient:
    """TLS 핸드셰이크 재사용을 위한 공유 클라이언트 (동시 연결 수 제한)"""

    global _shared_client
    if _shared_client is None or _shared_client.is_closed:
        _shared_client = httpx.AsyncClient(
            timeout=config.REQUEST_TIMEOUT_SECONDS,
            limits=httpx.Limits(
                max_connections=config.MAX_CONCURRENT_UPSTREAM,
                max_keepalive_connections=config.MAX_CONCURRENT_UPSTREAM,
            ),
        )
    return _shared_client


async def close_client() -> None:
    """서버 종료 시 연결 정리"""

    global _shared_client
    if _shared_client is not None and not _shared_client.is_closed:
        await _shared_client.aclose()
    _shared_client = None


def _check_result_header(payload: dict) -> None:
    """HTTP 200이어도 resultCode가 0000이 아니면 API 오류 (header/최상위 두 위치 확인)"""

    header = payload.get("response", {})
    header = header.get("header", {}) if isinstance(header, dict) else {}

    for source in (header, payload):
        if not isinstance(source, dict):
            continue
        result_code = source.get("resultCode")
        if result_code is not None and result_code != "0000":
            result_msg = source.get("resultMsg", "알 수 없는 오류")
            raise UpstreamAPIError(f"관광공사 API 오류 [{result_code}] {result_msg}")


def _extract_items(payload: dict) -> list[dict]:
    """items를 항상 list로 변환 (0건이면 빈 문자열, 1건이면 dict로 옴)"""

    body = payload.get("response", {})
    body = body.get("body", {}) if isinstance(body, dict) else {}
    items = body.get("items") if isinstance(body, dict) else None
    if not isinstance(items, dict):  # "" 또는 None = 결과 없음
        return []

    item = items.get("item", [])
    if isinstance(item, list):
        return item
    return [item] if item else []


async def _get_with_retry(client: httpx.AsyncClient, url: str, params: dict) -> dict:
    last_exc: Exception | None = None
    operation = url.rstrip("/").rsplit("/", 1)[-1]  # URL 전체는 로그에 남기지 않음
    for attempt in range(config.MAX_RETRY + 1):
        # 실패한 시도도 일일 한도를 쓰므로 요청 직전에 계수
        metrics.record(operation)
        try:
            resp = await client.get(url, params=params, timeout=config.REQUEST_TIMEOUT_SECONDS)
        except httpx.TimeoutException as exc:
            last_exc = exc
            continue
        except httpx.HTTPError as exc:
            raise UpstreamAPIError(f"요청 실패: {exc}") from exc

        if resp.status_code >= 500:
            # 서버 오류만 재시도 (4xx는 재시도해도 동일)
            last_exc = UpstreamAPIError(
                f"관광공사 API {resp.status_code}", status_code=resp.status_code
            )
            continue

        if resp.status_code >= 400:
            raise UpstreamAPIError(
                f"관광공사 API {resp.status_code}", status_code=resp.status_code
            )

        try:
            payload = resp.json()
        except ValueError as exc:
            raise InvalidUpstreamPayloadError("잘못된 JSON 응답") from exc

        _check_result_header(payload)
        return payload

    if isinstance(last_exc, httpx.TimeoutException):
        raise UpstreamTimeoutError("관광공사 API timeout") from last_exc
    if last_exc:
        raise last_exc
    raise UpstreamAPIError("알 수 없는 오류")


async def fetch_location_based_list(map_x: float, map_y: float, radius: int) -> list[dict]:
    """위치기반 관광지 검색 (정규화는 service.py)"""

    params = {
        "serviceKey": config.KTO_SERVICE_KEY,
        "mapX": map_x,
        "mapY": map_y,
        "radius": radius,
        "numOfRows": config.KTO_NUM_OF_ROWS,
        "pageNo": 1,
        "MobileOS": "ETC",
        "MobileApp": "TourPlanner",
        "_type": "json",
    }
    # 유형을 좁히지 않으면 음식점/숙박 위주라 집중률 매칭이 안 됨
    if config.KTO_CONTENT_TYPE_ID:
        params["contentTypeId"] = config.KTO_CONTENT_TYPE_ID
    payload = await _get_with_retry(_client(), f"{config.KTO_BASE_URL}/locationBasedList2", params)
    return _extract_items(payload)


async def fetch_congestion_candidates(t_ats_nm: str, area_cd: str, signgu_cd: str) -> list[dict]:
    """예측 집중률 조회, 날짜별 행 목록 원본 그대로 반환"""

    params = {
        "serviceKey": config.KTO_SERVICE_KEY,
        "pageNo": 1,
        "numOfRows": config.CONGESTION_NUM_OF_ROWS,
        "MobileOS": "ETC",
        "MobileApp": "TourPlanner",
        "tAtsNm": t_ats_nm,
        "areaCd": area_cd,
        "signguCd": signgu_cd,
        "_type": "json",
    }
    payload = await _get_with_retry(
        _client(), f"{config.KTO_CONGESTION_BASE_URL}/tatsCnctrRatedList", params
    )
    return _extract_items(payload)


async def fetch_place_detail(content_id: str) -> dict:
    """content_id 기반 공통정보 조회"""

    params = {
        "serviceKey": config.KTO_SERVICE_KEY,
        "contentId": content_id,
        "MobileOS": "ETC",
        "MobileApp": "TourPlanner",
        "_type": "json",
    }
    payload = await _get_with_retry(_client(), f"{config.KTO_BASE_URL}/detailCommon2", params)
    items = _extract_items(payload)
    if not items:
        raise InvalidUpstreamPayloadError(f"content_id={content_id} 상세정보 없음")
    return items[0]


async def fetch_place_intro(content_id: str, content_type_id: str) -> dict:
    """소개정보(운영시간/휴무일) 조회, 관광지마다 개별 호출"""

    params = {
        "serviceKey": config.KTO_SERVICE_KEY,
        "contentId": content_id,
        "contentTypeId": content_type_id,
        "MobileOS": "ETC",
        "MobileApp": "TourPlanner",
        "_type": "json",
    }
    payload = await _get_with_retry(_client(), f"{config.KTO_BASE_URL}/detailIntro2", params)
    items = _extract_items(payload)
    return items[0] if items else {}
