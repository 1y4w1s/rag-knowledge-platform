"""FastAPI exception_handlers：将 ServiceError 子类映射为对应 HTTP status_code 的 JSONResponse。
额外处理 DB 连接错误（OperationalError → 503）和存储错误（OSError → 503）。

注册方式（main.py）：
    for exc_cls, handler in EXCEPTION_HANDLERS:
        app.add_exception_handler(exc_cls, handler)
"""

from fastapi import Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import DBAPIError, OperationalError

from app.core.exceptions import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    RateLimitError,
    ServiceError,
    UnauthorizedError,
    ValidationError,
)


async def _service_error_handler(
    request: Request,
    exc: ServiceError,
) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )


async def _db_operational_error_handler(
    request: Request,
    exc: OperationalError,
) -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content={"detail": "数据库暂不可用，请稍后重试"},
    )


async def _os_error_handler(
    request: Request,
    exc: OSError,
) -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content={"detail": "存储服务异常，请稍后重试"},
    )


async def _generic_error_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    """兜底：未捕获的异常统一返回 500。"""
    return JSONResponse(
        status_code=503,
        content={"detail": "服务暂不可用，请稍后重试"},
    )


EXCEPTION_HANDLERS: list[tuple[type[Exception], type]] = [
    (NotFoundError, _service_error_handler),
    (ConflictError, _service_error_handler),
    (ForbiddenError, _service_error_handler),
    (UnauthorizedError, _service_error_handler),
    (ValidationError, _service_error_handler),
    (RateLimitError, _service_error_handler),
    (ServiceError, _service_error_handler),
    (OperationalError, _db_operational_error_handler),
    (DBAPIError, _db_operational_error_handler),
    (OSError, _os_error_handler),
    (Exception, _generic_error_handler),
]
