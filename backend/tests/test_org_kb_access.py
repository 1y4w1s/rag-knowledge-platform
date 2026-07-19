"""ORG-1.2：require_kb_access 权限守卫测试。"""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.deps import KbAction, require_kb_access
from app.models.knowledge_base import KnowledgeBase
from tests.fixtures.org_isolation import OrgIsolationFixture

pytestmark = pytest.mark.asyncio


async def test_require_kb_access_sibling_department_403(org_iso: OrgIsolationFixture) -> None:
    async with SessionLocal() as db:
        with pytest.raises(HTTPException) as exc:
            await require_kb_access(
                kb_id=org_iso.mkt_kb_id,
                action=KbAction.read,
                current_user=org_iso.rd_member,
                db=db,
            )
    assert exc.value.status_code == 403
    assert exc.value.detail == "无权访问该资料库"


async def test_require_kb_access_rd_member_can_read_own_dept_kb(
    org_iso: OrgIsolationFixture,
) -> None:
    async with SessionLocal() as db:
        kb = await require_kb_access(
            kb_id=org_iso.rd_kb_id,
            action=KbAction.read,
            current_user=org_iso.rd_member,
            db=db,
        )
    assert kb.id == org_iso.rd_kb_id


async def test_require_kb_access_company_admin_any_dept_kb(
    org_iso: OrgIsolationFixture,
) -> None:
    async with SessionLocal() as db:
        kb = await require_kb_access(
            kb_id=org_iso.mkt_kb_id,
            action=KbAction.read,
            current_user=org_iso.owner,
            db=db,
        )
    assert kb.id == org_iso.mkt_kb_id
