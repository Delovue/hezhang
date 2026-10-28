"""领域错误类型。

错误类别决定 HTTP 状态码，code 为 app.errors.ErrorCode 中的稳定错误码，供前端分支处理：
- InvalidInputError  -> 422 金额、成员等输入不合法
- PermissionDeniedError -> 403 当前用户无权执行该操作
- StateConflictError -> 409 业务状态或额度冲突
"""

from app.errors import ErrorCode


class DomainError(Exception):
    """所有领域错误的基类。"""

    def __init__(self, code: ErrorCode, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class InvalidInputError(DomainError):
    pass


class PermissionDeniedError(DomainError):
    pass


class StateConflictError(DomainError):
    pass
