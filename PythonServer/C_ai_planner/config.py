"""C 설정"""

from __future__ import annotations

import os

# 선택 날짜 예측 집중률이 이 값 이상이면 재추천 대상
CONGESTION_THRESHOLD: float = float(os.environ.get("CONGESTION_THRESHOLD", "70.0"))

# 재추천 후보의 최대 추가 이동거리(m)
MAX_REPLAN_DISTANCE_DELTA_M: float = float(os.environ.get("MAX_REPLAN_DISTANCE_DELTA_M", "3000"))

# 기본 체류시간(분), expected_stay_minutes가 없을 때 사용
DEFAULT_STAY_MINUTES: int = int(os.environ.get("DEFAULT_STAY_MINUTES", "60"))

B_BASE_URL: str = os.environ.get("B_BASE_URL", "http://localhost:8001")
REQUEST_TIMEOUT_SECONDS: float = float(os.environ.get("B_TIMEOUT_SECONDS", "5"))

USE_LLM: bool = os.environ.get("USE_LLM", "false").strip().lower() in {"1", "true", "yes"}
LLM_API_KEY: str = os.environ.get("LLM_API_KEY", "")  # OpenAI API 키
LLM_TIMEOUT_SECONDS: float = float(os.environ.get("LLM_TIMEOUT_SECONDS", "8"))

# OpenAI 모델
LLM_MODEL: str = os.environ.get("LLM_MODEL", "gpt-5.4-mini")
# 짧은 문장 생성이라 추론 불필요 (추론 토큰은 출력 토큰으로 과금)
LLM_REASONING_EFFORT: str = os.environ.get("LLM_REASONING_EFFORT", "none")
# 추론 토큰 포함 출력 상한, 너무 낮으면 잘려서 기본 문구로 전환
LLM_MAX_OUTPUT_TOKENS: int = int(os.environ.get("LLM_MAX_OUTPUT_TOKENS", "1500"))

# 하루 요청 상한 (계정 한도 50 RPD보다 낮게), 0이면 제한 없음
LLM_DAILY_REQUEST_LIMIT: int = int(os.environ.get("LLM_DAILY_REQUEST_LIMIT", "45"))
# SDK 자동 재시도도 한도를 쓰므로 기본은 재시도 없음
LLM_MAX_RETRIES: int = int(os.environ.get("LLM_MAX_RETRIES", "0"))

# 근거 자료 소개문 길이 상한(자)
LLM_OVERVIEW_MAX_CHARS: int = int(os.environ.get("LLM_OVERVIEW_MAX_CHARS", "400"))

# LLM 요청 수/토큰 사용량은 MySQL(llm_request, llm_token_usage)에 기록

HOST: str = os.environ.get("C_HOST", "0.0.0.0")
PORT: int = int(os.environ.get("C_PORT", "8002"))
