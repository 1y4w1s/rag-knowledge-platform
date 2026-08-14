"""P1-P1：退团必须清理 OrgUnitMember，重加入不得恢复部门管理员身份。"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.core.database import SessionLocal
from app.models.enums import OrgRole, UnitRole
from app.models.org_unit import OrgUnit
from app.models.org_unit_member import OrgUnitMember
from app.models.organization_member import OrganizationMember
from tests.conftest import unique_email, unique_username


async def _register_org_admin(
    client: AsyncClient,
    *,
    prefix: str,
    org_name: str,
) -> tuple[dict[str, str], dict]:
    email = unique_email(prefix)
    username = unique_username(prefix)
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "username": username,
            "password": "Test123!@",
            "account_type": "enterprise",
            "org_name": org_name,
        },
    )
    assert reg.status_code == 201, reg.text
    login = await client.post(
        "/api/v1/auth/login",
        json={"identifier": email, "password": "Test123!@"},
    )
    assert login.status_code == 200
    data = login.json()
    return {"Authorization": f"Bearer {data['access_token']}"}, data["user"]


async def _create_invite(client: AsyncClient, headers: dict[str, str]) -> str:
    resp = await client.post("/api/v1/organization/invites", headers=headers, json={})
    assert resp.status_code == 201, resp.text
    return resp.json()["code"]


async def _register_member(
    client: AsyncClient,
    *,
    prefix: str,
    invite_code: str,
) -> tuple[dict[str, str], dict]:
    email = unique_email(prefix)
    username = unique_username(prefix)
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "username": username,
            "password": "Test123!@",
            "account_type": "enterprise",
            "invite_code": invite_code,
        },
    )
    assert reg.status_code == 201, reg.text
    login = await client.post(
        "/api/v1/auth/login",
        json={"identifier": email, "password": "Test123!@"},
    )
    assert login.status_code == 200
    data = login.json()
    return {"Authorization": f"Bearer {data['access_token']}"}, data["user"]


async def _count_unit_memberships(org_id: uuid.UUID, user_id: uuid.UUID) -> int:
    async with SessionLocal() as db:
        count = await db.scalar(
            select(func.count())
            .select_from(OrgUnitMember)
            .join(OrgUnit, OrgUnit.id == OrgUnitMember.org_unit_id)
            .where(OrgUnit.org_id == org_id, OrgUnitMember.user_id == user_id)
        )
        return int(count or 0)


async def _org_membership_role(org_id: uuid.UUID, user_id: uuid.UUID) -> OrgRole | None:
    async with SessionLocal() as db:
        return await db.scalar(
            select(OrganizationMember.role).where(
                OrganizationMember.org_id == org_id,
                OrganizationMember.user_id == user_id,
            )
        )


@pytest.mark.asyncio
async def test_leave_team_clears_unit_admin_and_rejoin_does_not_restore(
    client: AsyncClient,
) -> None:
    """退团清空部门成员行；重新加入后仅恢复组织成员，不恢复部门管理员。"""
    admin_headers, admin = await _register_org_admin(
        client,
        prefix="leave-unit-admin",
        org_name="退团清权测试团队",
    )
    org_id = uuid.UUID(admin["org_id"])
    root_id = (await client.get("/api/v1/org-units", headers=admin_headers)).json()["items"][0]["id"]
    unit_resp = await client.post(
        "/api/v1/org-units",
        headers=admin_headers,
        json={"name": "研发中心", "parent_id": root_id},
    )
    assert unit_resp.status_code == 201, unit_resp.text
    unit_id = unit_resp.json()["id"]

    code = await _create_invite(client, admin_headers)
    member_headers, member = await _register_member(
        client,
        prefix="leave-unit-member",
        invite_code=code,
    )

    appoint = await client.post(
        f"/api/v1/org-units/{unit_id}/members",
        headers=admin_headers,
        json={
            "user_id": member["id"],
            "role": UnitRole.unit_admin.value,
            "is_primary": True,
        },
    )
    assert appoint.status_code == 201, appoint.text
    assert await _count_unit_memberships(org_id, uuid.UUID(member["id"])) == 1

    leave = await client.post(
        "/api/v1/settings/account/leave-team",
        headers=member_headers,
    )
    assert leave.status_code == 200, leave.text
    assert leave.json()["account"]["org_id"] is None
    assert await _count_unit_memberships(org_id, uuid.UUID(member["id"])) == 0
    assert await _org_membership_role(org_id, uuid.UUID(member["id"])) is None

    new_code = await _create_invite(client, admin_headers)
    rejoin = await client.post(
        "/api/v1/settings/account/join-team",
        headers=member_headers,
        json={"invite_code": new_code},
    )
    assert rejoin.status_code == 200, rejoin.text
    assert rejoin.json()["account"]["org_role"] == OrgRole.member.value
    assert await _count_unit_memberships(org_id, uuid.UUID(member["id"])) == 0
    assert await _org_membership_role(org_id, uuid.UUID(member["id"])) == OrgRole.member


@pytest.mark.asyncio
async def test_admin_remove_member_clears_unit_admin(
    client: AsyncClient,
) -> None:
    """对照：管理员移除成员路径本就清理部门成员，行为保持一致。"""
    admin_headers, admin = await _register_org_admin(
        client,
        prefix="remove-unit-admin",
        org_name="移除清权测试团队",
    )
    org_id = uuid.UUID(admin["org_id"])
    root_id = (await client.get("/api/v1/org-units", headers=admin_headers)).json()["items"][0]["id"]
    unit_resp = await client.post(
        "/api/v1/org-units",
        headers=admin_headers,
        json={"name": "财务部", "parent_id": root_id},
    )
    assert unit_resp.status_code == 201, unit_resp.text
    unit_id = unit_resp.json()["id"]

    code = await _create_invite(client, admin_headers)
    _member_headers, member = await _register_member(
        client,
        prefix="remove-unit-member",
        invite_code=code,
    )
    appoint = await client.post(
        f"/api/v1/org-units/{unit_id}/members",
        headers=admin_headers,
        json={
            "user_id": member["id"],
            "role": UnitRole.unit_admin.value,
            "is_primary": True,
        },
    )
    assert appoint.status_code == 201, appoint.text
    assert await _count_unit_memberships(org_id, uuid.UUID(member["id"])) == 1

    remove = await client.delete(
        f"/api/v1/organization/members/{member['id']}",
        headers=admin_headers,
    )
    assert remove.status_code == 204, remove.text
    assert await _count_unit_memberships(org_id, uuid.UUID(member["id"])) == 0
