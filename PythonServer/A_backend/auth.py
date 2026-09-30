"""서버 세션 + HttpOnly 쿠키 인증"""

from __future__ import annotations

import hashlib
import secrets
import time

from fastapi import Request, Response

from . import config, db
from .errors import AuthRequiredError, SessionExpiredError

# 세션은 재시작해도 유지되도록 DB에 저장, 로그아웃은 폐기 기록 추가 방식


def _token_hash(token: str) -> str:
    """토큰 원문 대신 SHA-256 해시 저장 (128비트 랜덤이라 느린 KDF 불필요)"""

    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_session(user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    db.create_session(_token_hash(token), user_id, time.time() + config.SESSION_TTL_SECONDS)
    return token


def _lookup(token: str) -> int | None:
    return db.get_session_user(_token_hash(token), time.time())


def delete_session(token: str) -> None:
    """로그아웃 처리"""

    db.revoke_session(_token_hash(token))


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=config.SESSION_COOKIE_NAME,
        value=token,
        max_age=config.SESSION_TTL_SECONDS,
        httponly=True,
        secure=config.COOKIE_SECURE,
        samesite=config.COOKIE_SAMESITE,
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(key=config.SESSION_COOKIE_NAME, path="/")


def get_current_user_optional(request: Request) -> int | None:
    """비회원 허용 API용, 미로그인 시 None"""

    token = request.cookies.get(config.SESSION_COOKIE_NAME)
    if not token:
        return None
    return _lookup(token)


def get_current_user_required(request: Request) -> int:
    """로그인 필수 API용"""

    token = request.cookies.get(config.SESSION_COOKIE_NAME)
    if not token:
        raise AuthRequiredError("로그인이 필요합니다.")
    user_id = _lookup(token)
    if user_id is None:
        raise SessionExpiredError("세션이 만료되었습니다. 다시 로그인해주세요.")
    return user_id
