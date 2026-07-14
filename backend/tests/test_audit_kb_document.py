"""EW-A3：知识库/文档审计事件测试（delete / upload / retry / delete document）。"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.document import Document
from app.models.enums import DocumentStatus
from app.services.auth.password import hash_password
from tests.conftest import create_test_kb
from tests.fixtures.audit_events import _count_audit_logs, _latest_audit_log

pytestmark = pytest.mark.asyncio


async def test_delete_kb_writes_audit_log(
    client: AsyncClient,
    register_and_login,
) -> None:
    headers, user = await register_and_login(prefix="audit-kb-del")
    kb = await create_test_kb(client, headers, user, name="待删库审计")

    before = await _count_audit_logs(action="kb.delete")

    del_resp = await client.delete(
        f"/api/v1/knowledge-bases/{kb['id']}",
        headers=headers,
    )
    assert del_resp.status_code == 204

    after = await _count_audit_logs(action="kb.delete")
    assert after - before == 1

    latest = await _latest_audit_log(action="kb.delete")
    assert latest is not None
    assert str(latest.actor_user_id) == user["id"]
    assert str(latest.kb_id) == kb["id"]
    assert latest.details == {"name": "待删库审计"}


async def test_upload_document_writes_audit_log(
    client: AsyncClient,
    register_and_login,
) -> None:
    headers, user = await register_and_login(prefix="audit-upload")
    kb = await create_test_kb(client, headers, user, name="上传审计库")

    before = await _count_audit_logs(action="document.upload")

    upload_resp = await client.post(
        f"/api/v1/knowledge-bases/{kb['id']}/documents",
        headers=headers,
        files=[("files", ("audit-note.txt", b"audit upload test", "text/plain"))],
    )
    assert upload_resp.status_code == 201

    after = await _count_audit_logs(action="document.upload")
    assert after - before == 1

    latest = await _latest_audit_log(action="document.upload")
    assert latest is not None
    assert str(latest.actor_user_id) == user["id"]
    assert str(latest.kb_id) == kb["id"]
    assert latest.details == {"filename": "audit-note.txt"}


async def test_document_retry_writes_audit_log(
    client: AsyncClient,
    register_and_login,
) -> None:
    """Plan-3E-6c：failed 文档 POST retry → audit document.retry 计数 +1。"""
    headers, user = await register_and_login(prefix="audit-doc-retry")
    kb = await create_test_kb(client, headers, user, name="重试审计库")
    kb_id = uuid.UUID(kb["id"])
    doc_id = uuid.uuid4()

    async with SessionLocal() as db:
        db.add(
            Document(
                id=doc_id,
                kb_id=kb_id,
                filename="retry-audit.txt",
                file_type="txt",
                file_size=12,
                storage_path="/tmp/unused-retry-audit.txt",
                status=DocumentStatus.failed,
                error_message="simulated failure",
                uploaded_by=uuid.UUID(user["id"]),
            )
        )
        await db.commit()

    before = await _count_audit_logs(action="document.retry")

    retry_resp = await client.post(
        f"/api/v1/knowledge-bases/{kb['id']}/documents/{doc_id}/retry",
        headers=headers,
    )
    assert retry_resp.status_code == 200

    after = await _count_audit_logs(action="document.retry")
    assert after - before == 1

    latest = await _latest_audit_log(action="document.retry")
    assert latest is not None
    assert str(latest.actor_user_id) == user["id"]
    assert str(latest.kb_id) == kb["id"]
    assert str(latest.resource_id) == str(doc_id)
    assert latest.resource_type == "document"
    assert latest.details == {"filename": "retry-audit.txt"}


async def test_delete_document_writes_audit_log(
    client: AsyncClient,
    register_and_login,
) -> None:
    headers, user = await register_and_login(prefix="audit-doc-del")
    kb = await create_test_kb(client, headers, user, name="删文档审计库")

    upload_resp = await client.post(
        f"/api/v1/knowledge-bases/{kb['id']}/documents",
        headers=headers,
        files=[("files", ("remove-me.txt", b"delete audit", "text/plain"))],
    )
    assert upload_resp.status_code == 201
    doc_id = upload_resp.json()["documents"][0]["id"]

    before = await _count_audit_logs(action="document.delete")

    del_resp = await client.delete(
        f"/api/v1/knowledge-bases/{kb['id']}/documents/{doc_id}",
        headers=headers,
    )
    assert del_resp.status_code == 204

    after = await _count_audit_logs(action="document.delete")
    assert after - before == 1

    latest = await _latest_audit_log(action="document.delete")
    assert latest is not None
    assert str(latest.resource_id) == doc_id
    assert latest.details == {"filename": "remove-me.txt"}
