"""A/B/C/D 공통 API 계약 (변경 시 팀 공유 필수)"""

from __future__ import annotations

from pydantic import BaseModel


class Place(BaseModel):
    content_id: str
    name: str
    addr: str
    map_x: float
    map_y: float
    dist: float
    image: str | None = None

    # --- 선택 보완 필드 ---
    content_type_id: str | None = None
    category: str | None = None
    use_time: str | None = None  # 운영시간
    rest_date: str | None = None  # 휴무일
    expected_stay_minutes: int | None = None  # 예상 체류시간(분)
    overview: str | None = None  # 관광공사 소개문 (LLM 근거 자료로도 사용)


class PlaceDetailsRequest(BaseModel):
    """최종 일정 장소들의 상세정보 일괄 조회 요청"""

    content_ids: list[str]


class Region(BaseModel):
    """화면 지역 선택지 (대표 좌표 포함)"""

    code: str
    name: str
    map_x: float
    map_y: float


class DayRate(BaseModel):
    date: str  # "YYYYMMDD"
    rate: float  # 예측 집중률(%), 현재 혼잡도 아님


class CongestionTarget(BaseModel):
    """집중률 조회 대상, 이름을 넘기면 B의 상세조회 생략"""

    content_id: str
    name: str | None = None


class Congestion(BaseModel):
    content_id: str
    name: str
    daily: list[DayRate]
    has_data: bool  # False = 정상 응답이지만 데이터 없음 (API 실패와 구분)


class PlanItem(BaseModel):
    content_id: str
    name: str
    order: int
    visit_time: str  # "HH:MM"
    note: str | None = None  # 사용자용 설명 (LLM이 덮어쓸 수 있음)

    # 재추천 판단 근거 유지를 위해 집중률은 note와 분리
    congestion_label: str | None = None
    high_congestion: bool = False

    # 최종 일정 장소만 상세정보 첨부
    detail: Place | None = None


class Plan(BaseModel):
    title: str
    travel_date: str  # "YYYYMMDD"
    items: list[PlanItem]
    summary: str


class PlanRequest(BaseModel):
    map_x: float
    map_y: float
    travel_date: str
    start_time: str  # "HH:MM"
    end_time: str  # "HH:MM"
    place_count: int
    theme: str | None = None


class SavedPlan(BaseModel):
    plan_id: int
    title: str
    travel_date: str
    items: list[PlanItem]


class LocationReq(BaseModel):
    map_x: float
    map_y: float
    # 검색 반경(m), 호출측은 보내지 않고 이 기본값 공유
    radius: int = 5000


class SavePlanRequest(BaseModel):
    title: str
    travel_date: str
    items: list[PlanItem]


class ReplanRequest(BaseModel):
    plan: Plan
    target_content_id: str
    reason: str


class ReplanResponse(BaseModel):
    plan: Plan
    replaced_content_id: str
    replacement_reason: str


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail


# 공통 에러 코드
class ErrorCode:
    NOT_FOUND = "NOT_FOUND"
    UPSTREAM_TIMEOUT = "UPSTREAM_TIMEOUT"
    UPSTREAM_ERROR = "UPSTREAM_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    AUTH_REQUIRED = "AUTH_REQUIRED"
    SESSION_EXPIRED = "SESSION_EXPIRED"
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"
    DUPLICATE_USER = "DUPLICATE_USER"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    NO_REPLACEMENT_CANDIDATE = "NO_REPLACEMENT_CANDIDATE"
