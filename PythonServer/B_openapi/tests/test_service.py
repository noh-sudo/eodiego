"""mock 계약 일치와 정상/데이터없음 케이스 검증"""

import asyncio

from shared.schemas import CongestionTarget, LocationReq

from B_openapi import mock_data, region, service


def test_mock_places_matches_schema():
    places = mock_data.mock_places()
    assert len(places) > 0
    assert all(p.content_id and p.name for p in places)


def test_mock_congestion_has_data_true():
    c = mock_data.mock_congestion("126508")
    assert c.has_data is True
    assert len(c.daily) > 0


def test_mock_congestion_has_data_false_for_empty():
    c = mock_data.mock_congestion("126511")
    assert c.has_data is False
    assert c.daily == []


def test_get_places_uses_mock_by_default():
    req = LocationReq(map_x=126.5, map_y=33.45, radius=1000)
    places = asyncio.run(service.get_places(req))
    assert len(places) > 0


def test_get_congestion_for_targets_limits_candidates(monkeypatch):
    monkeypatch.setattr(service.config, "MAX_CANDIDATES_FOR_CONGESTION", 2)
    targets = [CongestionTarget(content_id=p.content_id, name=p.name) for p in mock_data.mock_places()]
    result = asyncio.run(service.get_congestion_for_targets(targets, "50", "110"))
    assert len(result) == 2


def test_list_regions_has_name_and_coords():
    regions = region.list_regions()
    assert len(regions) > 0
    assert all(r.code and r.name for r in regions)
    # 모든 지역에 대표 좌표 필수
    assert all(isinstance(r.map_x, float) and isinstance(r.map_y, float) for r in regions)


def test_list_regions_codes_are_unique():
    codes = [r.code for r in region.list_regions()]
    assert len(codes) == len(set(codes))


def test_regions_endpoint_returns_list():
    from fastapi.testclient import TestClient

    from B_openapi.main import app

    resp = TestClient(app).get("/internal/regions")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == len(region.list_regions())
    assert {"code", "name", "map_x", "map_y"} <= set(body[0])


# --- 호출 수 절감 / 카운터 ---

def test_targets_with_names_skip_detail_lookup(monkeypatch):
    """이름을 주면 상세조회를 부르지 않아야 함"""
    from shared.schemas import CongestionTarget

    detail_calls = []

    async def spy_detail(content_id):
        detail_calls.append(content_id)
        return mock_data.mock_place_detail(content_id)

    monkeypatch.setattr(service, "get_place_detail", spy_detail)
    targets = [CongestionTarget(content_id=p.content_id, name=p.name) for p in mock_data.mock_places()]
    result = asyncio.run(service.get_congestion_for_targets(targets, "50", "110"))

    assert detail_calls == []
    assert len(result) == len(targets)


def test_targets_without_names_resolve_via_detail(monkeypatch):
    from shared.schemas import CongestionTarget

    detail_calls = []

    async def spy_detail(content_id):
        detail_calls.append(content_id)
        return mock_data.mock_place_detail(content_id)

    monkeypatch.setattr(service, "get_place_detail", spy_detail)
    targets = [CongestionTarget(content_id="126508"), CongestionTarget(content_id="126509")]
    result = asyncio.run(service.get_congestion_for_targets(targets, "50", "110"))

    assert sorted(detail_calls) == ["126508", "126509"]
    assert len(result) == 2


def test_candidate_cap_applies_before_detail_lookup(monkeypatch):
    """후보 상한이 상세조회에도 적용되는지 확인"""
    from shared.schemas import CongestionTarget

    detail_calls = []

    async def spy_detail(content_id):
        detail_calls.append(content_id)
        return mock_data.mock_place_detail(content_id)

    monkeypatch.setattr(service, "get_place_detail", spy_detail)
    monkeypatch.setattr(service.config, "MAX_CANDIDATES_FOR_CONGESTION", 2)
    targets = [CongestionTarget(content_id=p.content_id) for p in mock_data.mock_places()]
    asyncio.run(service.get_congestion_for_targets(targets, "50", "110"))

    assert len(detail_calls) == 2


def test_metrics_counts_and_reports_quota(mysql_db, monkeypatch):
    """호출마다 1행 추가 후 COUNT로 계수"""
    from B_openapi import metrics

    monkeypatch.setattr(metrics.config, "KTO_DAILY_QUOTA", 100)
    assert metrics.record("locationBasedList2") == 1
    assert metrics.record("tatsCnctrRatedList") == 2
    assert metrics.record("tatsCnctrRatedList") == 3

    snap = metrics.snapshot()
    assert snap["total"] == 3
    assert snap["by_operation"] == {"locationBasedList2": 1, "tatsCnctrRatedList": 2}
    assert snap["remaining"] == 97


def test_metrics_endpoint(mysql_db):
    from fastapi.testclient import TestClient

    from B_openapi.main import app

    body = TestClient(app).get("/internal/metrics").json()
    assert body["total"] == 0  # 고유 날짜라 기록 없음
    assert "by_operation" in body


def test_metrics_survive_process_restart(mysql_db, isolated_metrics_day, monkeypatch):
    """재시작 후에도 카운터 유지"""
    import importlib

    from B_openapi import metrics

    metrics.record("locationBasedList2")
    metrics.record("tatsCnctrRatedList")

    # 모듈 상태 없이 같은 DB만 다시 읽는 상황
    reloaded = importlib.reload(metrics)
    monkeypatch.setattr(reloaded, "_today", lambda: isolated_metrics_day)
    assert reloaded.snapshot()["total"] == 2


def test_metrics_history_includes_today(mysql_db, isolated_metrics_day):
    from B_openapi import metrics

    metrics.record("locationBasedList2")
    snap = metrics.snapshot(days=10000)
    # 다른 테스트 기록과 섞이므로 날짜로 조회
    entry = next(e for e in snap["history"] if e["date"] == isolated_metrics_day.isoformat())
    assert entry["total"] == 1


def test_metrics_record_failure_does_not_break_api_calls(monkeypatch):
    """카운터 DB 장애 시에도 관광공사 호출 유지"""
    from B_openapi import metrics
    from shared import database

    def broken_transaction():
        raise database.DatabaseConfigError("no db")

    monkeypatch.setattr(metrics.database, "transaction", broken_transaction)
    assert metrics.record("locationBasedList2") == -1


def test_metrics_uses_korean_date():
    """서버 시간대와 무관하게 한국 날짜로 계수"""
    import importlib
    from datetime import datetime, timedelta, timezone

    from B_openapi import metrics

    fresh = importlib.reload(metrics)  # conftest의 날짜 고정을 풀고 실제 함수 확인
    assert fresh._today() == datetime.now(timezone(timedelta(hours=9))).date()


# --- 검색 반경 단일화 / 뽑힌 장소만 상세정보 ---


def test_location_req_default_radius_is_5km():
    """반경 기본값은 공통 계약에서 한 번만 정의"""
    assert LocationReq(map_x=126.5, map_y=33.45).radius == 5000


def test_get_places_passes_request_radius_through(monkeypatch):
    """요청 반경을 그대로 관광공사 API에 전달"""
    captured = {}

    async def fake_fetch(map_x, map_y, radius):
        captured["radius"] = radius
        return []

    monkeypatch.setattr(service.config, "USE_MOCK", False)
    monkeypatch.setattr(service, "fetch_location_based_list", fake_fetch)

    asyncio.run(service.get_places(LocationReq(map_x=126.5, map_y=33.45)))
    assert captured["radius"] == 5000

    asyncio.run(service.get_places(LocationReq(map_x=126.5, map_y=33.45, radius=3000)))
    assert captured["radius"] == 3000


def _real_mode_detail_fakes(monkeypatch, intro_payload=None, intro_error=None):
    calls = {"common": [], "intro": []}

    async def fake_common(content_id):
        calls["common"].append(content_id)
        return {
            "contentid": content_id, "contenttypeid": "12", "title": f"장소{content_id}(제주)",
            "addr1": "제주특별자치도 제주시", "mapx": "126.5", "mapy": "33.5",
            "overview": "도심 속 공원이다.<br>산책로가 있다. &amp; 쉼터",
        }

    async def fake_intro(content_id, content_type_id):
        calls["intro"].append((content_id, content_type_id))
        if intro_error:
            raise intro_error
        return intro_payload if intro_payload is not None else {
            "usetime": "상시 개방<br />", "restdate": "연중무휴",
        }

    monkeypatch.setattr(service.config, "USE_MOCK", False)
    monkeypatch.setattr(service, "fetch_place_detail", fake_common)
    monkeypatch.setattr(service, "fetch_place_intro", fake_intro)
    return calls


def test_place_detail_merges_intro_and_cleans_html(monkeypatch):
    calls = _real_mode_detail_fakes(monkeypatch)
    place = asyncio.run(service.get_place_detail("1"))

    assert place.use_time == "상시 개방"
    assert place.rest_date == "연중무휴"
    assert place.overview == "도심 속 공원이다. 산책로가 있다. & 쉼터"
    assert calls["intro"] == [("1", "12")]


def test_place_detail_finds_type_specific_intro_fields(monkeypatch):
    """유형별 필드 이름 대응 (예: 문화시설 usetimeculture)"""
    _real_mode_detail_fakes(
        monkeypatch, intro_payload={"usetimeculture": "09:00~18:00", "restdateculture": "매주 월요일"}
    )
    place = asyncio.run(service.get_place_detail("1"))
    assert place.use_time == "09:00~18:00"
    assert place.rest_date == "매주 월요일"


def test_place_detail_survives_intro_failure(monkeypatch):
    from B_openapi.exceptions import UpstreamAPIError

    _real_mode_detail_fakes(monkeypatch, intro_error=UpstreamAPIError("boom"))
    place = asyncio.run(service.get_place_detail("1"))
    assert place is not None
    assert place.overview
    assert place.use_time is None


def test_get_place_details_dedups_caps_and_keeps_order(monkeypatch):
    calls = _real_mode_detail_fakes(monkeypatch)
    monkeypatch.setattr(service.config, "MAX_DETAIL_BATCH", 3)

    places = asyncio.run(service.get_place_details(["3", "1", "3", "2", "9"]))

    assert [p.content_id for p in places] == ["3", "1", "2"]
    assert sorted(calls["common"]) == ["1", "2", "3"]


def test_get_place_details_skips_failed_places(monkeypatch):
    from B_openapi.exceptions import UpstreamTimeoutError

    _real_mode_detail_fakes(monkeypatch)
    original = service.fetch_place_detail

    async def flaky(content_id):
        if content_id == "2":
            raise UpstreamTimeoutError("timeout")
        return await original(content_id)

    monkeypatch.setattr(service, "fetch_place_detail", flaky)
    places = asyncio.run(service.get_place_details(["1", "2", "3"]))
    assert [p.content_id for p in places] == ["1", "3"]


def test_place_details_endpoint():
    from fastapi.testclient import TestClient

    from B_openapi.main import app

    resp = TestClient(app).post("/internal/places/details", json={"content_ids": ["126508", "없는ID"]})
    assert resp.status_code == 200
    assert [p["content_id"] for p in resp.json()] == ["126508"]
