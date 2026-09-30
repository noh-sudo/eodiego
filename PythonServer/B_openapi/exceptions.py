"""B 내부 공통 예외 (has_data=False는 예외가 아닌 정상 값)"""

from __future__ import annotations


class UpstreamTimeoutError(Exception):
    """관광공사 API timeout"""


class UpstreamAPIError(Exception):
    """관광공사 API HTTP 오류/비정상 응답"""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class InvalidUpstreamPayloadError(Exception):
    """JSON 파싱 실패/필수 필드 누락"""
