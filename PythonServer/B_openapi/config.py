"""B 설정 (서비스키/URL은 환경변수, USE_MOCK=true면 mock 데이터)"""

from __future__ import annotations

import os
from urllib.parse import unquote


def _service_key(raw: str) -> str:
    """Encoding/Decoding 키 어느 쪽이든 쓸 수 있도록 한 번 디코딩"""

    return unquote(raw) if "%" in raw else raw


def _bool_env(name: str, default: bool) -> bool:
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


USE_MOCK: bool = _bool_env("USE_MOCK", True)

KTO_SERVICE_KEY: str = _service_key(os.environ.get("KTO_SERVICE_KEY", ""))
# 국문 관광정보 서비스
KTO_BASE_URL: str = os.environ.get(
    "KTO_BASE_URL", "https://apis.data.go.kr/B551011/KorService2"
)
# 관광지 예측 집중률 서비스
KTO_CONGESTION_BASE_URL: str = os.environ.get(
    "KTO_CONGESTION_BASE_URL", "https://apis.data.go.kr/B551011/TatsCnctrRateService"
)

# 위치기반 검색 콘텐츠 유형 (12=관광지, 비우면 집중률 매칭률 급감)
KTO_CONTENT_TYPE_ID: str = os.environ.get("KTO_CONTENT_TYPE_ID", "12").strip()

# 상세정보 일괄 조회 상한 (관광지 1곳당 API 2회)
MAX_DETAIL_BATCH: int = int(os.environ.get("MAX_DETAIL_BATCH", "10"))

# 위치기반 검색 1회 조회 건수 (미지정 시 API 기본값 10건)
KTO_NUM_OF_ROWS: int = int(os.environ.get("KTO_NUM_OF_ROWS", "20"))

# 일일 호출 한도, 0이면 추적 안 함
KTO_DAILY_QUOTA: int = int(os.environ.get("KTO_DAILY_QUOTA", "1000"))

# 호출 횟수는 MySQL(kto_api_call)에 기록

REQUEST_TIMEOUT_SECONDS: float = float(os.environ.get("KTO_TIMEOUT_SECONDS", "5"))
MAX_RETRY: int = int(os.environ.get("KTO_MAX_RETRY", "1"))

# 관광공사 API 동시 연결 수
MAX_CONCURRENT_UPSTREAM: int = int(os.environ.get("KTO_MAX_CONCURRENCY", "10"))

# 집중률 API 1회 조회 행(날짜) 수
CONGESTION_NUM_OF_ROWS: int = int(os.environ.get("CONGESTION_NUM_OF_ROWS", "30"))

# 상세/집중률 조회로 넘길 후보 수 상한
MAX_CANDIDATES_FOR_CONGESTION: int = int(os.environ.get("MAX_CANDIDATES", "20"))

HOST: str = os.environ.get("B_HOST", "0.0.0.0")
PORT: int = int(os.environ.get("B_PORT", "8001"))
