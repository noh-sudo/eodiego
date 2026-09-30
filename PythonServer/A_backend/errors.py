"""A 공통 예외 (main.py에서 ErrorResponse로 변환)"""

from __future__ import annotations

from shared.schemas import ErrorCode, ErrorResponse


class AppError(Exception):
    code: str = ErrorCode.INTERNAL_ERROR
    status_code: int = 500

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message

    def to_response(self) -> ErrorResponse:
        return ErrorResponse(error={"code": self.code, "message": self.message})


class DuplicateUserError(AppError):
    code = ErrorCode.DUPLICATE_USER
    status_code = 409


class InvalidCredentialsError(AppError):
    code = ErrorCode.INVALID_CREDENTIALS
    status_code = 401


class AuthRequiredError(AppError):
    code = ErrorCode.AUTH_REQUIRED
    status_code = 401


class SessionExpiredError(AppError):
    code = ErrorCode.SESSION_EXPIRED
    status_code = 401


class PlanNotFoundError(AppError):
    code = ErrorCode.NOT_FOUND
    status_code = 404
