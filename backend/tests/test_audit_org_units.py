"""EW-A3：组织单元审计事件测试（create / rename / delete / member_add / member_remove / member_update）。"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

from tests.fixtures.audit_events import (
    _count_audit_logs,
    _create_org_roster_member,
    _latest_audit_log,
    _register_org_admin,
)

pytestmark = pytest.mark.asyncio


async def test_create_org_unit_writes_audit_log(client: AsyncClient) -> None:
    headers, admin_user = await _register_org_admin(client, prefix="audit-unit-create")
    root_id = (
        await client.get("/api/v1/org-units", headers=headers)
    ).json()["items"][0]["id"]

    before = await _count_audit_logs(action="org_unit.create")

    create_resp = await client.post(
        "/api/v1/org-units",
        headers=headers,
        json={"name": "研发中心", "parent_id": root_id},
    )
    assert create_resp.status_code == 201
    unit = create_resp.json()

    after = await _count_audit_logs(action="org_unit.create")
    assert after - before == 1

    latest = await _latest_audit_log(action="org_unit.create")
    assert latest is not None
    assert str(latest.actor_user_id) == admin_user["id"]
    assert latest.resource_type == "org_unit"
    assert str(latest.resource_id) == unit["id"]
    assert latest.details["name"] == "研发中心"
    assert latest.details["parent_id"] == root_id


async def test_rename_org_unit_writes_audit_log(client: AsyncClient) -> None:
    headers, admin_user = await _register_org_admin(client, prefix="audit-unit-rename")
    root_id = (
        await client.get("/api/v1/org-units", headers=headers)
    ).json()["items"][0]["id"]
    create_resp = await client.post(
        "/api/v1/org-units",
        headers=headers,
        json={"name": "市场部", "parent_id": root_id},
    )
    assert create_resp.status_code == 201
    unit_id = create_resp.json()["id"]

    before = await _count_audit_logs(action="org_unit.rename")

    patch_resp = await client.patch(
        f"/api/v1/org-units/{unit_id}",
        headers=headers,
        json={"name": "市场营销部"},
    )
    assert patch_resp.status_code == 200

    after = await _count_audit_logs(action="org_unit.rename")
    assert after - before == 1

    latest = await _latest_audit_log(action="org_unit.rename")
    assert latest is not None
    assert str(latest.actor_user_id) == admin_user["id"]
    assert str(latest.resource_id) == unit_id
    assert latest.details == {"old_name": "市场部", "new_name": "市场营销部"}


async def test_delete_org_unit_writes_audit_log(client: AsyncClient) -> None:
    headers, admin_user = await _register_org_admin(client, prefix="audit-unit-del")
    root_id = (
        await client.get("/api/v1/org-units", headers=headers)
    ).json()["items"][0]["id"]
    create_resp = await client.post(
        "/api/v1/org-units",
        headers=headers,
        json={"name": "临时组", "parent_id": root_id},
    )
    assert create_resp.status_code == 201
    unit_id = create_resp.json()["id"]

    before = await _count_audit_logs(action="org_unit.delete")

    del_resp = await client.delete(
        f"/api/v1/org-units/{unit_id}",
        headers=headers,
    )
    assert del_resp.status_code == 204

    after = await _count_audit_logs(action="org_unit.delete")
    assert after - before == 1

    latest = await _latest_audit_log(action="org_unit.delete")
    assert latest is not None
    assert str(latest.actor_user_id) == admin_user["id"]
    assert str(latest.resource_id) == unit_id
    assert latest.details["name"] == "临时组"
    assert latest.details["parent_id"] == root_id


async def test_add_unit_member_writes_audit_log(client: AsyncClient) -> None:
    headers, admin_user = await _register_org_admin(client, prefix="audit-unit-add")
    root_id = (
        await client.get("/api/v1/org-units", headers=headers)
    ).json()["items"][0]["id"]
    unit_resp = await client.post(
        "/api/v1/org-units",
        headers=headers,
        json={"name": "研发中心", "parent_id": root_id},
    )
    assert unit_resp.status_code == 201
    unit = unit_resp.json()

    member = await _create_org_roster_member(
        org_id=uuid.UUID(admin_user["org_id"]),
        prefix="audit-add-member",
    )

    before = await _count_audit_logs(action="org_unit.member_add")

    add_resp = await client.post(
        f"/api/v1/org-units/{unit['id']}/members",
        headers=headers,
        json={
            "user_id": str(member.id),
            "role": "unit_member",
            "is_primary": True,
        },
    )
    assert add_resp.status_code == 201

    after = await _count_audit_logs(action="org_unit.member_add")
    assert after - before == 1

    latest = await _latest_audit_log(action="org_unit.member_add")
    assert latest is not None
    assert str(latest.actor_user_id) == admin_user["id"]
    assert str(latest.resource_id) == str(member.id)
    assert latest.details["unit_id"] == unit["id"]
    assert latest.details["unit_name"] == "研发中心"
    assert latest.details["email"] == member.email
    assert latest.details["role"] == "unit_member"
    assert latest.details["is_primary"] is True


async def test_remove_unit_member_writes_audit_log(client: AsyncClient) -> None:
    headers, admin_user = await _register_org_admin(client, prefix="audit-unit-rm")
    root_id = (
        await client.get("/api/v1/org-units", headers=headers)
    ).json()["items"][0]["id"]
    unit_resp = await client.post(
        "/api/v1/org-units",
        headers=headers,
        json={"name": "人事部", "parent_id": root_id},
    )
    assert unit_resp.status_code == 201
    unit = unit_resp.json()

    member = await _create_org_roster_member(
        org_id=uuid.UUID(admin_user["org_id"]),
        prefix="audit-rm-member",
    )
    add_resp = await client.post(
        f"/api/v1/org-units/{unit['id']}/members",
        headers=headers,
        json={
            "user_id": str(member.id),
            "role": "unit_member",
            "is_primary": True,
        },
    )
    assert add_resp.status_code == 201

    before = await _count_audit_logs(action="org_unit.member_remove")

    del_resp = await client.delete(
        f"/api/v1/org-units/{unit['id']}/members/{member.id}",
        headers=headers,
    )
    assert del_resp.status_code == 204

    after = await _count_audit_logs(action="org_unit.member_remove")
    assert after - before == 1

    latest = await _latest_audit_log(action="org_unit.member_remove")
    assert latest is not None
    assert str(latest.actor_user_id) == admin_user["id"]
    assert str(latest.resource_id) == str(member.id)
    assert latest.details["unit_id"] == unit["id"]
    assert latest.details["email"] == member.email
    assert latest.details["was_primary"] is True


async def test_update_unit_member_writes_audit_log(client: AsyncClient) -> None:
    headers, admin_user = await _register_org_admin(client, prefix="audit-unit-upd")
    root_id = (
        await client.get("/api/v1/org-units", headers=headers)
    ).json()["items"][0]["id"]
    rd_resp = await client.post(
        "/api/v1/org-units",
        headers=headers,
        json={"name": "研发中心", "parent_id": root_id},
    )
    assert rd_resp.status_code == 201
    rd = rd_resp.json()
    hr_resp = await client.post(
        "/api/v1/org-units",
        headers=headers,
        json={"name": "人事部", "parent_id": root_id},
    )
    assert hr_resp.status_code == 201
    hr = hr_resp.json()

    member = await _create_org_roster_member(
        org_id=uuid.UUID(admin_user["org_id"]),
        prefix="audit-upd-member",
    )
    add_rd = await client.post(
        f"/api/v1/org-units/{rd['id']}/members",
        headers=headers,
        json={
            "user_id": str(member.id),
            "role": "unit_member",
            "is_primary": True,
        },
    )
    assert add_rd.status_code == 201
    add_hr = await client.post(
        f"/api/v1/org-units/{hr['id']}/members",
        headers=headers,
        json={
            "user_id": str(member.id),
            "role": "unit_member",
            "is_primary": False,
        },
    )
    assert add_hr.status_code == 201

    before = await _count_audit_logs(action="org_unit.member_update")

    patch_resp = await client.patch(
        f"/api/v1/org-units/{hr['id']}/members/{member.id}",
        headers=headers,
        json={"role": "unit_admin", "is_primary": True},
    )
    assert patch_resp.status_code == 200

    after = await _count_audit_logs(action="org_unit.member_update")
    assert after - before == 1

    latest = await _latest_audit_log(action="org_unit.member_update")
    assert latest is not None
    assert str(latest.actor_user_id) == admin_user["id"]
    assert str(latest.resource_id) == str(member.id)
    assert latest.details["old_role"] == "unit_member"
    assert latest.details["new_role"] == "unit_admin"
    assert latest.details["old_primary"] is False
    assert latest.details["new_primary"] is True
