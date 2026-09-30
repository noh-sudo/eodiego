"""api_client 공통 예외 (main.py에서 사용자 메시지로 변환)"""

from __future__ import annotations


class UpstreamUnavailableError(Exception):
    """A/B/C timeout 또는 연결 실패"""

    def __init__(self, service: str, message: str = ""):
        super().__init__(message or f"{service} 서비스 호출 실패")
        self.service = service  # "A" | "B" | "C"


class UpstreamRejectedError(Exception):
    """A/B/C의 4xx/5xx 오류 응답"""

    def __init__(self, service: str, status_code: int, code: str, message: str):
        super().__init__(message)
        self.service = service
        self.status_code = status_code
        self.code = code
        self.message = message
