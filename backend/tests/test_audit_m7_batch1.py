"""M7 第一批：P2-P1/P2-P2 权限/审计补全的生效证据测试。"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.conftest import create_test_kb, unique_email, unique_username
from tests.fixtures.audit_events import (
    _count_audit_logs,
    _latest_audit_log,
    _register_org_admin,
)

pytestmark = pytest.mark.asyncio


async def test_create_kb_writes_audit_log(
    client: AsyncClient,
    register_and_login,
) -> None:
    headers, user = await register_and_login(prefix="audit-m7-kb-create")

    before = await _count_audit_logs(action="kb.create")

    resp = await client.post(
        "/api/v1/knowledge-bases",
        headers=headers,
        params={"workspace": "personal"},
        json={"name": "M7 建库审计库"},
    )
    assert resp.status_code == 201

    after = await _count_audit_logs(action="kb.create")
    assert after - before == 1

    latest = await _latest_audit_log(action="kb.create")
    assert latest is not None
    assert str(latest.actor_user_id) == user["id"]
    assert str(latest.resource_id) == resp.json()["id"]
    assert str(latest.kb_id) == resp.json()["id"]
    assert latest.resource_type == "kb"
    assert latest.details == {"name": "M7 建库审计库", "scope": "personal"}


async def test_update_kb_writes_audit_log(
    client: AsyncClient,
    register_and_login,
) -> None:
    headers, user = await register_and_login(prefix="audit-m7-kb-update")
    kb = await create_test_kb(client, headers, user, name="M7 改库前名称")

    before = await _count_audit_logs(action="kb.update")

    resp = await client.patch(
        f"/api/v1/knowledge-bases/{kb['id']}",
        headers=headers,
        json={"name": "M7 改库后名称", "description": "审计描述"},
    )
    assert resp.status_code == 200

    after = await _count_audit_logs(action="kb.update")
    assert after - before == 1

    latest = await _latest_audit_log(action="kb.update")
    assert latest is not None
    assert str(latest.actor_user_id) == user["id"]
    assert str(latest.resource_id) == kb["id"]
    assert str(latest.kb_id) == kb["id"]
    assert latest.details == {
        "name": "M7 改库后名称",
        "description": "审计描述",
    }


async def test_transfer_ownership_writes_audit_log(
    client: AsyncClient,
) -> None:
    owner_headers, owner_user = await _register_org_admin(
        client,
        prefix="audit-m7-transfer",
        org_name="M7 转让审计公司",
    )

    member_email = unique_email("audit-m7-transfer-member")
    member_username = unique_username("auditm7transfer")
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

    before = await _count_audit_logs(action="org.ownership_transfer")

    transfer_resp = await client.post(
        "/api/v1/organization/transfer-ownership",
        headers=owner_headers,
        json={"target_user_id": member_user_id},
    )
    assert transfer_resp.status_code == 200

    after = await _count_audit_logs(action="org.ownership_transfer")
    assert after - before == 1

    latest = await _latest_audit_log(action="org.ownership_transfer")
    assert latest is not None
    assert str(latest.actor_user_id) == owner_user["id"]
    assert str(latest.resource_id) == owner_user["org_id"]
    assert latest.resource_type == "organization"
    assert latest.details == {
        "prev_owner_user_id": owner_user["id"],
        "new_owner_user_id": member_user_id,
        "prev_owner_email": owner_user["email"],
        "new_owner_email": member_email,
    }


async def test_create_invite_writes_audit_log(
    client: AsyncClient,
) -> None:
    admin_headers, admin_user = await _register_org_admin(
        client,
        prefix="audit-m7-invite",
        org_name="M7 发码审计公司",
    )

    before = await _count_audit_logs(action="org.invite_create")

    resp = await client.post(
        "/api/v1/organization/invites",
        headers=admin_headers,
        json={},
    )
    assert resp.status_code == 201
    code = resp.json()["code"]

    after = await _count_audit_logs(action="org.invite_create")
    assert after - before == 1

    latest = await _latest_audit_log(action="org.invite_create")
    assert latest is not None
    assert str(latest.actor_user_id) == admin_user["id"]
    assert latest.resource_id is not None
    assert latest.resource_type == "organization_invite_code"
    assert latest.details["code"] == code
    assert latest.details["expires_at"] is not None
