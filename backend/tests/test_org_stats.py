"""ORG-3.5：Dashboard stats API 部门隔离测试。"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.enums import DocumentStatus
from app.models.user import User
from tests.fixtures.org_isolation import OrgIsolationFixture, _login_user, _seed_kb_documents

pytestmark = pytest.mark.asyncio


async def test_api_stats_rd_member_excludes_sibling_dept_kb(
    client: AsyncClient,
    org_iso: OrgIsolationFixture,
) -> None:
    async with SessionLocal() as db:
        await _seed_kb_documents(
            db,
            kb_id=org_iso.mkt_kb_id,
            count=3,
            uploaded_by=org_iso.mkt_member.id,
        )
        await _seed_kb_documents(
            db,
            kb_id=org_iso.rd_kb_id,
            count=2,
            uploaded_by=org_iso.rd_member.id,
        )
        await db.commit()
        rd_user = await db.get(User, org_iso.rd_member.id)
        assert rd_user is not None
        headers, _ = await _login_user(client, rd_user.email, "Test123!@")

    stats_resp = await client.get(
        "/api/v1/dashboard/stats",
        headers=headers,
        params={"workspace": str(org_iso.org_id)},
    )
    assert stats_resp.status_code == 200
    stats = stats_resp.json()

    assert stats["knowledge_base_count"] == 3
    assert stats["document_count"] == 2
    assert stats["total_chunk_count"] == 2


async def test_api_stats_matches_kb_list_for_rd_member(
    client: AsyncClient,
    org_iso: OrgIsolationFixture,
) -> None:
    async with SessionLocal() as db:
        await _seed_kb_documents(
            db,
            kb_id=org_iso.mkt_kb_id,
            count=3,
            uploaded_by=org_iso.mkt_member.id,
        )
        await _seed_kb_documents(
            db,
            kb_id=org_iso.rd_kb_id,
            count=2,
            uploaded_by=org_iso.rd_member.id,
        )
        await _seed_kb_documents(
            db,
            kb_id=org_iso.rd_child_kb_id,
            count=1,
            uploaded_by=org_iso.rd_member.id,
            status=DocumentStatus.failed,
            chunk_count=0,
        )
        await db.commit()
        rd_user = await db.get(User, org_iso.rd_member.id)
        assert rd_user is not None
        headers, _ = await _login_user(client, rd_user.email, "Test123!@")

    list_resp = await client.get(
        "/api/v1/knowledge-bases",
        headers=headers,
        params={"workspace": str(org_iso.org_id)},
    )
    stats_resp = await client.get(
        "/api/v1/dashboard/stats",
        headers=headers,
        params={"workspace": str(org_iso.org_id)},
    )
    assert list_resp.status_code == 200
    assert stats_resp.status_code == 200

    items = list_resp.json()["items"]
    stats = stats_resp.json()
    list_kb_ids = {item["id"] for item in items}

    assert str(org_iso.mkt_kb_id) not in list_kb_ids
    assert stats["knowledge_base_count"] == len(items)
    assert stats["document_count"] == sum(item["document_count"] for item in items)
    assert stats["documents_by_status"]["completed"] == sum(
        item["document_count"] - item["failed_count"] for item in items
    )
    assert stats["documents_by_status"]["failed"] == sum(
        item["failed_count"] for item in items
    )
    assert stats["total_chunk_count"] == 2


async def test_api_stats_ops_metrics_department_scoped(
    client: AsyncClient,
    org_iso: OrgIsolationFixture,
) -> None:
    """ORG-3.5 / Plan-3E-6b：运营指标 audit 聚合与 visible_kb 同 OrgScope。"""
    from app.services.audit.log import write_audit_log

    actor_id = org_iso.owner.id
    async with SessionLocal() as db:
        for _ in range(3):
            await write_audit_log(
                db,
                action="document.retry",
                actor_user_id=actor_id,
                resource_type="document",
                kb_id=org_iso.mkt_kb_id,
            )
        await write_audit_log(
            db,
            action="document.retry",
            actor_user_id=actor_id,
            resource_type="document",
            kb_id=org_iso.rd_kb_id,
        )
        await write_audit_log(
            db,
            action="storage.cleanup_failed",
            actor_user_id=actor_id,
            resource_type="document",
            kb_id=org_iso.mkt_kb_id,
        )
        await db.commit()
        owner_user = await db.get(User, org_iso.owner.id)
        assert owner_user is not None
        rd_user = await db.get(User, org_iso.rd_member.id)
        assert rd_user is not None
        owner_headers, _ = await _login_user(client, owner_user.email, "Test123!@")
        rd_headers, _ = await _login_user(client, rd_user.email, "Test123!@")

    ws = str(org_iso.org_id)
    mkt_stats = await client.get(
        "/api/v1/dashboard/stats",
        headers=owner_headers,
        params={"workspace": ws, "department_id": str(org_iso.mkt_id)},
    )
    rd_stats = await client.get(
        "/api/v1/dashboard/stats",
        headers=owner_headers,
        params={"workspace": ws, "department_id": str(org_iso.rd_id)},
    )
    rd_member_stats = await client.get(
        "/api/v1/dashboard/stats",
        headers=rd_headers,
        params={"workspace": ws},
    )
    assert mkt_stats.status_code == 200
    assert rd_stats.status_code == 200
    assert rd_member_stats.status_code == 200

    mkt_body = mkt_stats.json()
    rd_body = rd_stats.json()
    rd_member_body = rd_member_stats.json()

    assert mkt_body["document_retry_count_7d"] == 3
    assert mkt_body["storage_cleanup_failure_count"] == 1
    assert rd_body["document_retry_count_7d"] == 1
    assert rd_body["storage_cleanup_failure_count"] == 0
    assert rd_member_body["document_retry_count_7d"] == 1
    assert rd_member_body["storage_cleanup_failure_count"] == 0
