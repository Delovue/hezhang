from enum import StrEnum

from fastapi import HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field


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


class ValidationIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")
    loc: list[str | int]
    msg: str
    type: str


class ErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    detail: str | list[ValidationIssue] = Field(description="中文业务提示或字段校验问题")
    code: ErrorCode = Field(description="稳定错误码，前端据此选择处理方式")
    retryable: bool = Field(description="仅数据库暂忙为 true；重试仍须复用原请求并限制次数")


API_ERROR_RESPONSES = {
    401: {"model": ErrorResponse, "description": "需要认证或登录凭证错误"},
    403: {"model": ErrorResponse, "description": "当前成员无权执行此操作"},
    404: {"model": ErrorResponse, "description": "资源不存在或不可访问"},
    409: {
        "model": ErrorResponse,
        "description": "业务状态、请求编号、版本或数据库冲突；按 code 处理",
        "headers": {
            "Retry-After": {
                "description": "仅 DATABASE_BUSY 返回，建议等待的秒数",
                "schema": {"type": "integer", "minimum": 1},
            }
        },
        "content": {
            "application/json": {
                "examples": {
                    "version_conflict": {
                        "value": {
                            "detail": "费用已被修改，请刷新后重试",
                            "code": "EXPENSE_VERSION_CONFLICT",
                            "retryable": False,
                        }
                    },
                    "database_busy": {
                        "value": {
                            "detail": "账本正在更新，请稍后重试",
                            "code": "DATABASE_BUSY",
                            "retryable": True,
                        }
                    },
                }
            }
        },
    },
    422: {"model": ErrorResponse, "description": "字段格式或业务输入校验未通过"},
    500: {"model": ErrorResponse, "description": "未预期错误，先核对已有账目结果"},
    503: {"model": ErrorResponse, "description": "数据库未就绪，需要检查连接或迁移"},
}


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
