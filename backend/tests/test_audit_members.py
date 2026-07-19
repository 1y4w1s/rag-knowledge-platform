"""EW-A3：组织成员审计事件测试（add / remove / role_change）。"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.conftest import unique_email, unique_username
from tests.fixtures.audit_events import _count_audit_logs, _latest_audit_log

pytestmark = pytest.mark.asyncio


async def test_add_member_writes_audit_log(
    client: AsyncClient,
    register_and_login,
) -> None:
    admin_headers, admin_user = await register_and_login(
        prefix="audit-org-add",
        account_type="enterprise",
        org_name="审计成员公司",
    )

    member_email = unique_email("audit-member")
    member_username = unique_username("auditmember")
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": member_email,
            "username": member_username,
            "password": "Test123!@",
            "account_type": "personal",
        },
    )
    assert reg.status_code == 201
    member_user_id = reg.json()["user"]["id"]

    before = await _count_audit_logs(action="org.member_add")

    add_resp = await client.post(
        "/api/v1/organization/members",
        headers=admin_headers,
        json={"email": member_email},
    )
    assert add_resp.status_code == 201

    after = await _count_audit_logs(action="org.member_add")
    assert after - before == 1

    latest = await _latest_audit_log(action="org.member_add")
    assert latest is not None
    assert str(latest.actor_user_id) == admin_user["id"]
    assert str(latest.resource_id) == member_user_id
    assert latest.details == {"email": member_email, "role": "member"}


async def test_remove_member_writes_audit_log(
    client: AsyncClient,
    register_and_login,
) -> None:
    admin_headers, admin_user = await register_and_login(
        prefix="audit-org-rm",
        account_type="enterprise",
        org_name="移除成员审计",
    )

    member_email = unique_email("audit-rm-member")
    member_username = unique_username("auditrm")
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": member_email,
            "username": member_username,
            "password": "Test123!@",
            "account_type": "personal",
        },
    )
    assert reg.status_code == 201
    member_user_id = reg.json()["user"]["id"]

    add_resp = await client.post(
        "/api/v1/organization/members",
        headers=admin_headers,
        json={"email": member_email},
    )
    assert add_resp.status_code == 201

    before = await _count_audit_logs(action="org.member_remove")

    del_resp = await client.delete(
        f"/api/v1/organization/members/{member_user_id}",
        headers=admin_headers,
    )
    assert del_resp.status_code == 204

    after = await _count_audit_logs(action="org.member_remove")
    assert after - before == 1

    latest = await _latest_audit_log(action="org.member_remove")
    assert latest is not None
    assert str(latest.actor_user_id) == admin_user["id"]
    assert str(latest.resource_id) == member_user_id


async def test_role_change_writes_audit_log(
    client: AsyncClient,
    register_and_login,
) -> None:
    owner_headers, owner_user = await register_and_login(
        prefix="audit-role",
        account_type="enterprise",
        org_name="改角色审计",
    )

    member_email = unique_email("audit-role-member")
    member_username = unique_username("auditrole")
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": member_email,
            "username": member_username,
            "password": "Test123!@",
            "account_type": "personal",
        },
    )
    assert reg.status_code == 201
    member_user_id = reg.json()["user"]["id"]

    add_resp = await client.post(
        "/api/v1/organization/members",
        headers=owner_headers,
        json={"email": member_email},
    )
    assert add_resp.status_code == 201

    before = await _count_audit_logs(action="org.role_change")

    patch_resp = await client.patch(
        f"/api/v1/organization/members/{member_user_id}",
        headers=owner_headers,
        json={"role": "admin"},
    )
    assert patch_resp.status_code == 200

    after = await _count_audit_logs(action="org.role_change")
    assert after - before == 1

    latest = await _latest_audit_log(action="org.role_change")
    assert latest is not None
    assert str(latest.actor_user_id) == owner_user["id"]
    assert latest.details == {
        "email": member_email,
        "old_role": "member",
        "new_role": "admin",
    }
