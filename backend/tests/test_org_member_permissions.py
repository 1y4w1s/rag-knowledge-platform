"""Wave 5.4：成员 API 权限边界测试（personal 无权限 / member 只读 / 重复添加 / 404 / 保护 Admin）。"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

from tests.fixtures.org_members import _create_org_member_and_login, _register_personal_user

pytestmark = pytest.mark.asyncio


async def test_personal_user_cannot_access_members_api(
    client: AsyncClient,
    register_and_login,
) -> None:
    headers, _user = await register_and_login(prefix="personal-members")

    get_resp = await client.get("/api/v1/organization/members", headers=headers)
    assert get_resp.status_code == 403
    assert get_resp.json()["detail"] == "需要团队账号"

    post_resp = await client.post(
        "/api/v1/organization/members",
        headers=headers,
        json={"email": "someone@example.com"},
    )
    assert post_resp.status_code == 403


async def test_org_member_cannot_mutate_members_api(
    client: AsyncClient,
    register_and_login,
) -> None:
    admin_headers, admin_user = await register_and_login(
        prefix="deny-member-api",
        account_type="enterprise",
        org_name="成员无权写公司",
    )
    member_headers, member_user = await _create_org_member_and_login(
        client,
        org_id=admin_user["org_id"],
    )

    get_resp = await client.get("/api/v1/organization/members", headers=member_headers)
    assert get_resp.status_code == 200

    post_resp = await client.post(
        "/api/v1/organization/members",
        headers=member_headers,
        json={"email": "x@example.com"},
    )
    assert post_resp.status_code == 403

    patch_resp = await client.patch(
        f"/api/v1/organization/members/{admin_user['id']}",
        headers=member_headers,
        json={"role": "member"},
    )
    assert patch_resp.status_code == 403


async def test_add_member_duplicate_rejected(
    client: AsyncClient,
    register_and_login,
) -> None:
    admin_headers, admin_user = await register_and_login(
        prefix="dup-add",
        account_type="enterprise",
        org_name="重复添加公司",
    )
    _member_headers, member_user = await _create_org_member_and_login(
        client,
        org_id=admin_user["org_id"],
    )

    resp = await client.post(
        "/api/v1/organization/members",
        headers=admin_headers,
        json={"email": member_user["email"]},
    )
    assert resp.status_code == 409
    assert resp.json()["detail"] == "该用户已是团队成员"


async def test_add_member_user_not_found(
    client: AsyncClient,
    register_and_login,
) -> None:
    headers, _user = await register_and_login(
        prefix="not-found",
        account_type="enterprise",
        org_name="找不到用户公司",
    )
    resp = await client.post(
        "/api/v1/organization/members",
        headers=headers,
        json={"email": "nobody-here@example.com"},
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "未找到该邮箱对应的用户"


async def test_remove_non_member_rejected(
    client: AsyncClient,
    register_and_login,
) -> None:
    headers, _user = await register_and_login(
        prefix="remove-missing",
        account_type="enterprise",
        org_name="移除非成员公司",
    )
    random_id = uuid.uuid4()
    resp = await client.delete(
        f"/api/v1/organization/members/{random_id}",
        headers=headers,
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "该用户不是团队成员"


async def test_cannot_remove_org_admin(
    client: AsyncClient,
    register_and_login,
) -> None:
    admin_headers, admin_user = await register_and_login(
        prefix="no-remove-admin",
        account_type="enterprise",
        org_name="保护管理员公司",
    )
    resp = await client.delete(
        f"/api/v1/organization/members/{admin_user['id']}",
        headers=admin_headers,
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "不能移除团队所有者"


async def test_org_settings_includes_member_count(
    client: AsyncClient,
    register_and_login,
) -> None:
    admin_headers, admin_user = await register_and_login(
        prefix="member-count",
        account_type="enterprise",
        org_name="成员数公司",
    )
    await _create_org_member_and_login(client, org_id=admin_user["org_id"])

    resp = await client.get("/api/v1/organization/settings", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["member_count"] == 2
