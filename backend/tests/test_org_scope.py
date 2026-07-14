"""ORG-1.1：OrgScope 隔离矩阵 — resolve_org_scope 单元风格测试。"""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.enums import GranteeType, GrantPermission
from app.models.kb_unit_grant import KbUnitGrant
from app.models.knowledge_base import KnowledgeBase
from app.services.org.scope import resolve_org_scope
from tests.fixtures.org_isolation import OrgIsolationFixture

pytestmark = pytest.mark.asyncio


async def test_scope_rd_member_sees_subtree_and_public(org_iso: OrgIsolationFixture) -> None:
    async with SessionLocal() as db:
        scope = await resolve_org_scope(db, org_iso.rd_member)
    assert org_iso.public_kb_id in scope.visible_kb_ids
    assert org_iso.rd_kb_id in scope.visible_kb_ids
    assert org_iso.rd_child_kb_id in scope.visible_kb_ids
    assert org_iso.mkt_kb_id not in scope.visible_kb_ids


async def test_scope_sibling_department_isolated(org_iso: OrgIsolationFixture) -> None:
    async with SessionLocal() as db:
        rd_scope = await resolve_org_scope(db, org_iso.rd_member)
        mkt_scope = await resolve_org_scope(db, org_iso.mkt_member)
    assert org_iso.mkt_kb_id in mkt_scope.visible_kb_ids
    assert org_iso.mkt_kb_id not in rd_scope.visible_kb_ids
    assert org_iso.rd_kb_id in rd_scope.visible_kb_ids
    assert org_iso.rd_kb_id not in mkt_scope.visible_kb_ids


async def test_scope_company_admin_all_includes_every_dept_kb(org_iso: OrgIsolationFixture) -> None:
    async with SessionLocal() as db:
        scope = await resolve_org_scope(
            db, org_iso.owner, department_id="all"
        )
    assert org_iso.mkt_kb_id in scope.visible_kb_ids
    assert org_iso.rd_kb_id in scope.visible_kb_ids
    assert org_iso.public_kb_id in scope.visible_kb_ids


async def test_scope_member_cannot_use_department_all(org_iso: OrgIsolationFixture) -> None:
    async with SessionLocal() as db:
        with pytest.raises(HTTPException) as exc:
            await resolve_org_scope(db, org_iso.rd_member, department_id="all")
    assert exc.value.status_code == 403


async def test_scope_unassigned_only_public(org_iso: OrgIsolationFixture) -> None:
    async with SessionLocal() as db:
        scope = await resolve_org_scope(db, org_iso.unassigned_member)
    assert scope.visible_kb_ids == frozenset({org_iso.public_kb_id})


async def test_scope_grant_company_makes_dept_kb_visible(org_iso: OrgIsolationFixture) -> None:
    async with SessionLocal() as db:
        db.add(
            KbUnitGrant(
                kb_id=org_iso.mkt_kb_id,
                grantee_type=GranteeType.company,
                grantee_id=None,
                permission=GrantPermission.read,
            )
        )
        await db.commit()
        scope = await resolve_org_scope(db, org_iso.rd_member)
    assert org_iso.mkt_kb_id in scope.visible_kb_ids


async def test_scope_grant_target_unit_visible_to_grantee_dept(org_iso: OrgIsolationFixture) -> None:
    async with SessionLocal() as db:
        db.add(
            KbUnitGrant(
                kb_id=org_iso.mkt_kb_id,
                grantee_type=GranteeType.org_unit,
                grantee_id=org_iso.rd_id,
                permission=GrantPermission.read,
            )
        )
        await db.commit()
        scope = await resolve_org_scope(db, org_iso.rd_member)
    assert org_iso.mkt_kb_id in scope.visible_kb_ids


async def test_scope_forged_department_id_rejected(org_iso: OrgIsolationFixture) -> None:
    async with SessionLocal() as db:
        with pytest.raises(HTTPException) as exc:
            await resolve_org_scope(
                db,
                org_iso.rd_member,
                department_id=str(org_iso.mkt_id),
            )
    assert exc.value.status_code == 403


async def test_scope_sql_filter_matches_visible_set(org_iso: OrgIsolationFixture) -> None:
    async with SessionLocal() as db:
        scope = await resolve_org_scope(db, org_iso.rd_member)
        rows = await db.scalars(
            select(KnowledgeBase.id).where(scope.kb_visibility_clause())
        )
    assert set(rows.all()) == set(scope.visible_kb_ids)


async def test_scope_writable_unit_admin_subtree(org_iso: OrgIsolationFixture) -> None:
    async with SessionLocal() as db:
        scope = await resolve_org_scope(db, org_iso.rd_admin)
    assert org_iso.rd_kb_id in scope.writable_kb_ids
    assert org_iso.rd_child_kb_id in scope.writable_kb_ids
    assert org_iso.mkt_kb_id not in scope.writable_kb_ids
    assert org_iso.public_kb_id not in scope.writable_kb_ids


async def test_scope_writable_company_admin_all(org_iso: OrgIsolationFixture) -> None:
    async with SessionLocal() as db:
        scope = await resolve_org_scope(db, org_iso.owner, department_id="all")
    assert org_iso.mkt_kb_id in scope.writable_kb_ids
    assert org_iso.public_kb_id in scope.writable_kb_ids
