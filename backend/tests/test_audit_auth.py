"""EW-A3：认证审计事件测试（login_failed / login_success）。"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.conftest import unique_email, unique_username
from tests.fixtures.audit_events import _count_audit_logs, _latest_audit_log

pytestmark = pytest.mark.asyncio


async def test_login_failed_writes_audit_log(client: AsyncClient) -> None:
    """登录失败连点 N 次，audit_logs 有 auth.login_failed 行。"""
    email = unique_email("audit-fail")
    username = unique_username("auditfail")
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

    before = await _count_audit_logs(action="auth.login_failed")

    for _ in range(3):
        resp = await client.post(
            "/api/v1/auth/login",
            json={"identifier": username, "password": "wrongpassword"},
        )
        assert resp.status_code == 401

    after = await _count_audit_logs(action="auth.login_failed")
    assert after - before == 3

    latest = await _latest_audit_log(action="auth.login_failed")
    assert latest is not None
    assert latest.actor_user_id is None
    assert latest.details == {"identifier": username}


async def test_login_success_writes_audit_log(client: AsyncClient) -> None:
    email = unique_email("audit-ok")
    username = unique_username("auditok")
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
    user_id = reg.json()["user"]["id"]

    before = await _count_audit_logs(action="auth.login")

    resp = await client.post(
        "/api/v1/auth/login",
        json={"identifier": email, "password": password},
    )
    assert resp.status_code == 200

    after = await _count_audit_logs(action="auth.login")
    assert after - before == 1

    latest = await _latest_audit_log(action="auth.login")
    assert latest is not None
    assert str(latest.actor_user_id) == user_id
    assert latest.resource_type == "user"
    assert str(latest.resource_id) == user_id
