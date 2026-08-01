"""NW-24 I-1：部门 Admin 本节点成员鉴权 + 最后一名闸。"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import SessionLocal
from app.models.enums import AccountType, OrgRole, UnitRole
from app.models.organization_member import OrganizationMember
from app.models.user import User
from app.services.auth.password import hash_password
from app.services.org.units import add_unit_member
from tests.conftest import unique_email, unique_username
from tests.fixtures.org_isolation import OrgIsolationFixture, _login_user

PASSWORD = "Test123!@"
LAST_ADMIN_MSG = "部门至少保留一名部门管理员"


async def _create_roster_member(
    db: AsyncSession,
    *,
    org_id: uuid.UUID,
    prefix: str = "roster",
) -> User:
    user = User(
        id=uuid.uuid4(),
        email=unique_email(prefix),
        username=unique_username(prefix),
        password_hash=hash_password(PASSWORD),
        account_type=AccountType.enterprise,
    )
    db.add(user)
    db.add(
        OrganizationMember(
            id=uuid.uuid4(),
            org_id=org_id,
            user_id=user.id,
            role=OrgRole.member,
        )
    )
    await db.commit()
    return user


@pytest.mark.asyncio
async def test_unit_admin_can_manage_own_node_members(
    client: AsyncClient,
    org_iso: OrgIsolationFixture,
) -> None:
    """本节点：list / add / patch / delete ✅。"""
    headers, _ = await _login_user(client, org_iso.rd_admin.email, PASSWORD)

    async with SessionLocal() as db:
        target = await _create_roster_member(
            db, org_id=org_iso.org_id, prefix="nw24-own"
        )
        target_id = str(target.id)

    list_resp = await client.get(
        f"/api/v1/org-units/{org_iso.rd_id}/members",
        headers=headers,
    )
    assert list_resp.status_code == 200, list_resp.text
    assert any(
        item["user_id"] == str(org_iso.rd_admin.id)
        for item in list_resp.json()["items"]
    )

    add_resp = await client.post(
        f"/api/v1/org-units/{org_iso.rd_id}/members",
        headers=headers,
        json={
            "user_id": target_id,
            "role": "unit_member",
            "is_primary": True,
        },
    )
    assert add_resp.status_code == 201, add_resp.text
    assert add_resp.json()["role"] == "unit_member"

    patch_resp = await client.patch(
        f"/api/v1/org-units/{org_iso.rd_id}/members/{target_id}",
        headers=headers,
        json={"role": "unit_admin"},
    )
    assert patch_resp.status_code == 200, patch_resp.text
    assert patch_resp.json()["role"] == "unit_admin"

    # 降回 member：此时至少还有 rd_admin，允许
    demote = await client.patch(
        f"/api/v1/org-units/{org_iso.rd_id}/members/{target_id}",
        headers=headers,
        json={"role": "unit_member"},
    )
    assert demote.status_code == 200, demote.text

    delete_resp = await client.delete(
        f"/api/v1/org-units/{org_iso.rd_id}/members/{target_id}",
        headers=headers,
    )
    assert delete_resp.status_code == 204, delete_resp.text


@pytest.mark.asyncio
async def test_unit_admin_sibling_and_child_members_forbidden(
    client: AsyncClient,
    org_iso: OrgIsolationFixture,
) -> None:
    """兄弟节点 / 子节点 members → 403（精确本节点，非子树）。"""
    headers, _ = await _login_user(client, org_iso.rd_admin.email, PASSWORD)

    sibling = await client.get(
        f"/api/v1/org-units/{org_iso.mkt_id}/members",
        headers=headers,
    )
    assert sibling.status_code == 403

    child = await client.get(
        f"/api/v1/org-units/{org_iso.rd_child_id}/members",
        headers=headers,
    )
    assert child.status_code == 403

    child_post = await client.post(
        f"/api/v1/org-units/{org_iso.rd_child_id}/members",
        headers=headers,
        json={
            "user_id": str(org_iso.rd_member.id),
            "role": "unit_member",
            "is_primary": False,
        },
    )
    assert child_post.status_code == 403


@pytest.mark.asyncio
async def test_unit_admin_tree_crud_still_forbidden(
    client: AsyncClient,
    org_iso: OrgIsolationFixture,
) -> None:
    """树 CRUD 仍仅公司 Admin — unit_admin 403。"""
    headers, _ = await _login_user(client, org_iso.rd_admin.email, PASSWORD)

    create = await client.post(
        "/api/v1/org-units",
        headers=headers,
        json={"name": "不应创建", "parent_id": str(org_iso.rd_id)},
    )
    assert create.status_code == 403

    rename = await client.patch(
        f"/api/v1/org-units/{org_iso.rd_id}",
        headers=headers,
        json={"name": "改名失败"},
    )
    assert rename.status_code == 403

    delete = await client.delete(
        f"/api/v1/org-units/{org_iso.rd_child_id}",
        headers=headers,
    )
    assert delete.status_code == 403


@pytest.mark.asyncio
async def test_last_unit_admin_gate_and_company_admin_override(
    client: AsyncClient,
    org_iso: OrgIsolationFixture,
) -> None:
    """最后一名 unit_admin：自降/自移出 → 400；公司 Admin 可强制。"""
    ua_headers, _ = await _login_user(client, org_iso.rd_admin.email, PASSWORD)
    owner_headers, _ = await _login_user(client, org_iso.owner.email, PASSWORD)
    admin_id = str(org_iso.rd_admin.id)

    demote_self = await client.patch(
        f"/api/v1/org-units/{org_iso.rd_id}/members/{admin_id}",
        headers=ua_headers,
        json={"role": "unit_member"},
    )
    assert demote_self.status_code == 400
    assert demote_self.json()["detail"] == LAST_ADMIN_MSG

    remove_self = await client.delete(
        f"/api/v1/org-units/{org_iso.rd_id}/members/{admin_id}",
        headers=ua_headers,
    )
    assert remove_self.status_code == 400
    assert remove_self.json()["detail"] == LAST_ADMIN_MSG

    force_demote = await client.patch(
        f"/api/v1/org-units/{org_iso.rd_id}/members/{admin_id}",
        headers=owner_headers,
        json={"role": "unit_member"},
    )
    assert force_demote.status_code == 200, force_demote.text
    assert force_demote.json()["role"] == "unit_member"


@pytest.mark.asyncio
async def test_company_admin_any_node_and_member_forbidden(
    client: AsyncClient,
    org_iso: OrgIsolationFixture,
) -> None:
    """公司 Admin 任意节点 ✅；纯部门 Member 403。"""
    owner_headers, _ = await _login_user(client, org_iso.owner.email, PASSWORD)
    member_headers, _ = await _login_user(client, org_iso.rd_member.email, PASSWORD)

    for unit_id in (org_iso.rd_id, org_iso.mkt_id, org_iso.rd_child_id):
        resp = await client.get(
            f"/api/v1/org-units/{unit_id}/members",
            headers=owner_headers,
        )
        assert resp.status_code == 200, resp.text

    member_list = await client.get(
        f"/api/v1/org-units/{org_iso.rd_id}/members",
        headers=member_headers,
    )
    assert member_list.status_code == 403

    member_post = await client.post(
        f"/api/v1/org-units/{org_iso.rd_id}/members",
        headers=member_headers,
        json={
            "user_id": str(org_iso.mkt_member.id),
            "role": "unit_member",
            "is_primary": False,
        },
    )
    assert member_post.status_code == 403


@pytest.mark.asyncio
async def test_second_unit_admin_can_demote_when_not_last(
    client: AsyncClient,
    org_iso: OrgIsolationFixture,
) -> None:
    """非最后一名：可降级另一名 unit_admin。"""
    owner_headers, _ = await _login_user(client, org_iso.owner.email, PASSWORD)
    ua_headers, _ = await _login_user(client, org_iso.rd_admin.email, PASSWORD)

    async with SessionLocal() as db:
        second = await _create_roster_member(
            db, org_id=org_iso.org_id, prefix="nw24-2nd-admin"
        )
        await add_unit_member(
            db,
            org_unit_id=org_iso.rd_id,
            user_id=second.id,
            role=UnitRole.unit_admin,
            is_primary=False,
        )
        await db.commit()
        second_id = str(second.id)

    demote = await client.patch(
        f"/api/v1/org-units/{org_iso.rd_id}/members/{second_id}",
        headers=ua_headers,
        json={"role": "unit_member"},
    )
    assert demote.status_code == 200, demote.text
    assert demote.json()["role"] == "unit_member"

    await client.delete(
        f"/api/v1/org-units/{org_iso.rd_id}/members/{second_id}",
        headers=owner_headers,
    )
