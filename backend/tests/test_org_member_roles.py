"""Wave 5.4：角色管理测试（promote / demote / transfer ownership / 边界拒绝）。"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.fixtures.org_members import (
    _create_org_member_and_login,
    _register_personal_user,
    _promote_member_to_admin_in_db,
)

pytestmark = pytest.mark.asyncio


async def test_owner_promotes_member_to_admin(
    client: AsyncClient,
    register_and_login,
) -> None:
    owner_headers, owner_user = await register_and_login(
        prefix="role-promote",
        account_type="enterprise",
        org_name="提拔管理员公司",
    )
    _member_headers, member_user = await _create_org_member_and_login(
        client,
        org_id=owner_user["org_id"],
    )

    resp = await client.patch(
        f"/api/v1/organization/members/{member_user['id']}",
        headers=owner_headers,
        json={"role": "admin"},
    )
    assert resp.status_code == 200
    assert resp.json()["role"] == "admin"
    assert resp.json()["is_owner"] is False

    member_login = await client.post(
        "/api/v1/auth/login",
        json={"identifier": member_user["email"], "password": "password123"},
    )
    assert member_login.status_code == 200
    assert member_login.json()["user"]["org_role"] == "admin"


async def test_non_owner_admin_cannot_patch_role(
    client: AsyncClient,
    register_and_login,
) -> None:
    owner_headers, owner_user = await register_and_login(
        prefix="role-deny-admin",
        account_type="enterprise",
        org_name="副管无权改角色公司",
    )
    member_headers, member_user = await _create_org_member_and_login(
        client,
        org_id=owner_user["org_id"],
    )
    await _promote_member_to_admin_in_db(
        org_id=owner_user["org_id"],
        user_id=member_user["id"],
    )

    another = await _register_personal_user(client, prefix="role-target")
    add_resp = await client.post(
        "/api/v1/organization/members",
        headers=owner_headers,
        json={"email": another["email"]},
    )
    target_id = add_resp.json()["user_id"]

    resp = await client.patch(
        f"/api/v1/organization/members/{target_id}",
        headers=member_headers,
        json={"role": "admin"},
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "仅团队所有者可执行此操作"


async def test_owner_demotes_admin_to_member(
    client: AsyncClient,
    register_and_login,
) -> None:
    owner_headers, owner_user = await register_and_login(
        prefix="role-demote",
        account_type="enterprise",
        org_name="降级管理员公司",
    )
    _member_headers, member_user = await _create_org_member_and_login(
        client,
        org_id=owner_user["org_id"],
    )
    await _promote_member_to_admin_in_db(
        org_id=owner_user["org_id"],
        user_id=member_user["id"],
    )

    resp = await client.patch(
        f"/api/v1/organization/members/{member_user['id']}",
        headers=owner_headers,
        json={"role": "member"},
    )
    assert resp.status_code == 200
    assert resp.json()["role"] == "member"

    member_login = await client.post(
        "/api/v1/auth/login",
        json={"identifier": member_user["email"], "password": "password123"},
    )
    assert member_login.status_code == 200
    assert member_login.json()["user"]["org_role"] == "member"


async def test_member_cannot_patch_role(
    client: AsyncClient,
    register_and_login,
) -> None:
    owner_headers, owner_user = await register_and_login(
        prefix="role-deny-member",
        account_type="enterprise",
        org_name="成员无权改角色公司",
    )
    member_headers, member_user = await _create_org_member_and_login(
        client,
        org_id=owner_user["org_id"],
    )

    resp = await client.patch(
        f"/api/v1/organization/members/{owner_user['id']}",
        headers=member_headers,
        json={"role": "member"},
    )
    assert resp.status_code == 403


async def test_owner_cannot_patch_self_role(
    client: AsyncClient,
    register_and_login,
) -> None:
    owner_headers, owner_user = await register_and_login(
        prefix="role-self",
        account_type="enterprise",
        org_name="不能改自己角色公司",
    )

    resp = await client.patch(
        f"/api/v1/organization/members/{owner_user['id']}",
        headers=owner_headers,
        json={"role": "member"},
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "不能修改自己的角色"


async def test_non_owner_admin_cannot_patch_owner_role(
    client: AsyncClient,
    register_and_login,
) -> None:
    """R2：非 Owner 的 Admin 不能 PATCH 团队 Owner 的角色（路由 require_owner）。"""
    owner_headers, owner_user = await register_and_login(
        prefix="role-deny-patch-owner",
        account_type="enterprise",
        org_name="不能改 Owner 角色公司",
    )
    admin_headers, admin_user = await _create_org_member_and_login(
        client,
        org_id=owner_user["org_id"],
    )
    await _promote_member_to_admin_in_db(
        org_id=owner_user["org_id"],
        user_id=admin_user["id"],
    )

    resp = await client.patch(
        f"/api/v1/organization/members/{owner_user['id']}",
        headers=admin_headers,
        json={"role": "member"},
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "仅团队所有者可执行此操作"


async def test_owner_cannot_patch_new_owner_role_after_transfer(
    client: AsyncClient,
    register_and_login,
) -> None:
    """R2：转让后原 Owner 降为 Admin，不能再 PATCH 角色（require_owner）。"""
    owner_headers, owner_user = await register_and_login(
        prefix="role-deny-post-xfer",
        account_type="enterprise",
        org_name="转让后不能改角色公司",
    )
    _member_headers, member_user = await _create_org_member_and_login(
        client,
        org_id=owner_user["org_id"],
    )

    transfer = await client.post(
        "/api/v1/organization/transfer-ownership",
        headers=owner_headers,
        json={"target_user_id": member_user["id"]},
    )
    assert transfer.status_code == 200

    former_owner_login = await client.post(
        "/api/v1/auth/login",
        json={"identifier": owner_user["email"], "password": "password123"},
    )
    former_owner_headers = {
        "Authorization": f"Bearer {former_owner_login.json()['access_token']}"
    }

    resp = await client.patch(
        f"/api/v1/organization/members/{member_user['id']}",
        headers=former_owner_headers,
        json={"role": "member"},
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "仅团队所有者可执行此操作"


async def test_patch_role_duplicate_rejected(
    client: AsyncClient,
    register_and_login,
) -> None:
    owner_headers, owner_user = await register_and_login(
        prefix="role-dup",
        account_type="enterprise",
        org_name="重复改角色公司",
    )
    _member_headers, member_user = await _create_org_member_and_login(
        client,
        org_id=owner_user["org_id"],
    )

    resp = await client.patch(
        f"/api/v1/organization/members/{member_user['id']}",
        headers=owner_headers,
        json={"role": "member"},
    )
    assert resp.status_code == 409
    assert resp.json()["detail"] == "该用户已是该角色"


async def test_owner_transfers_ownership_to_member(
    client: AsyncClient,
    register_and_login,
) -> None:
    owner_headers, owner_user = await register_and_login(
        prefix="xfer-member",
        account_type="enterprise",
        org_name="转让给成员公司",
    )
    _member_headers, member_user = await _create_org_member_and_login(
        client,
        org_id=owner_user["org_id"],
    )

    resp = await client.post(
        "/api/v1/organization/transfer-ownership",
        headers=owner_headers,
        json={"target_user_id": member_user["id"]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["previous_owner"]["user_id"] == owner_user["id"]
    assert body["previous_owner"]["is_owner"] is False
    assert body["previous_owner"]["role"] == "admin"
    assert body["new_owner"]["user_id"] == member_user["id"]
    assert body["new_owner"]["is_owner"] is True
    assert body["new_owner"]["role"] == "admin"

    owner_me = await client.get("/api/v1/auth/me", headers=owner_headers)
    assert owner_me.status_code == 200
    assert owner_me.json()["is_owner"] is False
    assert owner_me.json()["org_role"] == "admin"

    member_login = await client.post(
        "/api/v1/auth/login",
        json={"identifier": member_user["email"], "password": "password123"},
    )
    assert member_login.status_code == 200
    assert member_login.json()["user"]["is_owner"] is True
    assert member_login.json()["user"]["org_role"] == "admin"


async def test_owner_transfers_ownership_to_admin(
    client: AsyncClient,
    register_and_login,
) -> None:
    owner_headers, owner_user = await register_and_login(
        prefix="xfer-admin",
        account_type="enterprise",
        org_name="转让给副管公司",
    )
    member_headers, member_user = await _create_org_member_and_login(
        client,
        org_id=owner_user["org_id"],
    )
    await _promote_member_to_admin_in_db(
        org_id=owner_user["org_id"],
        user_id=member_user["id"],
    )

    resp = await client.post(
        "/api/v1/organization/transfer-ownership",
        headers=owner_headers,
        json={"target_user_id": member_user["id"]},
    )
    assert resp.status_code == 200
    assert resp.json()["new_owner"]["is_owner"] is True


async def test_non_owner_admin_cannot_transfer_ownership(
    client: AsyncClient,
    register_and_login,
) -> None:
    owner_headers, owner_user = await register_and_login(
        prefix="xfer-deny-admin",
        account_type="enterprise",
        org_name="副管不能转让公司",
    )
    member_headers, member_user = await _create_org_member_and_login(
        client,
        org_id=owner_user["org_id"],
    )
    await _promote_member_to_admin_in_db(
        org_id=owner_user["org_id"],
        user_id=member_user["id"],
    )

    another = await _register_personal_user(client, prefix="xfer-target")
    add_resp = await client.post(
        "/api/v1/organization/members",
        headers=owner_headers,
        json={"email": another["email"]},
    )
    target_id = add_resp.json()["user_id"]

    resp = await client.post(
        "/api/v1/organization/transfer-ownership",
        headers=member_headers,
        json={"target_user_id": target_id},
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "仅团队所有者可执行此操作"


async def test_owner_cannot_transfer_to_self(
    client: AsyncClient,
    register_and_login,
) -> None:
    owner_headers, owner_user = await register_and_login(
        prefix="xfer-self",
        account_type="enterprise",
        org_name="不能转给自己公司",
    )

    resp = await client.post(
        "/api/v1/organization/transfer-ownership",
        headers=owner_headers,
        json={"target_user_id": owner_user["id"]},
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "不能将所有权转让给自己"


async def test_owner_cannot_transfer_to_non_member(
    client: AsyncClient,
    register_and_login,
) -> None:
    owner_headers, _owner_user = await register_and_login(
        prefix="xfer-missing",
        account_type="enterprise",
        org_name="转给非成员公司",
    )
    outsider = await _register_personal_user(client, prefix="xfer-outsider")

    resp = await client.post(
        "/api/v1/organization/transfer-ownership",
        headers=owner_headers,
        json={"target_user_id": outsider["id"]},
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "该用户不是团队成员"
