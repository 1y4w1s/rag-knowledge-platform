"""NW-26：限流 429 → /metrics ruige_rate_limit_rejected_total。"""

from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import AsyncClient

from app.core.config import settings
from app.core.exceptions import RateLimitError
from app.services.auth import api_rate_limit as api_rl
from app.services.auth import login_rate_limit as login_rl
from app.services.auth.api_rate_limit import ApiRateLimitKind
from app.services.auth.login_rate_limit import enforce_forgot_password_rate_limit
from app.services.observability.metrics_registry import (
    RATE_LIMIT_REJECT_KINDS,
    reset_process_counters_for_tests,
)

METRICS_TOKEN = "test-metrics-token"


# 恢复真实限流实现：本模块直接调用 enforce_api_rate_limit 的用例需真实 429
pytestmark = pytest.mark.usefixtures("real_api_rate_limit")


@pytest.fixture(autouse=True)
def _auth_metrics(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """P0-3 修复后 /metrics 需携带 METRICS_BEARER_TOKEN；本模块自动带上以保住既有断言。"""
    monkeypatch.setattr(settings, "metrics_bearer_token", METRICS_TOKEN)
    client.headers["Authorization"] = f"Bearer {METRICS_TOKEN}"
    yield


@pytest.fixture(autouse=True)
def _reset() -> None:
    reset_process_counters_for_tests()
    api_rl.reset_all_api_rate_limits()
    login_rl.reset_all_login_rate_limits()
    yield
    reset_process_counters_for_tests()
    api_rl.reset_all_api_rate_limits()
    login_rl.reset_all_login_rate_limits()


@pytest.mark.asyncio
async def test_metrics_exposes_rate_limit_rejected_skeleton(client: AsyncClient) -> None:
    resp = await client.get("/metrics")
    assert resp.status_code == 200
    body = resp.text
    assert "ruige_rate_limit_rejected_total" in body
    for kind in RATE_LIMIT_REJECT_KINDS:
        assert f'ruige_rate_limit_rejected_total{{kind="{kind}"}} 0' in body


@pytest.mark.asyncio
async def test_chat_429_increments_metrics(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(api_rl, "CHAT_MAX_REQUESTS", 2)
    uid = uuid4()
    await api_rl.enforce_api_rate_limit(ApiRateLimitKind.chat, uid)
    await api_rl.enforce_api_rate_limit(ApiRateLimitKind.chat, uid)
    with pytest.raises(RateLimitError):
        await api_rl.enforce_api_rate_limit(ApiRateLimitKind.chat, uid)

    resp = await client.get("/metrics")
    assert 'ruige_rate_limit_rejected_total{kind="chat"} 1' in resp.text
    assert 'ruige_rate_limit_rejected_total{kind="upload"} 0' in resp.text


@pytest.mark.asyncio
async def test_upload_and_search_429_kinds(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(api_rl, "UPLOAD_MAX_REQUESTS", 1)
    monkeypatch.setattr(api_rl, "SEARCH_MAX_REQUESTS", 1)
    u1, u2 = uuid4(), uuid4()
    await api_rl.enforce_api_rate_limit(ApiRateLimitKind.upload, u1)
    with pytest.raises(RateLimitError):
        await api_rl.enforce_api_rate_limit(ApiRateLimitKind.upload, u1)
    await api_rl.enforce_api_rate_limit(ApiRateLimitKind.search, u2)
    with pytest.raises(RateLimitError):
        await api_rl.enforce_api_rate_limit(ApiRateLimitKind.search, u2)

    body = (await client.get("/metrics")).text
    assert 'ruige_rate_limit_rejected_total{kind="upload"} 1' in body
    assert 'ruige_rate_limit_rejected_total{kind="search"} 1' in body


@pytest.mark.asyncio
async def test_forgot_password_429_increments_metrics(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(login_rl, "FORGOT_PASSWORD_MAX", 2)
    ip = "203.0.113.50"
    await enforce_forgot_password_rate_limit(ip)
    await enforce_forgot_password_rate_limit(ip)
    with pytest.raises(RateLimitError):
        await enforce_forgot_password_rate_limit(ip)

    resp = await client.get("/metrics")
    assert 'ruige_rate_limit_rejected_total{kind="forgot"} 1' in resp.text


@pytest.mark.asyncio
async def test_login_429_increments_metrics(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tests.conftest import unique_email, unique_username

    monkeypatch.setattr(login_rl, "MAX_FAILURES", 2)
    email = unique_email("nw26-login")
    username = unique_username("nw26lg")
    strong = "Test123!@"

    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "username": username,
            "password": strong,
            "account_type": "personal",
        },
    )
    assert reg.status_code == 201, reg.text

    for _ in range(2):
        bad = await client.post(
            "/api/v1/auth/login",
            json={"identifier": username, "password": "Wrong!@"},
        )
        assert bad.status_code == 401, bad.text

    blocked = await client.post(
        "/api/v1/auth/login",
        json={"identifier": username, "password": "Wrong!@"},
    )
    assert blocked.status_code == 429, blocked.text

    resp = await client.get("/metrics")
    assert 'ruige_rate_limit_rejected_total{kind="login"} 1' in resp.text


@pytest.mark.asyncio
async def test_metrics_requires_token(client: AsyncClient) -> None:
    """P0-3 回归：匿名（无令牌）读取 /metrics 必须被拒。"""
    client.headers.pop("Authorization", None)
    resp = await client.get("/metrics")
    assert resp.status_code == 401
