"""A 설정 (시크릿은 전부 환경변수)"""

from __future__ import annotations

import os

# DB 접속 정보는 shared/database.py가 환경변수에서 직접 읽음

SESSION_COOKIE_NAME: str = "session_id"
SESSION_TTL_SECONDS: int = int(os.environ.get("SESSION_TTL_SECONDS", str(60 * 60 * 24 * 7)))  # 7일

# HTTPS 운영에서는 반드시 true
COOKIE_SECURE: bool = os.environ.get("COOKIE_SECURE", "false").strip().lower() in {"1", "true", "yes"}
COOKIE_SAMESITE: str = os.environ.get("COOKIE_SAMESITE", "lax")

B_BASE_URL: str = os.environ.get("B_BASE_URL", "http://localhost:8001")
B_TIMEOUT_SECONDS: float = float(os.environ.get("B_TIMEOUT_SECONDS", "5"))

# 쿠키 세션용 CORS: 정확한 origin 명시 필요 ("*" 금지)
ALLOWED_ORIGINS: list[str] = [
    o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "http://localhost:8003").split(",") if o.strip()
]

HOST: str = os.environ.get("A_HOST", "0.0.0.0")
PORT: int = int(os.environ.get("A_PORT", "8000"))
