"""D(BFF) 설정: 화면이 호출하는 JSON API 서버, 키는 직접 다루지 않음"""

from __future__ import annotations

import os

A_BASE_URL: str = os.environ.get("A_BASE_URL", "http://localhost:8000")
B_BASE_URL: str = os.environ.get("B_BASE_URL", "http://localhost:8001")
C_BASE_URL: str = os.environ.get("C_BASE_URL", "http://localhost:8002")

REQUEST_TIMEOUT_SECONDS: float = float(os.environ.get("UPSTREAM_TIMEOUT_SECONDS", "6"))

# A와 같은 세션 쿠키 이름 사용
SESSION_COOKIE_NAME: str = os.environ.get("SESSION_COOKIE_NAME", "session_id")

# 브라우저 쿠키 유지 기간 (A의 SESSION_TTL_SECONDS와 동일하게)
SESSION_COOKIE_MAX_AGE: int = int(os.environ.get("SESSION_TTL_SECONDS", str(60 * 60 * 24 * 7)))

# HTTPS 운영에서는 반드시 true
COOKIE_SECURE: bool = os.environ.get("COOKIE_SECURE", "false").strip().lower() in {"1", "true", "yes"}
COOKIE_SAMESITE: str = os.environ.get("COOKIE_SAMESITE", "lax")

# 화면(worker/dev 프록시)만 D를 부를 수 있게 하는 공유 시크릿, 비우면 검사 안 함
GATEWAY_TOKEN: str = os.environ.get("BFF_GATEWAY_TOKEN", "")
GATEWAY_HEADER: str = "x-bff-token"

# 화면 집중률 높음/보통/낮음 구분 기준
CONGESTION_DISPLAY_THRESHOLD: float = float(os.environ.get("CONGESTION_DISPLAY_THRESHOLD", "70.0"))

# 쿠키 인증과 함께 쓰므로 명시적 origin만 허용 ("*" 금지)
ALLOWED_ORIGINS: list[str] = [
    o.strip()
    for o in os.environ.get(
        "ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",")
    if o.strip() and o.strip() != "*"
]

HOST: str = os.environ.get("D_HOST", "0.0.0.0")
PORT: int = int(os.environ.get("D_PORT", "8003"))
