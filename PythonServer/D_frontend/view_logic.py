"""API 응답을 화면 표시용으로 가공하는 순수 로직"""

from __future__ import annotations

from . import config
from .api_client.errors import UpstreamRejectedError, UpstreamUnavailableError

# --- 집중률 UI ("실시간 혼잡도" 표현 금지) ---


def congestion_label(rate: float | None, has_data: bool) -> str:
    if not has_data or rate is None:
        return "혼잡도 예측 정보 없음"
    if rate >= config.CONGESTION_DISPLAY_THRESHOLD:
        return "예측 집중률 높음"
    if rate >= config.CONGESTION_DISPLAY_THRESHOLD * 0.5:
        return "예측 집중률 보통"
    return "예측 집중률 낮음"


def is_high_congestion(rate: float | None, has_data: bool) -> bool:
    return has_data and rate is not None and rate >= config.CONGESTION_DISPLAY_THRESHOLD


# --- 일정 화면 카드 가공 ---


def plan_display_context(plan: dict) -> dict:
    """Plan -> 화면 반복 렌더링용 dict (title/summary/travel_date/items)"""

    items = sorted(plan.get("items", []), key=lambda i: i["order"])
    result_items = []
    for i in items:
        note = i.get("note") or "혼잡도 예측 정보 없음"
        # 집중률은 C가 따로 내려준 값 우선, note 비교는 폴백
        label = i.get("congestion_label") or (note if note.startswith("예측 집중률") else None)
        high = bool(i.get("high_congestion")) or note == "예측 집중률 높음"
        entry = {
            "content_id": i["content_id"],
            "order": i["order"],
            "visit_time": i["visit_time"],
            "name": i["name"],
            "note": note,
            "congestion_label": label or "혼잡도 예측 정보 없음",
            "high_congestion": high,
            # 최종 일정 장소의 상세정보, 없으면 None
            "detail": i.get("detail"),
        }
        if high:
            entry["replan_prompt"] = replan_prompt(i["name"])
        result_items.append(entry)

    return {
        "title": plan.get("title", ""),
        "summary": plan.get("summary", ""),
        "travel_date": plan.get("travel_date", ""),
        "items": result_items,
    }


# --- 재추천 UX: 바뀐 항목 표시 ---


def replan_prompt(item_name: str) -> dict:
    return {
        "message": "예측 집중률이 높습니다.\n다른 관광지를 추천받으시겠습니까?",
        "target_name": item_name,
    }


def replan_result_context(replan_response: dict) -> dict:
    return {
        "plan": plan_display_context(replan_response["plan"]),
        "changed_content_id": replan_response["replaced_content_id"],
        "change_reason": replan_response["replacement_reason"],
    }


# --- API 오류 UI ---


# 상류(A/B/C) 에러 코드별 문구 (화면 맥락보다 우선)
_CODE_MESSAGES: dict[str, str] = {
    "SESSION_EXPIRED": "세션이 만료되었습니다.\n다시 로그인해주세요.",
    "AUTH_REQUIRED": "로그인이 필요합니다.",
    "INVALID_CREDENTIALS": "아이디 또는 비밀번호가 올바르지 않습니다.",
    "DUPLICATE_USER": "이미 사용 중인 아이디입니다.",
    "VALIDATION_ERROR": "입력값을 다시 확인해주세요.",
    "NOT_FOUND": "요청하신 항목을 찾을 수 없습니다.",
}

_FRIENDLY_MESSAGES: dict[str, str] = {
    "regions": "여행 지역 목록을 불러오지 못했습니다.\n잠시 후 다시 시도해주세요.",
    "register": "회원가입에 실패했습니다.\n입력값을 확인해주세요.",
    "places_nearby": "관광지 정보를 불러오지 못했습니다.\n잠시 후 다시 시도해주세요.",
    "congestion": "집중률 정보를 가져오지 못했습니다.\n관광지 정보만으로 추천을 계속합니다.",
    "plan_generate": "일정 생성에 실패했습니다.\n다시 시도해주세요.",
    "plan_replan": "재추천에 실패했습니다.\n잠시 후 다시 시도해주세요.",
    "auth": "로그인에 실패했습니다.\n아이디와 비밀번호를 확인해주세요.",
    "session_expired": "세션이 만료되었습니다.\n다시 로그인해주세요.",
    "plan_save": "일정 저장에 실패했습니다.\n다시 시도해주세요.",
    "generic": "요청을 처리하지 못했습니다.\n잠시 후 다시 시도해주세요.",
}


def error_context(context_key: str, exc: Exception) -> dict:
    """실제 API 실패를 {message, retryable} 형태로 변환 (데이터 없음은 제외)"""

    code = exc.code if isinstance(exc, UpstreamRejectedError) else None
    message = _CODE_MESSAGES.get(code) if code else None
    if message is None:
        message = _FRIENDLY_MESSAGES.get(context_key, _FRIENDLY_MESSAGES["generic"])

    retryable = isinstance(exc, UpstreamUnavailableError) or (
        isinstance(exc, UpstreamRejectedError) and exc.status_code >= 500
    )

    # 화면이 로그인 창을 띄울 수 있도록 code 포함
    return {"message": message, "retryable": retryable, "code": code}


# --- 로딩/빈 상태 envelope ---


def status_envelope(status: str, data=None, empty_message: str | None = None) -> dict:
    """status: success | empty | error (loading은 화면이 자체 표시)"""

    envelope = {"status": status}
    if status in ("success", "error"):
        envelope["data"] = data
    elif status == "empty":
        envelope["message"] = empty_message or "표시할 항목이 없습니다."
    return envelope
