"""FastAPI exception_handlers：将 ServiceError 子类映射为对应 HTTP status_code 的 JSONResponse。

注册方式（main.py）：
    for exc_cls, handler in EXCEPTION_HANDLERS:
        app.add_exception_handler(exc_cls, handler)
"""

from fastapi import Request
from fastapi.responses import JSONResponse

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


EXCEPTION_HANDLERS: list[tuple[type[Exception], type]] = [
    (NotFoundError, _service_error_handler),
    (ConflictError, _service_error_handler),
    (ForbiddenError, _service_error_handler),
    (UnauthorizedError, _service_error_handler),
    (ValidationError, _service_error_handler),
    (RateLimitError, _service_error_handler),
    (ServiceError, _service_error_handler),
]
