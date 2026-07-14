"""ORG-4.1：建库 org_unit_id 归属 + 权限边界。"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

from tests.conftest import workspace_query
from tests.test_org_isolation import OrgIsolationFixture, _login_user


def _org_workspace_params(org_id: uuid.UUID, *, department_id: str | None = None) -> dict:
    params = {"workspace": str(org_id)}
    if department_id is not None:
        params["department_id"] = department_id
    return params


@pytest.mark.asyncio
async def test_unit_admin_create_kb_attached_to_department(
    client: AsyncClient,
    org_iso: OrgIsolationFixture,
) -> None:
    """S1：研发 unit_admin 建库挂研发部；研发 Member 可见，市场 Member 不可见。"""
    password = "password123"
    rd_admin_headers, _ = await _login_user(client, org_iso.rd_admin.email, password)

    create_resp = await client.post(
        "/api/v1/knowledge-bases",
        headers=rd_admin_headers,
        params=_org_workspace_params(org_iso.org_id, department_id=str(org_iso.rd_id)),
        json={"name": "研发专属库"},
    )
    assert create_resp.status_code == 201
    kb = create_resp.json()
    assert kb["org_unit_id"] == str(org_iso.rd_id)

    rd_member_headers, _ = await _login_user(
        client,
        org_iso.rd_member.email,
        password,
    )
    rd_list = await client.get(
        "/api/v1/knowledge-bases",
        headers=rd_member_headers,
        params=_org_workspace_params(org_iso.org_id, department_id=str(org_iso.rd_id)),
    )
    assert rd_list.status_code == 200
    assert any(item["id"] == kb["id"] for item in rd_list.json()["items"])

    mkt_member_headers, _ = await _login_user(
        client,
        org_iso.mkt_member.email,
        password,
    )
    mkt_list = await client.get(
        "/api/v1/knowledge-bases",
        headers=mkt_member_headers,
        params=_org_workspace_params(org_iso.org_id, department_id=str(org_iso.mkt_id)),
    )
    assert mkt_list.status_code == 200
    assert not any(item["id"] == kb["id"] for item in mkt_list.json()["items"])


@pytest.mark.asyncio
async def test_company_admin_create_public_kb(
    client: AsyncClient,
    org_iso: OrgIsolationFixture,
) -> None:
    """S2：公司 Admin 建公司公共库；各部门 Member 均可见。"""
    password = "password123"
    owner_headers, _ = await _login_user(client, org_iso.owner.email, password)

    create_resp = await client.post(
        "/api/v1/knowledge-bases",
        headers=owner_headers,
        params=_org_workspace_params(org_iso.org_id, department_id=str(org_iso.rd_id)),
        json={"name": "全员手册", "org_unit_id": None},
    )
    assert create_resp.status_code == 201
    kb = create_resp.json()
    assert kb["org_unit_id"] is None

    for member in (org_iso.rd_member, org_iso.mkt_member):
        headers, _ = await _login_user(client, member.email, password)
        dept = org_iso.rd_id if member.id == org_iso.rd_member.id else org_iso.mkt_id
        list_resp = await client.get(
            "/api/v1/knowledge-bases",
            headers=headers,
            params=_org_workspace_params(org_iso.org_id, department_id=str(dept)),
        )
        assert list_resp.status_code == 200
        assert any(item["id"] == kb["id"] for item in list_resp.json()["items"])


@pytest.mark.asyncio
async def test_unit_admin_cannot_create_public_kb(
    client: AsyncClient,
    org_iso: OrgIsolationFixture,
) -> None:
    """E8：部门 Admin 不能建公司公共库。"""
    password = "password123"
    headers, _ = await _login_user(client, org_iso.rd_admin.email, password)

    resp = await client.post(
        "/api/v1/knowledge-bases",
        headers=headers,
        params=_org_workspace_params(org_iso.org_id, department_id=str(org_iso.rd_id)),
        json={"name": "试图公共", "org_unit_id": None},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_unit_admin_cannot_attach_sibling_department(
    client: AsyncClient,
    org_iso: OrgIsolationFixture,
) -> None:
    """E2：部门 Admin 不能把库挂到兄弟部门。"""
    password = "password123"
    headers, _ = await _login_user(client, org_iso.rd_admin.email, password)

    resp = await client.post(
        "/api/v1/knowledge-bases",
        headers=headers,
        params=_org_workspace_params(org_iso.org_id, department_id=str(org_iso.rd_id)),
        json={"name": "越权库", "org_unit_id": str(org_iso.mkt_id)},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_org_member_cannot_create_kb(
    client: AsyncClient,
    org_iso: OrgIsolationFixture,
) -> None:
    """E1：普通 Member 建库 403。"""
    password = "password123"
    headers, _ = await _login_user(client, org_iso.rd_member.email, password)

    resp = await client.post(
        "/api/v1/knowledge-bases",
        headers=headers,
        params=_org_workspace_params(org_iso.org_id, department_id=str(org_iso.rd_id)),
        json={"name": "Member 建库"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_personal_create_ignores_org_unit_id(
    client: AsyncClient,
    register_and_login,
) -> None:
    """E10：个人空间忽略 body 中的 org_unit_id。"""
    headers, user = await register_and_login(prefix="personal-org-unit")

    resp = await client.post(
        "/api/v1/knowledge-bases",
        headers=headers,
        params=workspace_query(user),
        json={"name": "个人库", "org_unit_id": str(uuid.uuid4())},
    )
    assert resp.status_code == 201
    assert resp.json()["org_unit_id"] is None
