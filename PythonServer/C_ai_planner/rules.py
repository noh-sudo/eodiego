"""규칙 기반 일정 생성 (LLM 없이 완결된 Plan 생성)"""

from __future__ import annotations

import math
from datetime import datetime, timedelta

from shared.schemas import Congestion, Place, PlanItem

from . import config


def rate_for_date(congestion: Congestion, travel_date: str) -> float | None:
    """daily에서 travel_date의 예측 집중률 조회, 없으면 None"""

    for day in congestion.daily:
        if day.date == travel_date:
            return day.rate
    return None


def congestion_level_label(rate: float | None) -> str:
    """note 기본 라벨 ("실시간 혼잡" 표현 금지)"""

    if rate is None:
        return "혼잡도 미제공"
    if rate >= config.CONGESTION_THRESHOLD:
        return "예측 집중률 높음"
    if rate >= config.CONGESTION_THRESHOLD * 0.5:
        return "예측 집중률 보통"
    return "예측 집중률 낮음"


class Candidate:
    """일정 선정용 내부 작업 단위 (규칙 계산 중간값 보관)"""

    __slots__ = ("place", "rate", "has_data", "score")

    def __init__(self, place: Place, rate: float | None, has_data: bool):
        self.place = place
        self.rate = rate
        self.has_data = has_data
        self.score = 0.0

    def __repr__(self) -> str:  # pragma: no cover - 디버그 편의용
        return f"Candidate({self.place.name}, rate={self.rate}, score={self.score:.2f})"


def attach_congestion(
    places: list[Place], congestion_map: dict[str, Congestion], travel_date: str
) -> list[Candidate]:
    """집중률이 없어도 후보에서 제외하지 않음"""

    candidates = []
    for place in places:
        congestion = congestion_map.get(place.content_id)
        if congestion is None or not congestion.has_data:
            candidates.append(Candidate(place, rate=None, has_data=False))
            continue
        rate = rate_for_date(congestion, travel_date)
        candidates.append(Candidate(place, rate=rate, has_data=rate is not None))
    return candidates


def score_candidates(candidates: list[Candidate]) -> list[Candidate]:
    """거리 60% + 집중률 40% 가중 점수로 정렬 (낮을수록 우선)"""

    if not candidates:
        return []

    max_dist = max((c.place.dist for c in candidates), default=1.0) or 1.0
    for c in candidates:
        dist_score = c.place.dist / max_dist
        if c.rate is None:
            c.score = dist_score
        else:
            rate_score = c.rate / 100.0
            c.score = dist_score * 0.6 + rate_score * 0.4
    return sorted(candidates, key=lambda c: c.score)


def select_diverse(candidates: list[Candidate], place_count: int) -> list[Candidate]:
    """유형 중복을 피하며 place_count개 선택"""

    selected: list[Candidate] = []
    seen_categories: set[str] = set()

    for c in candidates:
        if len(selected) >= place_count:
            break
        category = c.place.category
        if category and category in seen_categories and len(candidates) - len(selected) > (
            place_count - len(selected)
        ):
            # 후보가 충분할 때만 같은 카테고리 중복 회피
            continue
        selected.append(c)
        if category:
            seen_categories.add(category)

    if len(selected) < place_count:
        # 부족하면 남은 후보로 채움
        remaining = [c for c in candidates if c not in selected]
        selected.extend(remaining[: place_count - len(selected)])

    return selected[:place_count]


def haversine_m(p1: Place, p2: Place) -> float:
    r = 6371000.0
    lat1, lat2 = math.radians(p1.map_y), math.radians(p2.map_y)
    dlat = lat2 - lat1
    dlon = math.radians(p2.map_x - p1.map_x)
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))


def order_by_route(selected: list[Candidate]) -> list[Candidate]:
    """최근접 이웃 방식 동선 정렬"""

    if len(selected) <= 2:
        return selected

    remaining = list(selected)
    ordered = [remaining.pop(0)]
    while remaining:
        last = ordered[-1].place
        nxt = min(remaining, key=lambda c: haversine_m(last, c.place))
        ordered.append(nxt)
        remaining.remove(nxt)
    return ordered


def schedule_visits(
    ordered: list[Candidate], start_time: str, end_time: str
) -> list[PlanItem]:
    """시작~종료 시간 안에 체류시간을 누적해 방문 시간 배치"""

    fmt = "%H:%M"
    clock = datetime.strptime(start_time, fmt)
    end = datetime.strptime(end_time, fmt)

    items: list[PlanItem] = []
    for order, cand in enumerate(ordered, start=1):
        stay = cand.place.expected_stay_minutes or config.DEFAULT_STAY_MINUTES
        if clock >= end:
            break
        visit_time = clock.strftime(fmt)
        label = congestion_level_label(cand.rate)
        items.append(
            PlanItem(
                content_id=cand.place.content_id,
                name=cand.place.name,
                order=order,
                visit_time=visit_time,
                note=label,
                # note는 LLM 설명으로 덮일 수 있어 따로 보관
                congestion_label=label,
                high_congestion=cand.rate is not None and cand.rate >= config.CONGESTION_THRESHOLD,
            )
        )
        clock += timedelta(minutes=stay)

    return items


def build_candidates(
    places: list[Place],
    congestion_map: dict[str, Congestion],
    travel_date: str,
    place_count: int,
) -> list[Candidate]:
    """집중률 결합 -> 정렬 -> 다양성 선택 -> 동선 정렬"""

    attached = attach_congestion(places, congestion_map, travel_date)
    scored = score_candidates(attached)
    selected = select_diverse(scored, place_count)
    return order_by_route(selected)


def default_summary() -> str:
    """LLM 없이 쓰는 기본 문구"""

    return "선택한 날짜의 예측 집중률과 이동 거리를 고려해 구성한 일정입니다."
