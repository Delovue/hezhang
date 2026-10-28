from enum import StrEnum

from fastapi import HTTPException
from fastapi.responses import JSONResponse


class ErrorCode(StrEnum):
    VALIDATION_ERROR = "VALIDATION_ERROR"
    INVALID_QUERY = "INVALID_QUERY"
    INVALID_EXPENSE = "INVALID_EXPENSE"
    AUTHENTICATION_REQUIRED = "AUTHENTICATION_REQUIRED"
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"
    USERNAME_EXISTS = "USERNAME_EXISTS"
    ACTIVITY_NOT_FOUND = "ACTIVITY_NOT_FOUND"
    INVITE_INVALID = "INVITE_INVALID"
    ACTIVITY_OWNER_REQUIRED = "ACTIVITY_OWNER_REQUIRED"
    ACTIVITY_LOCKED = "ACTIVITY_LOCKED"
    EXPENSE_NOT_FOUND = "EXPENSE_NOT_FOUND"
    EXPENSE_EDIT_FORBIDDEN = "EXPENSE_EDIT_FORBIDDEN"
    EXPENSE_VERSION_CONFLICT = "EXPENSE_VERSION_CONFLICT"
    EXPENSE_MEMBER_MISMATCH = "EXPENSE_MEMBER_MISMATCH"
    REQUEST_ID_CONFLICT = "REQUEST_ID_CONFLICT"
    EXPENSE_DELETED = "EXPENSE_DELETED"
    DATABASE_BUSY = "DATABASE_BUSY"
    DATABASE_NOT_READY = "DATABASE_NOT_READY"
    DATA_CONFLICT = "DATA_CONFLICT"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    NOT_FOUND = "NOT_FOUND"
    METHOD_NOT_ALLOWED = "METHOD_NOT_ALLOWED"
    HTTP_ERROR = "HTTP_ERROR"


class ApiError(HTTPException):
    def __init__(
        self,
        status_code: int,
        code: ErrorCode,
        detail: str,
        *,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(status_code=status_code, detail=detail, headers=headers)
        self.code = code


def error_response(
    status_code: int,
    code: ErrorCode,
    detail: str | list[dict],
    *,
    retryable: bool = False,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"detail": detail, "code": code.value, "retryable": retryable},
        headers=headers,
    )
