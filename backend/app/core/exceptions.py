"""领域异常层次：替换 services/ 层中 `raise HTTPException` 的标准化方案。

用法：
    from app.core.exceptions import NotFoundError
    raise NotFoundError("文档不存在")

异常自动映射为对应 HTTP JSONResponse（通过 exception_handlers.py 注册）。
"""

from __future__ import annotations


class ServiceError(Exception):
    """领域异常基类。status_code 由子类覆盖。"""

    status_code: int = 500

    def __init__(self, detail: str, *, extra: dict | None = None) -> None:
        self.detail = detail
        self.extra = extra
        super().__init__(detail)


class NotFoundError(ServiceError):
    status_code = 404


class ConflictError(ServiceError):
    status_code = 409


class UnauthorizedError(ServiceError):
    status_code = 401


class ForbiddenError(ServiceError):
    status_code = 403


class ValidationError(ServiceError):
    status_code = 422


class RateLimitError(ServiceError):
    status_code = 429
