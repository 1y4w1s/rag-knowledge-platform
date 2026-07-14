"""Wave 5.4：成员权限控制测试（member 不可删 KB / remove 后丧失权限）。"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.conftest import create_test_kb as _create_kb
from tests.fixtures.org_members import _register_personal_user

pytestmark = pytest.mark.asyncio


async def test_ac6_member_cannot_delete_kb_after_being_added(
    client: AsyncClient,
    register_and_login,
) -> None:
    admin_headers, admin_user = await register_and_login(
        prefix="ac6-admin",
        account_type="enterprise",
        org_name="AC6 公司",
    )
    kb = await _create_kb(client, admin_headers, admin_user)

    invitee = await _register_personal_user(client, prefix="ac6-invitee")
    await client.post(
        "/api/v1/organization/members",
        headers=admin_headers,
        json={"email": invitee["email"]},
    )

    member_login = await client.post(
        "/api/v1/auth/login",
        json={"identifier": invitee["email"], "password": "password123"},
    )
    member_headers = {"Authorization": f"Bearer {member_login.json()['access_token']}"}

    del_resp = await client.delete(
        f"/api/v1/knowledge-bases/{kb['id']}",
        headers=member_headers,
    )
    assert del_resp.status_code == 403


async def test_ac9_admin_removes_member_member_loses_kb_access(
    client: AsyncClient,
    register_and_login,
) -> None:
    admin_headers, admin_user = await register_and_login(
        prefix="ac9-admin",
        account_type="enterprise",
        org_name="AC9 公司",
    )
    kb = await _create_kb(client, admin_headers, admin_user)

    invitee = await _register_personal_user(client, prefix="ac9-invitee")
    add_resp = await client.post(
        "/api/v1/organization/members",
        headers=admin_headers,
        json={"email": invitee["email"]},
    )
    invitee_id = add_resp.json()["user_id"]

    member_login = await client.post(
        "/api/v1/auth/login",
        json={"identifier": invitee["email"], "password": "password123"},
    )
    member_headers = {"Authorization": f"Bearer {member_login.json()['access_token']}"}
    assert (
        await client.get(f"/api/v1/knowledge-bases/{kb['id']}", headers=member_headers)
    ).status_code == 200

    remove_resp = await client.delete(
        f"/api/v1/organization/members/{invitee_id}",
        headers=admin_headers,
    )
    assert remove_resp.status_code == 204

    after_login = await client.post(
        "/api/v1/auth/login",
        json={"identifier": invitee["email"], "password": "password123"},
    )
    assert after_login.status_code == 200
    after_headers = {
        "Authorization": f"Bearer {after_login.json()['access_token']}"
    }
    assert after_login.json()["user"]["org_id"] is None

    list_resp = await client.get(
        "/api/v1/knowledge-bases",
        headers=after_headers,
        params={"workspace": "personal"},
    )
    assert list_resp.status_code == 200
    assert list_resp.json()["items"] == []

    get_resp = await client.get(
        f"/api/v1/knowledge-bases/{kb['id']}",
        headers=after_headers,
    )
    assert get_resp.status_code == 403
