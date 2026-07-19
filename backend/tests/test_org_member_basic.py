"""Wave 5.4：组织成员基础操作测试（只读列表 / 注册 Owner / 移除 Owner 保护）。"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.conftest import unique_email, unique_username, workspace_query
from tests.fixtures.org_members import _create_org_member_and_login

pytestmark = pytest.mark.asyncio


async def test_org_member_can_list_members_readonly(
    client: AsyncClient,
    register_and_login,
) -> None:
    admin_headers, admin_user = await register_and_login(
        prefix="member-roster",
        account_type="enterprise",
        org_name="只读花名册公司",
    )
    member_headers, _ = await _create_org_member_and_login(
        client,
        org_id=admin_user["org_id"],
    )

    resp = await client.get("/api/v1/organization/members", headers=member_headers)
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 2


async def test_team_creator_register_has_is_owner(client: AsyncClient) -> None:
    email = unique_email("owner-creator")
    username = unique_username("owner-creator")
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "username": username,
            "password": "Test123!@",
            "account_type": "enterprise",
            "org_name": "Owner 创建团队",
        },
    )
    assert resp.status_code == 201
    user = resp.json()["user"]
    assert user["org_role"] == "admin"
    assert user["is_owner"] is True


async def test_cannot_remove_owner(
    client: AsyncClient,
    register_and_login,
) -> None:
    admin_headers, admin_user = await register_and_login(
        prefix="owner-protect",
        account_type="enterprise",
        org_name="Owner 保护公司",
    )
    resp = await client.delete(
        f"/api/v1/organization/members/{admin_user['id']}",
        headers=admin_headers,
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "不能移除团队所有者"


async def test_org_admin_can_list_members(
    client: AsyncClient,
    register_and_login,
) -> None:
    admin_headers, admin_user = await register_and_login(
        prefix="list-members",
        account_type="enterprise",
        org_name="列表测试公司",
    )
    await _create_org_member_and_login(client, org_id=admin_user["org_id"])

    resp = await client.get("/api/v1/organization/members", headers=admin_headers)
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 2
    roles = {item["role"] for item in items}
    assert roles == {"admin", "member"}
    for item in items:
        assert "email" in item
        assert "joined_at" in item
        assert "user_id" in item
        assert "is_owner" in item
    owners = [item for item in items if item["is_owner"]]
    assert len(owners) == 1


async def test_ac5_admin_adds_member_by_email_member_can_access_kb(
    client: AsyncClient,
    register_and_login,
) -> None:
    admin_headers, admin_user = await register_and_login(
        prefix="ac5-admin",
        account_type="enterprise",
        org_name="AC5 公司",
    )
    from tests.conftest import create_test_kb as _create_kb

    kb = await _create_kb(client, admin_headers, admin_user, name="共享资料库")

    from tests.fixtures.org_members import _register_personal_user

    invitee = await _register_personal_user(client, prefix="ac5-invitee")
    add_resp = await client.post(
        "/api/v1/organization/members",
        headers=admin_headers,
        json={"email": invitee["email"]},
    )
    assert add_resp.status_code == 201
    assert add_resp.json()["role"] == "member"
    assert add_resp.json()["email"] == invitee["email"]

    member_login = await client.post(
        "/api/v1/auth/login",
        json={"identifier": invitee["email"], "password": "Test123!@"},
    )
    assert member_login.status_code == 200
    member_user = member_login.json()["user"]
    assert member_user["org_id"] == admin_user["org_id"]
    assert member_user["org_role"] == "member"
    member_headers = {"Authorization": f"Bearer {member_login.json()['access_token']}"}

    list_resp = await client.get(
        "/api/v1/knowledge-bases",
        headers=member_headers,
        params=workspace_query(admin_user),
    )
    assert list_resp.status_code == 200
    assert len(list_resp.json()["items"]) == 1
    assert list_resp.json()["items"][0]["id"] == kb["id"]

    get_resp = await client.get(
        f"/api/v1/knowledge-bases/{kb['id']}",
        headers=member_headers,
    )
    assert get_resp.status_code == 200
