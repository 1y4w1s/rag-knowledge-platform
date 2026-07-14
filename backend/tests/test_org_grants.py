"""ORG-4.5：kb_unit_grants CRUD + ORG-1-4 边界 E1～E8。"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.core.database import SessionLocal
from app.models.knowledge_base import KnowledgeBase
from tests.fixtures.org_isolation import OrgIsolationFixture, _login_user


def _org_workspace_params(org_id, *, department_id: str | None = None) -> dict:
    params = {"workspace": str(org_id)}
    if department_id is not None:
        params["department_id"] = department_id
    return params


def _grants_url(kb_id) -> str:
    return f"/api/v1/knowledge-bases/{kb_id}/grants"


@pytest.mark.asyncio
async def test_list_create_delete_grant_company_wide(
    client: AsyncClient,
    org_iso: OrgIsolationFixture,
) -> None:
    """S3：unit_admin 对部门库加全公司 read grant；列表可查；撤销后消失。"""
    password = "password123"
    owner_headers, _ = await _login_user(client, org_iso.owner.email, password)

    create_resp = await client.post(
        _grants_url(org_iso.mkt_kb_id),
        headers=owner_headers,
        json={"grantee_type": "company", "permission": "read"},
    )
    assert create_resp.status_code == 201
    grant = create_resp.json()
    assert grant["kb_id"] == str(org_iso.mkt_kb_id)
    assert grant["grantee_type"] == "company"
    assert grant["grantee_id"] is None

    list_resp = await client.get(
        _grants_url(org_iso.mkt_kb_id),
        headers=owner_headers,
    )
    assert list_resp.status_code == 200
    assert any(item["id"] == grant["id"] for item in list_resp.json()["items"])

    delete_resp = await client.delete(
        f"{_grants_url(org_iso.mkt_kb_id)}/{grant['id']}",
        headers=owner_headers,
    )
    assert delete_resp.status_code == 204

    list_after = await client.get(
        _grants_url(org_iso.mkt_kb_id),
        headers=owner_headers,
    )
    assert list_after.status_code == 200
    assert list_after.json()["items"] == []


@pytest.mark.asyncio
async def test_grant_makes_kb_visible_then_revoke_hides(
    client: AsyncClient,
    org_iso: OrgIsolationFixture,
) -> None:
    """S3/S4：grant 后研发 Member 列表可见市场库；撤销后不可见。"""
    password = "password123"
    owner_headers, _ = await _login_user(client, org_iso.owner.email, password)
    rd_member_headers, _ = await _login_user(
        client,
        org_iso.rd_member.email,
        password,
    )

    create_resp = await client.post(
        _grants_url(org_iso.mkt_kb_id),
        headers=owner_headers,
        json={"grantee_type": "company", "permission": "read"},
    )
    assert create_resp.status_code == 201
    grant_id = create_resp.json()["id"]

    visible = await client.get(
        "/api/v1/knowledge-bases",
        headers=rd_member_headers,
        params=_org_workspace_params(org_iso.org_id, department_id=str(org_iso.rd_id)),
    )
    assert visible.status_code == 200
    assert any(item["id"] == str(org_iso.mkt_kb_id) for item in visible.json()["items"])

    delete_resp = await client.delete(
        f"{_grants_url(org_iso.mkt_kb_id)}/{grant_id}",
        headers=owner_headers,
    )
    assert delete_resp.status_code == 204

    hidden = await client.get(
        "/api/v1/knowledge-bases",
        headers=rd_member_headers,
        params=_org_workspace_params(org_iso.org_id, department_id=str(org_iso.rd_id)),
    )
    assert hidden.status_code == 200
    assert not any(item["id"] == str(org_iso.mkt_kb_id) for item in hidden.json()["items"])


@pytest.mark.asyncio
async def test_unit_admin_can_grant_own_department_kb(
    client: AsyncClient,
    org_iso: OrgIsolationFixture,
) -> None:
    """研发 unit_admin 可对本部门库添加 grant。"""
    password = "password123"
    headers, _ = await _login_user(client, org_iso.rd_admin.email, password)

    resp = await client.post(
        _grants_url(org_iso.rd_kb_id),
        headers=headers,
        json={
            "grantee_type": "org_unit",
            "grantee_id": str(org_iso.mkt_id),
            "permission": "read",
        },
    )
    assert resp.status_code == 201
    assert resp.json()["grantee_id"] == str(org_iso.mkt_id)


@pytest.mark.asyncio
async def test_cannot_grant_invisible_kb_e3(
    client: AsyncClient,
    org_iso: OrgIsolationFixture,
) -> None:
    """E3：研发 unit_admin 不能对市场部库加 grant。"""
    password = "password123"
    headers, _ = await _login_user(client, org_iso.rd_admin.email, password)

    resp = await client.post(
        _grants_url(org_iso.mkt_kb_id),
        headers=headers,
        json={"grantee_type": "company", "permission": "read"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_duplicate_grant_returns_409_e4(
    client: AsyncClient,
    org_iso: OrgIsolationFixture,
) -> None:
    """E4：重复添加同一 grant 目标 → 409。"""
    password = "password123"
    headers, _ = await _login_user(client, org_iso.owner.email, password)
    payload = {"grantee_type": "company", "permission": "read"}

    first = await client.post(
        _grants_url(org_iso.mkt_kb_id),
        headers=headers,
        json=payload,
    )
    assert first.status_code == 201

    second = await client.post(
        _grants_url(org_iso.mkt_kb_id),
        headers=headers,
        json=payload,
    )
    assert second.status_code == 409


@pytest.mark.asyncio
async def test_public_kb_company_grant_redundant_e6(
    client: AsyncClient,
    org_iso: OrgIsolationFixture,
) -> None:
    """E6：公司公共库再加全公司 grant → 409。"""
    password = "password123"
    headers, _ = await _login_user(client, org_iso.owner.email, password)

    resp = await client.post(
        _grants_url(org_iso.public_kb_id),
        headers=headers,
        json={"grantee_type": "company", "permission": "read"},
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_member_cannot_manage_grants(
    client: AsyncClient,
    org_iso: OrgIsolationFixture,
) -> None:
    """普通 Member 不能查/建 grant。"""
    password = "password123"
    headers, _ = await _login_user(client, org_iso.rd_member.email, password)

    list_resp = await client.get(
        _grants_url(org_iso.rd_kb_id),
        headers=headers,
    )
    assert list_resp.status_code == 403

    create_resp = await client.post(
        _grants_url(org_iso.rd_kb_id),
        headers=headers,
        json={"grantee_type": "company", "permission": "read"},
    )
    assert create_resp.status_code == 403


@pytest.mark.asyncio
async def test_member_cannot_create_kb_e1(
    client: AsyncClient,
    org_iso: OrgIsolationFixture,
) -> None:
    """E1：普通 Member 建库 / 选公共 → 403。"""
    password = "password123"
    headers, _ = await _login_user(client, org_iso.rd_member.email, password)

    dept_resp = await client.post(
        "/api/v1/knowledge-bases",
        headers=headers,
        params=_org_workspace_params(org_iso.org_id, department_id=str(org_iso.rd_id)),
        json={"name": "Member 部门库"},
    )
    assert dept_resp.status_code == 403

    public_resp = await client.post(
        "/api/v1/knowledge-bases",
        headers=headers,
        params=_org_workspace_params(org_iso.org_id, department_id=str(org_iso.rd_id)),
        json={"name": "Member 公共库", "org_unit_id": None},
    )
    assert public_resp.status_code == 403


@pytest.mark.asyncio
async def test_unit_admin_cannot_attach_sibling_department_e2(
    client: AsyncClient,
    org_iso: OrgIsolationFixture,
) -> None:
    """E2：硬闯 POST 库 · org_unit_id=兄弟部门 → 403。"""
    password = "password123"
    headers, _ = await _login_user(client, org_iso.rd_admin.email, password)

    resp = await client.post(
        "/api/v1/knowledge-bases",
        headers=headers,
        params=_org_workspace_params(org_iso.org_id, department_id=str(org_iso.rd_id)),
        json={"name": "越权挂兄弟部门", "org_unit_id": str(org_iso.mkt_id)},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_grant_survives_kb_relocation_e5(
    client: AsyncClient,
    org_iso: OrgIsolationFixture,
) -> None:
    """E5：库迁到另一部门后旧 grant 仍有效（按 kb_id）；可见性按新归属+grant 重算。"""
    password = "password123"
    owner_headers, _ = await _login_user(client, org_iso.owner.email, password)
    rd_member_headers, _ = await _login_user(
        client,
        org_iso.rd_member.email,
        password,
    )
    mkt_member_headers, _ = await _login_user(
        client,
        org_iso.mkt_member.email,
        password,
    )

    before_mkt = await client.get(
        "/api/v1/knowledge-bases",
        headers=mkt_member_headers,
        params=_org_workspace_params(org_iso.org_id, department_id=str(org_iso.mkt_id)),
    )
    assert before_mkt.status_code == 200
    assert any(item["id"] == str(org_iso.mkt_kb_id) for item in before_mkt.json()["items"])

    before_rd = await client.get(
        "/api/v1/knowledge-bases",
        headers=rd_member_headers,
        params=_org_workspace_params(org_iso.org_id, department_id=str(org_iso.rd_id)),
    )
    assert before_rd.status_code == 200
    assert not any(item["id"] == str(org_iso.mkt_kb_id) for item in before_rd.json()["items"])

    create_resp = await client.post(
        _grants_url(org_iso.mkt_kb_id),
        headers=owner_headers,
        json={
            "grantee_type": "org_unit",
            "grantee_id": str(org_iso.rd_id),
            "permission": "read",
        },
    )
    assert create_resp.status_code == 201
    grant_id = create_resp.json()["id"]

    after_grant = await client.get(
        "/api/v1/knowledge-bases",
        headers=rd_member_headers,
        params=_org_workspace_params(org_iso.org_id, department_id=str(org_iso.rd_id)),
    )
    assert after_grant.status_code == 200
    assert any(item["id"] == str(org_iso.mkt_kb_id) for item in after_grant.json()["items"])

    async with SessionLocal() as db:
        kb = await db.get(KnowledgeBase, org_iso.mkt_kb_id)
        assert kb is not None
        kb.org_unit_id = org_iso.rd_child_id
        await db.commit()

    list_grants = await client.get(
        _grants_url(org_iso.mkt_kb_id),
        headers=owner_headers,
    )
    assert list_grants.status_code == 200
    assert any(item["id"] == grant_id for item in list_grants.json()["items"])

    after_move_mkt = await client.get(
        "/api/v1/knowledge-bases",
        headers=mkt_member_headers,
        params=_org_workspace_params(org_iso.org_id, department_id=str(org_iso.mkt_id)),
    )
    assert after_move_mkt.status_code == 200
    assert not any(item["id"] == str(org_iso.mkt_kb_id) for item in after_move_mkt.json()["items"])

    after_move_rd = await client.get(
        "/api/v1/knowledge-bases",
        headers=rd_member_headers,
        params=_org_workspace_params(org_iso.org_id, department_id=str(org_iso.rd_id)),
    )
    assert after_move_rd.status_code == 200
    assert any(item["id"] == str(org_iso.mkt_kb_id) for item in after_move_rd.json()["items"])


@pytest.mark.asyncio
async def test_chat_blocked_after_grant_revoked_e7(
    client: AsyncClient,
    org_iso: OrgIsolationFixture,
) -> None:
    """E7：对话检索 grant 库 · 撤 grant 后下一条 chat → 403。"""
    password = "password123"
    owner_headers, _ = await _login_user(client, org_iso.owner.email, password)
    rd_member_headers, _ = await _login_user(
        client,
        org_iso.rd_member.email,
        password,
    )

    create_resp = await client.post(
        _grants_url(org_iso.mkt_kb_id),
        headers=owner_headers,
        json={"grantee_type": "company", "permission": "read"},
    )
    assert create_resp.status_code == 201
    grant_id = create_resp.json()["id"]

    allowed = await client.post(
        f"/api/v1/knowledge-bases/{org_iso.mkt_kb_id}/chat",
        headers=rd_member_headers,
        json={"message": "grant 可见时提问"},
    )
    assert allowed.status_code == 200

    delete_resp = await client.delete(
        f"{_grants_url(org_iso.mkt_kb_id)}/{grant_id}",
        headers=owner_headers,
    )
    assert delete_resp.status_code == 204

    blocked = await client.post(
        f"/api/v1/knowledge-bases/{org_iso.mkt_kb_id}/chat",
        headers=rd_member_headers,
        json={"message": "撤 grant 后再问"},
    )
    assert blocked.status_code == 403


@pytest.mark.asyncio
async def test_unit_admin_cannot_create_public_kb_e8(
    client: AsyncClient,
    org_iso: OrgIsolationFixture,
) -> None:
    """E8：部门 Admin 建库选「公司公共」→ 403。"""
    password = "password123"
    headers, _ = await _login_user(client, org_iso.rd_admin.email, password)

    resp = await client.post(
        "/api/v1/knowledge-bases",
        headers=headers,
        params=_org_workspace_params(org_iso.org_id, department_id=str(org_iso.rd_id)),
        json={"name": "部门 Admin 公共库", "org_unit_id": None},
    )
    assert resp.status_code == 403
