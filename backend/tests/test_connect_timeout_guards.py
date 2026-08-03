"""P0-11 连接超时守卫：Redis/DB/HTTP 全部外部连接显式 socket/connect timeout。

验收口径（audit-fix-masterplan §2 主题 E · P0-11 T6-D-1）：
- Redis 连接池带 socket_timeout / socket_connect_timeout（settings 驱动，fail-fast）；
- DB 引擎带 asyncpg 建连 timeout + SQLAlchemy pool_timeout；
- HTTP 共享客户端超时 = settings 驱动（DeepSeek / 通义）；
- webhook 发送端保持 timeout=10 基线；
- /health 探活不挂死：超时/不可达 → 快速返回 False。
"""

from __future__ import annotations

import pytest

import app.core.redis as redis_core
from app.api import health as health_api
from app.core.config import settings
from app.core.database import _build_engine, engine
from app.core.http_client import close_all_clients, get_deepseek_client, get_tongyi_client


@pytest.fixture(autouse=True)
async def _reset_external_clients():
    """每个用例后重置 Redis 连接池与 HTTP 共享客户端，避免跨用例串状态。"""
    yield
    await redis_core.close_redis()
    await close_all_clients()


# ── Redis：连接池显式 socket/connect timeout（P0-11 主缺口）─────────────


@pytest.mark.asyncio
async def test_redis_pool_explicit_socket_timeouts(monkeypatch) -> None:
    monkeypatch.setattr(settings, "redis_socket_timeout_seconds", 3.5)
    monkeypatch.setattr(settings, "redis_connect_timeout_seconds", 4.5)
    monkeypatch.setattr(redis_core, "_REDIS_URL", "redis://localhost:6379/9")
    monkeypatch.setattr(redis_core, "_pool", None)

    r = await redis_core.get_redis()
    kwargs = r.connection_pool.connection_kwargs
    assert kwargs["socket_timeout"] == 3.5
    assert kwargs["socket_connect_timeout"] == 4.5
    # fail-fast：超时不自动重试，由调用方降级/拒答
    assert kwargs.get("retry_on_timeout") is False


@pytest.mark.asyncio
async def test_redis_health_probe_fails_fast_on_timeout(monkeypatch) -> None:
    """Redis socket 超时 → /health 探活快速返回 False（不挂死）。"""
    import redis as redis_lib

    class _TimedOutClient:
        async def ping(self) -> bool:
            raise redis_lib.exceptions.TimeoutError("socket timeout")

    class _OkClient:
        async def ping(self) -> bool:
            return True

    async def _timed_out() -> _TimedOutClient:
        return _TimedOutClient()

    async def _ok() -> _OkClient:
        return _OkClient()

    # health.py 在 import 时已绑定 get_redis 引用，需 patch 到其命名空间
    monkeypatch.setattr(health_api, "get_redis", _timed_out)
    assert await health_api._check_redis() is False

    monkeypatch.setattr(health_api, "get_redis", _ok)
    assert await health_api._check_redis() is True


# ── DB：asyncpg 建连 timeout + SQLAlchemy pool_timeout ────────────────


def test_db_engine_explicit_connect_and_pool_timeouts(monkeypatch) -> None:
    import app.core.database as db_core

    captured: dict = {}

    def _fake_create_async_engine(url: str, **kwargs: object):
        captured["url"] = url
        captured["kwargs"] = kwargs
        return object()

    monkeypatch.setattr(db_core, "create_async_engine", _fake_create_async_engine)
    monkeypatch.setattr(settings, "db_connect_timeout_seconds", 7.0)
    monkeypatch.setattr(settings, "db_pool_timeout_seconds", 9.0)

    _build_engine()

    assert captured["url"] == settings.database_url
    assert captured["kwargs"]["pool_pre_ping"] is True
    assert captured["kwargs"]["pool_timeout"] == 9.0
    assert captured["kwargs"]["connect_args"]["timeout"] == 7.0


def test_engine_pool_timeout_matches_settings() -> None:
    """模块级真实引擎（import 时构建）的池排队超时与配置一致。"""
    assert engine.pool._timeout == settings.db_pool_timeout_seconds


@pytest.mark.asyncio
async def test_db_health_probe_fails_fast_on_timeout(monkeypatch) -> None:
    """DB 建连超时 → /health 探活快速返回 False（不挂死）。"""
    import app.core.database as db_core

    class _HangingConn:
        async def __aenter__(self):
            raise TimeoutError("asyncpg connect timeout")

        async def __aexit__(self, *exc: object) -> bool:
            return False

    class _StubEngine:
        def connect(self) -> _HangingConn:
            return _HangingConn()

    monkeypatch.setattr(db_core, "engine", _StubEngine())
    assert await db_core.check_database() is False


# ── HTTP：共享客户端超时 = settings 驱动；webhook 发送端 timeout=10 ────


@pytest.mark.asyncio
async def test_deepseek_client_timeout_settings_driven(monkeypatch) -> None:
    import app.core.http_client as hc

    monkeypatch.setattr(hc, "_deepseek_client", None)
    monkeypatch.setattr(settings, "llm_timeout_seconds", 42.0)

    client = get_deepseek_client()
    expected = 47.0  # llm_timeout_seconds + 5.0
    assert client.timeout.connect == expected
    assert client.timeout.read == expected
    assert client.timeout.write == expected
    assert client.timeout.pool == expected


@pytest.mark.asyncio
async def test_tongyi_client_timeout_takes_max_plus_five(monkeypatch) -> None:
    import app.core.http_client as hc

    monkeypatch.setattr(hc, "_tongyi_client", None)
    monkeypatch.setattr(settings, "embed_timeout_seconds", 10.0)
    monkeypatch.setattr(settings, "rerank_timeout_seconds", 20.0)
    monkeypatch.setattr(settings, "llm_timeout_seconds", 15.0)

    client = get_tongyi_client()
    assert client.timeout.connect == 25.0  # max(10, 20, 15) + 5.0


@pytest.mark.asyncio
async def test_webhook_sender_explicit_10s_timeout_baseline(monkeypatch) -> None:
    """webhook 发送端保留 timeout=10 基线（delta-fix-plan §二 R4/R6）。"""
    import app.services.webhook.sender as sender

    recorded: list[float] = []

    class _FakeResp:
        is_success = True
        status_code = 200

    class _FakeClient:
        def __init__(self, timeout: float):
            recorded.append(timeout)

        async def __aenter__(self) -> "_FakeClient":
            return self

        async def __aexit__(self, *exc: object) -> bool:
            return False

        async def post(self, *args: object, **kwargs: object) -> _FakeResp:
            return _FakeResp()

    monkeypatch.setattr(sender.httpx, "AsyncClient", _FakeClient)

    ok = await sender.send_webhook(
        "https://example.com/hook",
        "whsec_plain",
        "document.completed",
        {"x": 1},
    )
    assert ok is True
    assert recorded == [10]
