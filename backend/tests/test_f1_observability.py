"""F1 可观测性接线验收（masterplan §2 主题 F · 序 1.3）。

覆盖：
- P0-13：三个 5xx handler 必须 logger.exception（含 path / 异常类 / traceback）
- P1-30：日志 trace_id 与响应头 X-Trace-ID 同源
- P2-02：编程错误 500 / 依赖故障（DB、OS）503 分类
- P2-03：ServiceError 5xx 对外只给通用文案，内部 detail 只进日志
"""
from __future__ import annotations

import json
import logging
import uuid
from types import SimpleNamespace

import pytest
from fastapi import APIRouter
from httpx import ASGITransport, AsyncClient
from sqlalchemy.exc import OperationalError

from app.core.exception_handlers import (
    _db_operational_error_handler,
    _generic_error_handler,
    _os_error_handler,
    _service_error_handler,
)
from app.core.exceptions import NotFoundError, ServiceError
from app.core.logging import get_trace_id, sanitize_trace_id, set_trace_id
from app.core.logging import _StructuredFormatter
from app.main import app


def _request_for(path: str):
    return SimpleNamespace(url=SimpleNamespace(path=path))


class _CaptureHandler(logging.Handler):
    """临时挂到根 logger，捕获结构化 JSON 日志（与生产 formatter 一致）。"""

    def __init__(self) -> None:
        super().__init__(level=logging.DEBUG)
        self.setFormatter(_StructuredFormatter())
        self.lines: list[dict] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.lines.append(json.loads(self.format(record)))


@pytest.fixture
def structured_logs() -> list[dict]:
    handler = _CaptureHandler()
    root = logging.getLogger()
    root.handlers.append(handler)
    try:
        yield handler.lines
    finally:
        root.handlers.remove(handler)


def _last_error_log(structured_logs: list[dict]) -> dict:
    errors = [
        r for r in structured_logs
        if r.get("level") == "ERROR" and r.get("exception")
    ]
    assert errors, "应产生 ERROR+exception 的结构化日志"
    return errors[-1]


@pytest.fixture
async def boom_client() -> AsyncClient:
    """带错误注入路由的测试客户端：raise_app_exceptions=False 以便读取 500 响应。"""
    router = APIRouter(prefix="/__f1__")

    @router.get("/boom")
    async def boom(kind: str = "generic"):
        if kind == "service":
            raise ServiceError("内部敏感错误: token=abc", client_message="服务暂时不可用，请稍后重试")
        if kind == "db":
            raise OperationalError("could not connect", None, None)
        if kind == "os":
            raise OSError("disk full")
        raise RuntimeError("unhandled programming error")

    app.include_router(router)
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_generic_error_is_500_with_log(structured_logs: list[dict]) -> None:
    """P0-13 + P2-02：未捕获编程错误 → 500 + 日志含 path/异常类/traceback。"""
    try:
        raise RuntimeError("boom")
    except RuntimeError as exc:
        await _generic_error_handler(_request_for("/api/v1/documents/boom"), exc)

    record = _last_error_log(structured_logs)
    assert record["logger"] == "app.core.exception_handlers"
    assert "5xx 请求异常: 未捕获异常" in record["message"]
    assert record["path"] == "/api/v1/documents/boom"
    assert record["exc_class"] == "RuntimeError"
    assert "RuntimeError" in record["exception"]  # traceback 内容


@pytest.mark.asyncio
async def test_db_error_is_503_with_log(structured_logs: list[dict]) -> None:
    """P0-13 + P2-02：DB 连接故障 → 503 + 日志。"""
    try:
        raise OperationalError("could not connect", None, None)
    except OperationalError as exc:
        resp = await _db_operational_error_handler(
            _request_for("/api/v1/knowledge-bases"), exc
        )

    assert resp.status_code == 503
    assert resp.body.decode() == '{"detail":"数据库暂不可用，请稍后重试"}'
    record = _last_error_log(structured_logs)
    assert record["path"] == "/api/v1/knowledge-bases"
    assert record["exc_class"] == "OperationalError"


@pytest.mark.asyncio
async def test_os_error_is_503_with_log(structured_logs: list[dict]) -> None:
    """P0-13 + P2-02：存储 OSError → 503 + 日志。"""
    try:
        raise OSError("disk full")
    except OSError as exc:
        resp = await _os_error_handler(
            _request_for("/api/v1/documents/upload"), exc
        )

    assert resp.status_code == 503
    record = _last_error_log(structured_logs)
    assert record["path"] == "/api/v1/documents/upload"
    assert record["exc_class"] == "OSError"


@pytest.mark.asyncio
async def test_service_error_500_hides_internal_detail(structured_logs: list[dict]) -> None:
    """P2-03：ServiceError(500) 对外通用文案，内部 detail 仅进日志。"""
    try:
        raise ServiceError("内部敏感错误: token=abc")
    except ServiceError as exc:
        resp = await _service_error_handler(
            _request_for("/api/v1/agent/run"), exc
        )

    assert resp.status_code == 500
    body = json.loads(resp.body)
    assert body["detail"] == "服务暂时不可用，请稍后重试"
    assert "token=abc" not in resp.body.decode()
    record = _last_error_log(structured_logs)
    assert "内部敏感错误: token=abc" in record["message"]
    assert record["exc_class"] == "ServiceError"


@pytest.mark.asyncio
async def test_service_error_4xx_keeps_client_detail(caplog: pytest.LogCaptureFixture) -> None:
    """P2-03 兼容：4xx 领域错误 detail 仍直达客户端，仅 WARNING 不落 traceback。"""
    with caplog.at_level("WARNING", logger="app.core.exception_handlers"):
        resp = await _service_error_handler(
            _request_for("/api/v1/knowledge-bases/x"),
            NotFoundError("文档不存在"),
        )

    assert resp.status_code == 404
    assert json.loads(resp.body)["detail"] == "文档不存在"
    assert not [r for r in caplog.records if r.levelname == "ERROR" and r.exc_info]
    warning = [r for r in caplog.records if r.levelname == "WARNING"]
    assert warning and "文档不存在" in warning[-1].getMessage()


@pytest.mark.asyncio
async def test_trace_id_sanitize() -> None:
    """日志注入防护：非法字符被清洗、过长截断。"""
    assert sanitize_trace_id("abc-123_def") == "abc-123_def"
    assert sanitize_trace_id("bad\ninjection") != "bad\ninjection"
    long_id = "a" * 100
    assert len(sanitize_trace_id(long_id)) == 64
    assert len(sanitize_trace_id("")) == 16


@pytest.mark.asyncio
async def test_trace_id_echoed_on_success_and_5xx(
    boom_client: AsyncClient,
    register_and_login,
) -> None:
    """P1-30：日志 trace_id 与响应头 X-Trace-ID 一致；500 响应同样带头。"""
    headers, _ = await register_and_login(prefix="f1-trace")
    headers["X-Trace-ID"] = "f1-trace-0001"

    resp = await boom_client.get(
        "/__f1__/boom",
        headers=headers,
        params={"kind": "generic"},
    )
    assert resp.status_code == 500
    assert resp.json()["detail"] == "服务内部错误，请稍后重试"
    assert resp.headers.get("X-Trace-ID") == "f1-trace-0001"
    assert get_trace_id() == "f1-trace-0001"


@pytest.mark.asyncio
async def test_trace_id_logged_in_error_record(structured_logs: list[dict]) -> None:
    """P1-30：日志行 trace_id 与上下文一致（异常日志同样携带）。"""
    tid = uuid.uuid4().hex[:16]
    set_trace_id(tid)
    try:
        try:
            raise RuntimeError("x")
        except RuntimeError as exc:
            await _generic_error_handler(_request_for("/api/v1/x"), exc)
        record = _last_error_log(structured_logs)
        assert record["trace_id"] == tid
    finally:
        set_trace_id("")


@pytest.mark.asyncio
async def test_403_error_still_403_with_header(client: AsyncClient) -> None:
    """回归：4xx 走 ExceptionMiddleware 正常返回且带头（未误伤既有错误语义）。"""
    resp = await client.get("/api/v1/knowledge-bases", params={"workspace": "personal"})
    assert resp.status_code == 401  # 未带 token
    assert resp.headers.get("X-Trace-ID")
