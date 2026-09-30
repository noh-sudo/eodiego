"""A 인증 API 프록시 (세션 쿠키를 그대로 전달)"""

from __future__ import annotations

from .. import config
from . import _http


async def register(username: str, password: str) -> dict:
    resp = await _http.request(
        "A", config.A_BASE_URL, "POST", "/auth/register", json={"username": username, "password": password}
    )
    return resp.json()


async def login(username: str, password: str) -> tuple[dict, str | None]:
    """반환: (사용자 정보, A가 내려준 세션 토큰 또는 None)"""

    resp = await _http.request(
        "A", config.A_BASE_URL, "POST", "/auth/login", json={"username": username, "password": password}
    )
    token = resp.cookies.get(config.SESSION_COOKIE_NAME)
    return resp.json(), token


async def logout(session_token: str | None) -> None:
    cookies = {config.SESSION_COOKIE_NAME: session_token} if session_token else None
    await _http.request("A", config.A_BASE_URL, "POST", "/auth/logout", cookies=cookies)


async def me(session_token: str | None) -> dict | None:
    cookies = {config.SESSION_COOKIE_NAME: session_token} if session_token else None
    resp = await _http.request("A", config.A_BASE_URL, "GET", "/auth/me", cookies=cookies)
    return resp.json()
