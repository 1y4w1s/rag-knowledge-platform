import logging

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
from app.core.logging import get_trace_id

logger = logging.getLogger(__name__)


def _json_response(status_code: int, content: dict) -> JSONResponse:
    """统一响应构造：所有 handler 响应都带 X-Trace-ID（与日志 trace_id 同源）。

    500 路径由 ServerErrorMiddleware 直接用原始 ASGI send 发送，绕开用户中间件，
    因此必须在响应对象上直接带头，才能保证 日志 trace_id == 响应头。
    """
    return JSONResponse(
        status_code=status_code,
        content=content,
        headers={"X-Trace-ID": get_trace_id()},
    )


def _log_5xx(request: Request, exc: Exception, message: str) -> None:
    """P0-13：5xx 统一结构化日志——含请求 path、异常类、完整 traceback。

    自定义 exception handler 注册后 FastAPI 不再打印 traceback，此处兜底。
    """
    logger.exception(
        "5xx 请求异常: %s",
        message,
        extra={"path": request.url.path, "exc_class": type(exc).__name__},
    )


async def _service_error_handler(
    request: Request,
    exc: ServiceError,
) -> JSONResponse:
    status = exc.status_code
    if status >= 500:
        # P2-02/P2-03：ServiceError(500) 视为服务端错误——记全量 detail，对外只给通用文案。
        _log_5xx(request, exc, f"ServiceError({type(exc).__name__}): {exc.detail}")
        content: dict = {"detail": exc.client_message}
    else:
        # 4xx 领域错误是客户端问题，不落 ERROR traceback；保留原有 detail 语义。
        logger.warning(
            "客户端请求错误: %s %s %s",
            type(exc).__name__,
            request.url.path,
            exc.detail,
        )
        content = {"detail": exc.detail}
    return _json_response(status, content)


async def _db_operational_error_handler(
    request: Request,
    exc: OperationalError,
) -> JSONResponse:
    _log_5xx(request, exc, "数据库连接故障")
    return _json_response(503, {"detail": "数据库暂不可用，请稍后重试"})


async def _os_error_handler(
    request: Request,
    exc: OSError,
) -> JSONResponse:
    _log_5xx(request, exc, "存储服务异常")
    return _json_response(503, {"detail": "存储服务异常，请稍后重试"})


async def _generic_error_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    """兜底：未捕获的异常是编程错误 → 500（P2-02：与依赖故障 503 区分）。"""
    _log_5xx(request, exc, "未捕获异常")
    return _json_response(500, {"detail": "服务内部错误，请稍后重试"})


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
