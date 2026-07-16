"""ORG-2.2：org_unit_members API — PRD ORG-1-3 §3.4 S3/S4/S7 + E5/E6。"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import SessionLocal
from app.models.enums import AccountType, OrgRole, UnitRole
from app.models.org_unit import OrgUnit
from app.models.org_unit_member import OrgUnitMember
from app.models.organization_member import OrganizationMember
from app.models.user import User
from app.services.auth.password import hash_password
from tests.conftest import unique_email, unique_username


async def _register_org_admin(
    client: AsyncClient,
    *,
    prefix: str = "org-admin",
    org_name: str = "睿阁科技",
) -> tuple[dict[str, str], dict]:
    email = unique_email(prefix)
    username = unique_username(prefix)
    password = "password123"
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "username": username,
            "password": password,
            "account_type": "enterprise",
            "org_name": org_name,
        },
    )
    assert reg.status_code == 201
    login = await client.post(
        "/api/v1/auth/login",
        json={"identifier": email, "password": password},
    )
    assert login.status_code == 200
    data = login.json()
    return {"Authorization": f"Bearer {data['access_token']}"}, data["user"]


async def _create_unit(
    client: AsyncClient,
    headers: dict[str, str],
    *,
    name: str,
    parent_id: str,
) -> dict:
    resp = await client.post(
        "/api/v1/org-units",
        headers=headers,
        json={"name": name, "parent_id": parent_id},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _create_org_member(
    db: AsyncSession,
    *,
    org_id: uuid.UUID,
    prefix: str = "member",
) -> User:
    user = User(
        id=uuid.uuid4(),
        email=unique_email(prefix),
        username=unique_username(prefix),
        password_hash=hash_password("password123"),
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


async def _count_user_unit_memberships(
    db: AsyncSession,
    org_id: uuid.UUID,
    user_id: uuid.UUID,
) -> int:
    count = await db.scalar(
        select(func.count())
        .select_from(OrgUnitMember)
        .join(OrgUnit, OrgUnit.id == OrgUnitMember.org_unit_id)
        .where(OrgUnit.org_id == org_id, OrgUnitMember.user_id == user_id)
    )
    return int(count or 0)


async def _count_user_primary_units(
    db: AsyncSession,
    org_id: uuid.UUID,
    user_id: uuid.UUID,
) -> int:
    count = await db.scalar(
        select(func.count())
        .select_from(OrgUnitMember)
        .join(OrgUnit, OrgUnit.id == OrgUnitMember.org_unit_id)
        .where(
            OrgUnit.org_id == org_id,
            OrgUnitMember.user_id == user_id,
            OrgUnitMember.is_primary.is_(True),
        )
    )
    return int(count or 0)


@pytest.mark.asyncio
async def test_unit_member_s3_add_from_roster_with_primary(client: AsyncClient) -> None:
    """S3：从花名册添加李四 · 角色部门 Member · 主部门。"""
    headers, admin_user = await _register_org_admin(client, prefix="s3-member-admin")
    root_id = (
        await client.get("/api/v1/org-units", headers=headers)
    ).json()["items"][0]["id"]
    rd = await _create_unit(client, headers, name="研发中心", parent_id=root_id)

    async with SessionLocal() as db:
        member = await _create_org_member(
            db, org_id=uuid.UUID(admin_user["org_id"]), prefix="lisi"
        )
        member_id = str(member.id)

    add_resp = await client.post(
        f"/api/v1/org-units/{rd['id']}/members",
        headers=headers,
        json={
            "user_id": member_id,
            "role": "unit_member",
            "is_primary": True,
        },
    )
    assert add_resp.status_code == 201, add_resp.text
    data = add_resp.json()
    assert data["user_id"] == member_id
    assert data["role"] == "unit_member"
    assert data["is_primary"] is True

    list_resp = await client.get(
        f"/api/v1/org-units/{rd['id']}/members",
        headers=headers,
    )
    assert list_resp.status_code == 200
    assert len(list_resp.json()["items"]) == 1


@pytest.mark.asyncio
async def test_unit_member_s4_appoint_unit_admin(client: AsyncClient) -> None:
    """S4：任命张三为「研发中心」unit_admin。"""
    headers, admin_user = await _register_org_admin(client, prefix="s4-member-admin")
    root_id = (
        await client.get("/api/v1/org-units", headers=headers)
    ).json()["items"][0]["id"]
    rd = await _create_unit(client, headers, name="研发中心", parent_id=root_id)

    async with SessionLocal() as db:
        user = await _create_org_member(
            db, org_id=uuid.UUID(admin_user["org_id"]), prefix="zhangsan"
        )
        user_id = str(user.id)

    await client.post(
        f"/api/v1/org-units/{rd['id']}/members",
        headers=headers,
        json={"user_id": user_id, "role": "unit_member", "is_primary": True},
    )

    patch_resp = await client.patch(
        f"/api/v1/org-units/{rd['id']}/members/{user_id}",
        headers=headers,
        json={"role": "unit_admin"},
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["role"] == "unit_admin"


@pytest.mark.asyncio
async def test_unit_member_s7_org_remove_cascades_unit_memberships(
    client: AsyncClient,
) -> None:
    """S7：成员管理页移除公司身份 — 其所有 org_unit_members 级联清除。"""
    headers, admin_user = await _register_org_admin(client, prefix="s7-member-admin")
    root_id = (
        await client.get("/api/v1/org-units", headers=headers)
    ).json()["items"][0]["id"]
    rd = await _create_unit(client, headers, name="研发中心", parent_id=root_id)

    async with SessionLocal() as db:
        member = await _create_org_member(
            db, org_id=uuid.UUID(admin_user["org_id"]), prefix="s7-target"
        )
        member_id = str(member.id)

    await client.post(
        f"/api/v1/org-units/{rd['id']}/members",
        headers=headers,
        json={"user_id": member_id, "role": "unit_member", "is_primary": True},
    )

    delete_resp = await client.delete(
        f"/api/v1/organization/members/{member_id}",
        headers=headers,
    )
    assert delete_resp.status_code == 204

    async with SessionLocal() as db:
        remaining = await _count_user_unit_memberships(
            db,
            uuid.UUID(admin_user["org_id"]),
            uuid.UUID(member_id),
        )
        assert remaining == 0


@pytest.mark.asyncio
async def test_unit_member_e5_primary_on_unjoined_unit(client: AsyncClient) -> None:
    """E5：把用户主部门设为未加入的节点 — 400。"""
    headers, admin_user = await _register_org_admin(client, prefix="e5-member-admin")
    root_id = (
        await client.get("/api/v1/org-units", headers=headers)
    ).json()["items"][0]["id"]
    rd = await _create_unit(client, headers, name="研发中心", parent_id=root_id)
    mkt = await _create_unit(client, headers, name="市场部", parent_id=root_id)

    async with SessionLocal() as db:
        member = await _create_org_member(
            db, org_id=uuid.UUID(admin_user["org_id"]), prefix="e5-user"
        )
        member_id = str(member.id)

    await client.post(
        f"/api/v1/org-units/{rd['id']}/members",
        headers=headers,
        json={"user_id": member_id, "role": "unit_member", "is_primary": True},
    )

    patch_resp = await client.patch(
        f"/api/v1/org-units/{mkt['id']}/members/{member_id}",
        headers=headers,
        json={"is_primary": True},
    )
    assert patch_resp.status_code == 400
    assert patch_resp.json()["detail"] == "用户未加入该部门"


@pytest.mark.asyncio
async def test_unit_member_e6_unassigned_has_no_unit_memberships(
    client: AsyncClient,
) -> None:
    """E6：用户零部门（未分配）— 无 org_unit_members。"""
    headers, admin_user = await _register_org_admin(client, prefix="e6-member-admin")
    root_id = (
        await client.get("/api/v1/org-units", headers=headers)
    ).json()["items"][0]["id"]
    rd = await _create_unit(client, headers, name="研发中心", parent_id=root_id)

    async with SessionLocal() as db:
        member = await _create_org_member(
            db, org_id=uuid.UUID(admin_user["org_id"]), prefix="e6-unassigned"
        )
        member_id = str(member.id)

    async with SessionLocal() as db:
        assert (
            await _count_user_unit_memberships(
                db,
                uuid.UUID(admin_user["org_id"]),
                uuid.UUID(member_id),
            )
            == 0
        )

    await client.post(
        f"/api/v1/org-units/{rd['id']}/members",
        headers=headers,
        json={"user_id": member_id, "role": "unit_member", "is_primary": True},
    )

    delete_resp = await client.delete(
        f"/api/v1/org-units/{rd['id']}/members/{member_id}",
        headers=headers,
    )
    assert delete_resp.status_code == 204

    async with SessionLocal() as db:
        assert (
            await _count_user_unit_memberships(
                db,
                uuid.UUID(admin_user["org_id"]),
                uuid.UUID(member_id),
            )
            == 0
        )

    login = await client.post(
        "/api/v1/auth/login",
        json={"identifier": member.email, "password": "password123"},
    )
    assert login.status_code == 200
    login_user = login.json()["user"]
    assert login_user["unit_ids"] == []
    assert login_user["primary_unit_id"] is None

    member_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    me = await client.get("/api/v1/auth/me", headers=member_headers)
    assert me.status_code == 200
    me_data = me.json()
    assert me_data["unit_ids"] == []
    assert me_data["primary_unit_id"] is None


@pytest.mark.asyncio
async def test_unit_member_primary_uniqueness(client: AsyncClient) -> None:
    """主部门唯一：全公司恰好一个 is_primary=true。"""
    headers, admin_user = await _register_org_admin(client, prefix="primary-admin")
    root_id = (
        await client.get("/api/v1/org-units", headers=headers)
    ).json()["items"][0]["id"]
    rd = await _create_unit(client, headers, name="研发中心", parent_id=root_id)
    mkt = await _create_unit(client, headers, name="市场部", parent_id=root_id)

    async with SessionLocal() as db:
        member = await _create_org_member(
            db, org_id=uuid.UUID(admin_user["org_id"]), prefix="dual-unit"
        )
        member_id = str(member.id)

    await client.post(
        f"/api/v1/org-units/{rd['id']}/members",
        headers=headers,
        json={"user_id": member_id, "role": "unit_member", "is_primary": True},
    )
    await client.post(
        f"/api/v1/org-units/{mkt['id']}/members",
        headers=headers,
        json={"user_id": member_id, "role": "unit_member", "is_primary": False},
    )

    async with SessionLocal() as db:
        assert (
            await _count_user_primary_units(
                db,
                uuid.UUID(admin_user["org_id"]),
                uuid.UUID(member_id),
            )
            == 1
        )

    switch_resp = await client.patch(
        f"/api/v1/org-units/{mkt['id']}/members/{member_id}",
        headers=headers,
        json={"is_primary": True},
    )
    assert switch_resp.status_code == 200
    assert switch_resp.json()["is_primary"] is True

    async with SessionLocal() as db:
        assert (
            await _count_user_primary_units(
                db,
                uuid.UUID(admin_user["org_id"]),
                uuid.UUID(member_id),
            )
            == 1
        )
        rows = (
            await db.scalars(
                select(OrgUnitMember)
                .join(OrgUnit, OrgUnit.id == OrgUnitMember.org_unit_id)
                .where(
                    OrgUnit.org_id == uuid.UUID(admin_user["org_id"]),
                    OrgUnitMember.user_id == uuid.UUID(member_id),
                    OrgUnitMember.is_primary.is_(True),
                )
            )
        ).all()
        assert len(rows) == 1
        assert rows[0].org_unit_id == uuid.UUID(mkt["id"])


@pytest.mark.asyncio
async def test_unit_member_remove_promotes_new_primary(client: AsyncClient) -> None:
    """移出主部门且仍有其它部门 — 自动改主。"""
    headers, admin_user = await _register_org_admin(client, prefix="remove-primary-admin")
    root_id = (
        await client.get("/api/v1/org-units", headers=headers)
    ).json()["items"][0]["id"]
    rd = await _create_unit(client, headers, name="研发中心", parent_id=root_id)
    mkt = await _create_unit(client, headers, name="市场部", parent_id=root_id)

    async with SessionLocal() as db:
        member = await _create_org_member(
            db, org_id=uuid.UUID(admin_user["org_id"]), prefix="remove-primary"
        )
        member_id = str(member.id)

    await client.post(
        f"/api/v1/org-units/{rd['id']}/members",
        headers=headers,
        json={"user_id": member_id, "role": "unit_member", "is_primary": True},
    )
    await client.post(
        f"/api/v1/org-units/{mkt['id']}/members",
        headers=headers,
        json={"user_id": member_id, "role": "unit_member", "is_primary": False},
    )

    delete_resp = await client.delete(
        f"/api/v1/org-units/{rd['id']}/members/{member_id}",
        headers=headers,
    )
    assert delete_resp.status_code == 204

    async with SessionLocal() as db:
        assert (
            await _count_user_primary_units(
                db,
                uuid.UUID(admin_user["org_id"]),
                uuid.UUID(member_id),
            )
            == 1
        )
        primary = await db.scalar(
            select(OrgUnitMember)
            .join(OrgUnit, OrgUnit.id == OrgUnitMember.org_unit_id)
            .where(
                OrgUnit.org_id == uuid.UUID(admin_user["org_id"]),
                OrgUnitMember.user_id == uuid.UUID(member_id),
                OrgUnitMember.is_primary.is_(True),
            )
        )
        assert primary is not None
        assert primary.org_unit_id == uuid.UUID(mkt["id"])
