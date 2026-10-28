"""领域错误类型。

接口层按以下约定映射状态码：
- InvalidInputError  -> 422 金额、成员等输入不合法
- PermissionDeniedError -> 403 当前用户无权执行该操作
- StateConflictError -> 409 业务状态或额度冲突
"""


class DomainError(Exception):
    """所有领域错误的基类。"""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class InvalidInputError(DomainError):
    pass


class PermissionDeniedError(DomainError):
    pass


class StateConflictError(DomainError):
    pass
