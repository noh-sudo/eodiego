"""부분 재추천: 혼잡한 관광지 한 곳만 교체"""

from __future__ import annotations

from shared.schemas import Congestion, Place, Plan, PlanItem

from . import config
from .rules import Candidate, haversine_m, attach_congestion, congestion_level_label, score_candidates


class NoReplacementCandidateError(Exception):
    """대체 후보 없음"""


def find_replacement(
    plan: Plan,
    target_place: Place,
    candidate_places: list[Place],
    congestion_map: dict[str, Congestion],
    travel_date: str,
) -> Candidate:
    """재추천 후보 선정 (중복 제외, 집중률 기준 이하, 거리 제한, 데이터 없으면 폴백)"""

    existing_ids = {item.content_id for item in plan.items}

    pool = [p for p in candidate_places if p.content_id not in existing_ids]
    pool = [p for p in pool if haversine_m(target_place, p) <= config.MAX_REPLAN_DISTANCE_DELTA_M]

    attached = attach_congestion(pool, congestion_map, travel_date)

    under_threshold = [c for c in attached if c.rate is not None and c.rate < config.CONGESTION_THRESHOLD]
    if under_threshold:
        return score_candidates(under_threshold)[0]

    no_data_fallback = [c for c in attached if not c.has_data]
    if no_data_fallback:
        return score_candidates(no_data_fallback)[0]

    raise NoReplacementCandidateError(f"target_content_id={target_place.content_id} 대체 후보 없음")


def replan_reason_text(old_name: str, new_name: str, old_congestion_label: str | None) -> str:
    """재추천 사유 문구 (LLM 미사용, 교체 대상의 실제 집중률 라벨 기준)"""

    if old_congestion_label == "예측 집중률 높음":
        return f"{old_name}의 예측 집중률이 높아 {new_name}(으)로 대체했습니다."
    return f"{old_name} 대신 {new_name}을(를) 추천합니다."


def apply_replacement(plan: Plan, target_content_id: str, replacement: Candidate, reason_text: str) -> Plan:
    """대상 항목만 교체하고 나머지 순서/시간 유지"""

    new_items: list[PlanItem] = []
    for item in plan.items:
        if item.content_id != target_content_id:
            new_items.append(item)
            continue
        label = congestion_level_label(replacement.rate)
        new_items.append(
            PlanItem(
                content_id=replacement.place.content_id,
                name=replacement.place.name,
                order=item.order,
                visit_time=item.visit_time,
                note=label,
                # 화면 판단용으로 새 항목도 집중률을 note와 별도로 보관
                congestion_label=label,
                high_congestion=replacement.rate is not None
                and replacement.rate >= config.CONGESTION_THRESHOLD,
            )
        )

    return Plan(
        title=plan.title,
        travel_date=plan.travel_date,
        items=new_items,
        summary=plan.summary + f" ({reason_text})",
    )
