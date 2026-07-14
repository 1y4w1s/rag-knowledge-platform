"""EW-A4：登录失败限流（5 次/15min → 429 + auth.login_rate_limited）。"""

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.audit_log import AuditLog
from app.services.auth.login_rate_limit import reset_all_login_rate_limits
from tests.conftest import unique_email, unique_username


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
    """第 1～5 次错误密码 401；第 6 次 429 且写 auth.login_rate_limited。"""
    email = unique_email("rl-six")
    username = unique_username("rlsix")
    password = "password123"
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "username": username,
            "password": password,
            "account_type": "personal",
        },
    )
    assert reg.status_code == 201

    for _ in range(5):
        resp = await client.post(
            "/api/v1/auth/login",
            json={"identifier": username, "password": "wrong-password"},
        )
        assert resp.status_code == 401

    blocked = await client.post(
        "/api/v1/auth/login",
        json={"identifier": username, "password": "wrong-password"},
    )
    assert blocked.status_code == 429
    assert "15" in blocked.json()["detail"]

    latest = await _latest_audit_log(action="auth.login_rate_limited")
    assert latest is not None
    assert latest.details == {"identifier": username}


@pytest.mark.asyncio
async def test_successful_login_clears_failure_counter(client: AsyncClient) -> None:
    """成功登录后计数重置，可再次尝试错误密码直至再次触顶。"""
    email = unique_email("rl-clear")
    username = unique_username("rlclear")
    password = "password123"
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "username": username,
            "password": password,
            "account_type": "personal",
        },
    )
    assert reg.status_code == 201

    for _ in range(5):
        resp = await client.post(
            "/api/v1/auth/login",
            json={"identifier": username, "password": "wrong-password"},
        )
        assert resp.status_code == 401

    ok = await client.post(
        "/api/v1/auth/login",
        json={"identifier": username, "password": password},
    )
    assert ok.status_code == 200

    for _ in range(5):
        resp = await client.post(
            "/api/v1/auth/login",
            json={"identifier": username, "password": "wrong-password"},
        )
        assert resp.status_code == 401

    blocked = await client.post(
        "/api/v1/auth/login",
        json={"identifier": username, "password": "wrong-password"},
    )
    assert blocked.status_code == 429
