"""M8-S 批次 A/B/C：登录限流默认 Redis + DATABASE_URL 守卫 + 结构化降级告警。

conftest 在导入 app.main 前 setdefault ``RATE_LIMIT_BACKEND=memory`` 作为测试基线；
本文件验证：生产代码默认 redis、显式 env 可覆盖、生产环境拒绝默认数据库密码、
Redis 后端异常时降级日志含 module/operation/error 结构化字段。
"""

from __future__ import annotations

import logging

import pytest

from app.core.config import Settings, settings
from app.services.auth import login_rate_limit
from app.services.auth.rate_limit_store import (
    get_rate_limit_backend,
    reset_rate_limit_backend_cache,
)
from app.services.observability.metrics_registry import (
    rate_limit_backend_fallback_snapshot,
)


def test_default_backend_is_redis(monkeypatch: pytest.MonkeyPatch) -> None:
    """删除 env 后，代码默认应为 redis（settings 与懒加载后端一致）。"""
    monkeypatch.delenv("RATE_LIMIT_BACKEND", raising=False)

    assert settings.rate_limit_backend == "redis"
    assert Settings().rate_limit_backend == "redis"

    reset_rate_limit_backend_cache()
    assert get_rate_limit_backend() == "redis"


def test_env_override_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    """显式 RATE_LIMIT_BACKEND=memory 仍可覆盖代码默认 redis。"""
    monkeypatch.setenv("RATE_LIMIT_BACKEND", "memory")

    reset_rate_limit_backend_cache()
    assert get_rate_limit_backend() == "memory"


@pytest.mark.asyncio
async def test_redis_fallback_logs_structured_warning(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Redis 后端异常回退 memory：login 降级计数 + operation/error 结构化日志。"""
    monkeypatch.setenv("RATE_LIMIT_BACKEND", "redis")
    reset_rate_limit_backend_cache()
    login_rate_limit.reset_all_login_rate_limits()

    async def _boom() -> None:
        raise ConnectionError("redis down")

    monkeypatch.setattr("app.core.redis.get_redis", _boom)
    with caplog.at_level(logging.WARNING, logger="app.services.auth.login_rate_limit"):
        await login_rate_limit.record_login_failure("203.0.113.66", "user-batch-c")
        await login_rate_limit.is_login_rate_limited("203.0.113.66", "user-batch-c")

    assert rate_limit_backend_fallback_snapshot()["login"] >= 1
    assert "回退 memory" in caplog.text
    assert "module=login" in caplog.text
    assert "operation=write_failures" in caplog.text
    assert "operation=read_failures" in caplog.text
    assert "error=redis down" in caplog.text

    monkeypatch.delenv("RATE_LIMIT_BACKEND", raising=False)
    reset_rate_limit_backend_cache()
    login_rate_limit.reset_all_login_rate_limits()


def test_database_url_default_credential_rejected_in_production(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """生产环境 + 默认 changeme 数据库密码必须 fail-fast。"""
    from app.main import _check_production_guard

    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(
        settings,
        "webhook_encryption_secret",
        "test-only-webhook-encryption-key-0123456789abcdef",
    )
    monkeypatch.setattr(
        settings,
        "database_url",
        "postgresql+asyncpg://ruige:changeme@localhost:5432/ruige",
    )
    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        _check_production_guard()


def test_database_url_default_allowed_in_development(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """开发环境（含 CI）默认 URL 照常放行，不破坏本地/测试基线。"""
    from app.main import _check_production_guard

    monkeypatch.setattr(settings, "environment", "development")
    monkeypatch.setattr(
        settings,
        "database_url",
        "postgresql+asyncpg://ruige:changeme@localhost:5432/ruige",
    )
    _check_production_guard()


def test_production_guard_accepts_safe_database_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """生产环境 + 安全数据库密码通过守卫。"""
    from app.main import _check_production_guard

    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(
        settings,
        "webhook_encryption_secret",
        "test-only-webhook-encryption-key-0123456789abcdef",
    )
    monkeypatch.setattr(
        settings,
        "database_url",
        "postgresql+asyncpg://ruige:strong-random-db-password@localhost:5432/ruige",
    )
    _check_production_guard()
