"""ORG-1.3～1.4：KB 列表/详情 API 可见性隔离测试。"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.user import User
from tests.fixtures.org_isolation import OrgIsolationFixture, _login_user

pytestmark = pytest.mark.asyncio


async def test_api_list_rd_member_excludes_sibling_dept_kb(
    client: AsyncClient,
    org_iso: OrgIsolationFixture,
) -> None:
    async with SessionLocal() as db:
        rd_user = await db.get(User, org_iso.rd_member.id)
        assert rd_user is not None
        headers, _ = await _login_user(client, rd_user.email, "Test123!@")

    list_resp = await client.get(
        "/api/v1/knowledge-bases",
        headers=headers,
        params={"workspace": str(org_iso.org_id)},
    )
    assert list_resp.status_code == 200
    kb_ids = {item["id"] for item in list_resp.json()["items"]}
    assert str(org_iso.public_kb_id) in kb_ids
    assert str(org_iso.rd_kb_id) in kb_ids
    assert str(org_iso.rd_child_kb_id) in kb_ids
    assert str(org_iso.mkt_kb_id) not in kb_ids


async def test_api_get_sibling_department_kb_returns_403(
    client: AsyncClient,
    org_iso: OrgIsolationFixture,
) -> None:
    async with SessionLocal() as db:
        rd_user = await db.get(User, org_iso.rd_member.id)
        assert rd_user is not None
        headers, _ = await _login_user(client, rd_user.email, "Test123!@")

    resp = await client.get(
        f"/api/v1/knowledge-bases/{org_iso.mkt_kb_id}",
        headers=headers,
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "无权访问该资料库"


async def test_api_unassigned_member_reads_public_only(
    client: AsyncClient,
    org_iso: OrgIsolationFixture,
) -> None:
    async with SessionLocal() as db:
        user = await db.get(User, org_iso.unassigned_member.id)
        assert user is not None
        headers, _ = await _login_user(client, user.email, "Test123!@")

    public_resp = await client.get(
        f"/api/v1/knowledge-bases/{org_iso.public_kb_id}",
        headers=headers,
    )
    assert public_resp.status_code == 200

    dept_resp = await client.get(
        f"/api/v1/knowledge-bases/{org_iso.rd_kb_id}",
        headers=headers,
    )
    assert dept_resp.status_code == 403


async def test_api_e2_omitted_department_id_uses_primary_dept_scope(
    client: AsyncClient,
    org_iso: OrgIsolationFixture,
) -> None:
    """ORG-1.8 / PRD E2：不带 department_id 时默认主部门 scope。"""
    async with SessionLocal() as db:
        rd_user = await db.get(User, org_iso.rd_member.id)
        assert rd_user is not None
        headers, _ = await _login_user(client, rd_user.email, "Test123!@")

    default_resp = await client.get(
        "/api/v1/knowledge-bases",
        headers=headers,
        params={"workspace": str(org_iso.org_id)},
    )
    explicit_resp = await client.get(
        "/api/v1/knowledge-bases",
        headers=headers,
        params={
            "workspace": str(org_iso.org_id),
            "department_id": str(org_iso.rd_id),
        },
    )
    assert default_resp.status_code == 200
    assert explicit_resp.status_code == 200
    assert {item["id"] for item in default_resp.json()["items"]} == {
        item["id"] for item in explicit_resp.json()["items"]
    }
    kb_ids = {item["id"] for item in default_resp.json()["items"]}
    assert str(org_iso.rd_kb_id) in kb_ids
    assert str(org_iso.mkt_kb_id) not in kb_ids


async def test_api_e3_member_forged_department_id_returns_403(
    client: AsyncClient,
    org_iso: OrgIsolationFixture,
) -> None:
    """ORG-1.8 / PRD E3：Member 伪造兄弟部门 department_id → 403。"""
    async with SessionLocal() as db:
        rd_user = await db.get(User, org_iso.rd_member.id)
        assert rd_user is not None
        headers, _ = await _login_user(client, rd_user.email, "Test123!@")

    forged_params = {
        "workspace": str(org_iso.org_id),
        "department_id": str(org_iso.mkt_id),
    }

    list_resp = await client.get(
        "/api/v1/knowledge-bases",
        headers=headers,
        params=forged_params,
    )
    assert list_resp.status_code == 403
    assert list_resp.json()["detail"] == "无权访问该部门"

    stats_resp = await client.get(
        "/api/v1/dashboard/stats",
        headers=headers,
        params=forged_params,
    )
    assert stats_resp.status_code == 403

    search_resp = await client.get(
        "/api/v1/search/documents",
        headers=headers,
        params={**forged_params, "q": "doc"},
    )
    assert search_resp.status_code == 403


async def test_api_e3_member_department_all_returns_403(
    client: AsyncClient,
    org_iso: OrgIsolationFixture,
) -> None:
    """ORG-1.8 / PRD E3/E8：Member 带 department_id=all → 403。"""
    async with SessionLocal() as db:
        rd_user = await db.get(User, org_iso.rd_member.id)
        assert rd_user is not None
        headers, _ = await _login_user(client, rd_user.email, "Test123!@")

    params = {
        "workspace": str(org_iso.org_id),
        "department_id": "all",
    }

    list_resp = await client.get(
        "/api/v1/knowledge-bases",
        headers=headers,
        params=params,
    )
    assert list_resp.status_code == 403
    assert list_resp.json()["detail"] == "无权访问该部门"

    stats_resp = await client.get(
        "/api/v1/dashboard/stats",
        headers=headers,
        params=params,
    )
    assert stats_resp.status_code == 403


async def test_api_admin_department_all_includes_all_dept_kbs(
    client: AsyncClient,
    org_iso: OrgIsolationFixture,
) -> None:
    """ORG-1.8：公司 Admin department_id=all 可见全公司库。"""
    async with SessionLocal() as db:
        owner_user = await db.get(User, org_iso.owner.id)
        assert owner_user is not None
        headers, _ = await _login_user(client, owner_user.email, "Test123!@")

    list_resp = await client.get(
        "/api/v1/knowledge-bases",
        headers=headers,
        params={
            "workspace": str(org_iso.org_id),
            "department_id": "all",
        },
    )
    assert list_resp.status_code == 200
    kb_ids = {item["id"] for item in list_resp.json()["items"]}
    assert str(org_iso.mkt_kb_id) in kb_ids
    assert str(org_iso.rd_kb_id) in kb_ids
    assert str(org_iso.public_kb_id) in kb_ids
