"""EW-A4: login rate limit tests (identifier 5/15min + IP 20/5min -> 429)."""
from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.audit_log import AuditLog
from app.services.auth.login_rate_limit import reset_all_login_rate_limits
from tests.conftest import unique_email, unique_username

_STRONG_PW = "Test123!@"

async def _latest_audit_log(*, action: str) -> AuditLog | None:
    async with SessionLocal() as db:
        stmt = (
            select(AuditLog)
            .where(AuditLog.action == action)
            .order_by(AuditLog.created_at.desc())
            .limit(1)
        )
        return await db.scalar(stmt)


@pytest.fixture(autouse=True)
def _isolate_login_rate_limits() -> None:
    reset_all_login_rate_limits()
    yield
    reset_all_login_rate_limits()


@pytest.mark.asyncio
async def test_sixth_failed_login_returns_429(client: AsyncClient) -> None:
    email = unique_email("rl-six")
    username = unique_username("rlsix")
    reg = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "username": username, "password": _STRONG_PW, "account_type": "personal"},
    )
    assert reg.status_code == 201

    for _ in range(5):
        resp = await client.post(
            "/api/v1/auth/login",
            json={"identifier": username, "password": "Wrong!@"},
        )
        assert resp.status_code == 401

    blocked = await client.post(
        "/api/v1/auth/login",
        json={"identifier": username, "password": "Wrong!@"},
    )
    assert blocked.status_code == 429
    assert "15" in blocked.json()["detail"]

    latest = await _latest_audit_log(action="auth.login_rate_limited")
    assert latest is not None


@pytest.mark.asyncio
async def test_successful_login_clears_failure_counter(client: AsyncClient) -> None:
    email = unique_email("rl-clear")
    username = unique_username("rlclear")
    reg = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "username": username, "password": _STRONG_PW, "account_type": "personal"},
    )
    assert reg.status_code == 201

    for _ in range(5):
        resp = await client.post(
            "/api/v1/auth/login",
            json={"identifier": username, "password": "Wrong!@"},
        )
        assert resp.status_code == 401

    ok = await client.post(
        "/api/v1/auth/login",
        json={"identifier": username, "password": _STRONG_PW},
    )
    assert ok.status_code == 200

    for _ in range(5):
        resp = await client.post(
            "/api/v1/auth/login",
            json={"identifier": username, "password": "Wrong!@"},
        )
        assert resp.status_code == 401

    blocked = await client.post(
        "/api/v1/auth/login",
        json={"identifier": username, "password": "Wrong!@"},
    )
    assert blocked.status_code == 429


@pytest.mark.asyncio
async def test_ip_rate_limit_across_users(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.auth.login_rate_limit.MAX_IP_FAILURES",
        3,
    )

    for i in range(3):
        username = unique_username(f"ip-rl-{i}")
        email = unique_email(f"ip-rl-{i}")
        reg = await client.post(
            "/api/v1/auth/register",
            json={"email": email, "username": username, "password": _STRONG_PW, "account_type": "personal"},
        )
        assert reg.status_code == 201
        resp = await client.post(
            "/api/v1/auth/login",
            json={"identifier": username, "password": "Wrong!@"},
        )
        assert resp.status_code == 401

    other = unique_username("ip-rl-final")
    other_email = unique_email("ip-rl-final")
    await client.post(
        "/api/v1/auth/register",
        json={"email": other_email, "username": other, "password": _STRONG_PW, "account_type": "personal"},
    )
    blocked = await client.post(
        "/api/v1/auth/login",
        json={"identifier": other, "password": "Wrong!@"},
    )
    assert blocked.status_code == 429
    assert "IP" in blocked.json()["detail"]

    latest = await _latest_audit_log(action="auth.ip_rate_limited")
    assert latest is not None
