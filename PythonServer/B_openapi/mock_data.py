"""실제 API 없이 개발·테스트용 mock (shared.schemas 계약 준수)"""

from __future__ import annotations

from shared.schemas import Congestion, DayRate, Place

_MOCK_PLACES: list[dict] = [
    dict(
        content_id="126508",
        name="보덕사",
        addr="제주특별자치도 제주시 산록북로",
        map_x=126.4995,
        map_y=33.4622,
        dist=320.5,
        image=None,
        content_type_id="12",
        category="사찰",
        use_time="09:00~18:00",
        rest_date=None,
        expected_stay_minutes=40,
    ),
    dict(
        content_id="126509",
        name="제주민속자연사박물관",
        addr="제주특별자치도 제주시 삼성로",
        map_x=126.5231,
        map_y=33.4881,
        dist=850.2,
        image=None,
        content_type_id="14",
        category="박물관",
        use_time="08:30~17:00",
        rest_date="1월 1일",
        expected_stay_minutes=60,
    ),
    dict(
        content_id="126510",
        name="성산일출봉",
        addr="제주특별자치도 서귀포시 성산읍",
        map_x=126.9424,
        map_y=33.4587,
        dist=15230.0,
        image=None,
        content_type_id="12",
        category="자연",
        use_time="07:00~20:00",
        rest_date=None,
        expected_stay_minutes=90,
    ),
    dict(
        content_id="126511",
        name="한라수목원",
        addr="제주특별자치도 제주시 수목원길",
        map_x=126.4813,
        map_y=33.4756,
        dist=1200.0,
        image=None,
        content_type_id="12",
        category="공원",
        use_time="상시개방",
        rest_date=None,
        expected_stay_minutes=50,
    ),
    dict(
        content_id="126512",
        name="용두암",
        addr="제주특별자치도 제주시 용담동",
        map_x=126.5122,
        map_y=33.5147,
        dist=2100.0,
        image=None,
        content_type_id="12",
        category="자연",
        use_time="상시개방",
        rest_date=None,
        expected_stay_minutes=20,
    ),
]

# content_id -> 집중률 데이터 (하나는 has_data=False)
_MOCK_CONGESTION: dict[str, dict] = {
    "126508": {"rate_by_date": {"20260826": 42.0, "20260827": 55.0, "20260828": 76.0}},
    "126509": {"rate_by_date": {"20260826": 20.0, "20260827": 18.0, "20260828": 25.0}},
    "126510": {"rate_by_date": {"20260826": 88.0, "20260827": 90.0, "20260828": 95.0}},
    "126511": {"rate_by_date": {}},  # has_data=False 케이스
    "126512": {"rate_by_date": {"20260826": 60.0, "20260827": 40.0, "20260828": 30.0}},
}


def mock_places(limit: int | None = None) -> list[Place]:
    places = [Place(**p) for p in _MOCK_PLACES]
    return places[:limit] if limit else places


def mock_place_detail(content_id: str) -> Place | None:
    for p in _MOCK_PLACES:
        if p["content_id"] == content_id:
            return Place(**p)
    return None


def mock_congestion(content_id: str) -> Congestion:
    entry = _MOCK_CONGESTION.get(content_id)
    name = next((p["name"] for p in _MOCK_PLACES if p["content_id"] == content_id), content_id)

    if not entry or not entry["rate_by_date"]:
        return Congestion(content_id=content_id, name=name, daily=[], has_data=False)

    daily = [DayRate(date=d, rate=r) for d, r in sorted(entry["rate_by_date"].items())]
    return Congestion(content_id=content_id, name=name, daily=daily, has_data=True)
