"""R1-4 / Plan-10-4：单库文档列表高级筛选。"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient

from app.core.database import SessionLocal
from app.models.document import Document
from app.models.enums import DocumentStatus
from tests.conftest import create_test_kb as _create_kb


async def _seed_document(
    *,
    kb_id: uuid.UUID,
    user_id: uuid.UUID,
    filename: str,
    file_type: str = "txt",
    status: DocumentStatus = DocumentStatus.completed,
    created_at: datetime | None = None,
) -> uuid.UUID:
    doc_id = uuid.uuid4()
    async with SessionLocal() as db:
        doc = Document(
            id=doc_id,
            kb_id=kb_id,
            filename=filename,
            file_type=file_type,
            file_size=12,
            storage_path=f"/tmp/{doc_id}.{file_type}",
            status=status,
            uploaded_by=user_id,
        )
        if created_at is not None:
            doc.created_at = created_at
            doc.updated_at = created_at
        db.add(doc)
        await db.commit()
    return doc_id


@pytest.mark.asyncio
async def test_list_documents_filter_by_file_type(
    client: AsyncClient,
    register_and_login,
) -> None:
    headers, user = await register_and_login(prefix="doc-filter-type")
    kb = await _create_kb(client, headers, user)
    kb_id = uuid.UUID(kb["id"])
    user_id = uuid.UUID(user["id"])

    await _seed_document(
        kb_id=kb_id, user_id=user_id, filename="a.pdf", file_type="pdf"
    )
    await _seed_document(
        kb_id=kb_id, user_id=user_id, filename="b.docx", file_type="docx"
    )
    await _seed_document(
        kb_id=kb_id, user_id=user_id, filename="c.txt", file_type="txt"
    )

    resp = await client.get(
        f"/api/v1/knowledge-bases/{kb['id']}/documents",
        headers=headers,
        params=[("file_type", "pdf"), ("file_type", "docx")],
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    names = {item["filename"] for item in body["items"]}
    assert names == {"a.pdf", "b.docx"}


@pytest.mark.asyncio
async def test_list_documents_filter_by_status_failed(
    client: AsyncClient,
    register_and_login,
) -> None:
    headers, user = await register_and_login(prefix="doc-filter-failed")
    kb = await _create_kb(client, headers, user)
    kb_id = uuid.UUID(kb["id"])
    user_id = uuid.UUID(user["id"])

    await _seed_document(
        kb_id=kb_id,
        user_id=user_id,
        filename="ok.txt",
        status=DocumentStatus.completed,
    )
    await _seed_document(
        kb_id=kb_id,
        user_id=user_id,
        filename="bad.txt",
        status=DocumentStatus.failed,
    )

    resp = await client.get(
        f"/api/v1/knowledge-bases/{kb['id']}/documents",
        headers=headers,
        params={"status": "failed"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["filename"] == "bad.txt"


@pytest.mark.asyncio
async def test_list_documents_filter_processing_expands_queued_and_processing(
    client: AsyncClient,
    register_and_login,
) -> None:
    headers, user = await register_and_login(prefix="doc-filter-proc")
    kb = await _create_kb(client, headers, user)
    kb_id = uuid.UUID(kb["id"])
    user_id = uuid.UUID(user["id"])

    await _seed_document(
        kb_id=kb_id,
        user_id=user_id,
        filename="queued.txt",
        status=DocumentStatus.queued,
    )
    await _seed_document(
        kb_id=kb_id,
        user_id=user_id,
        filename="running.txt",
        status=DocumentStatus.processing,
    )
    await _seed_document(
        kb_id=kb_id,
        user_id=user_id,
        filename="done.txt",
        status=DocumentStatus.completed,
    )

    resp = await client.get(
        f"/api/v1/knowledge-bases/{kb['id']}/documents",
        headers=headers,
        params={"status": "processing"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    names = {item["filename"] for item in body["items"]}
    assert names == {"queued.txt", "running.txt"}


@pytest.mark.asyncio
async def test_list_documents_filter_multi_status(
    client: AsyncClient,
    register_and_login,
) -> None:
    headers, user = await register_and_login(prefix="doc-filter-multi")
    kb = await _create_kb(client, headers, user)
    kb_id = uuid.UUID(kb["id"])
    user_id = uuid.UUID(user["id"])

    await _seed_document(
        kb_id=kb_id,
        user_id=user_id,
        filename="done.txt",
        status=DocumentStatus.completed,
    )
    await _seed_document(
        kb_id=kb_id,
        user_id=user_id,
        filename="bad.txt",
        status=DocumentStatus.failed,
    )
    await _seed_document(
        kb_id=kb_id,
        user_id=user_id,
        filename="run.txt",
        status=DocumentStatus.processing,
    )

    resp = await client.get(
        f"/api/v1/knowledge-bases/{kb['id']}/documents",
        headers=headers,
        params=[("status", "failed"), ("status", "completed")],
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    names = {item["filename"] for item in body["items"]}
    assert names == {"done.txt", "bad.txt"}


@pytest.mark.asyncio
async def test_list_documents_filter_uploaded_date_range(
    client: AsyncClient,
    register_and_login,
) -> None:
    headers, user = await register_and_login(prefix="doc-filter-date")
    kb = await _create_kb(client, headers, user)
    kb_id = uuid.UUID(kb["id"])
    user_id = uuid.UUID(user["id"])

    old = datetime(2026, 1, 10, 12, 0, tzinfo=timezone.utc)
    mid = datetime(2026, 3, 15, 12, 0, tzinfo=timezone.utc)
    new = datetime(2026, 6, 20, 12, 0, tzinfo=timezone.utc)

    await _seed_document(
        kb_id=kb_id, user_id=user_id, filename="old.txt", created_at=old
    )
    await _seed_document(
        kb_id=kb_id, user_id=user_id, filename="mid.txt", created_at=mid
    )
    await _seed_document(
        kb_id=kb_id, user_id=user_id, filename="new.txt", created_at=new
    )

    resp = await client.get(
        f"/api/v1/knowledge-bases/{kb['id']}/documents",
        headers=headers,
        params={
            "uploaded_from": "2026-03-01",
            "uploaded_to": "2026-04-30",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["filename"] == "mid.txt"


@pytest.mark.asyncio
async def test_list_documents_invalid_date_range_returns_400(
    client: AsyncClient,
    register_and_login,
) -> None:
    headers, user = await register_and_login(prefix="doc-filter-date-bad")
    kb = await _create_kb(client, headers, user)

    resp = await client.get(
        f"/api/v1/knowledge-bases/{kb['id']}/documents",
        headers=headers,
        params={
            "uploaded_from": "2026-06-01",
            "uploaded_to": "2026-01-01",
        },
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_list_documents_filters_with_pagination(
    client: AsyncClient,
    register_and_login,
) -> None:
    headers, user = await register_and_login(prefix="doc-filter-page")
    kb = await _create_kb(client, headers, user)
    kb_id = uuid.UUID(kb["id"])
    user_id = uuid.UUID(user["id"])

    base = datetime(2026, 5, 1, tzinfo=timezone.utc)
    for i in range(12):
        await _seed_document(
            kb_id=kb_id,
            user_id=user_id,
            filename=f"pdf-{i:02d}.pdf",
            file_type="pdf",
            created_at=base + timedelta(days=i),
        )
    await _seed_document(
        kb_id=kb_id,
        user_id=user_id,
        filename="note.txt",
        file_type="txt",
    )

    page1 = await client.get(
        f"/api/v1/knowledge-bases/{kb['id']}/documents",
        headers=headers,
        params={"file_type": "pdf", "limit": 10, "offset": 0},
    )
    assert page1.status_code == 200
    body1 = page1.json()
    assert body1["total"] == 12
    assert len(body1["items"]) == 10

    page2 = await client.get(
        f"/api/v1/knowledge-bases/{kb['id']}/documents",
        headers=headers,
        params={"file_type": "pdf", "limit": 10, "offset": 10},
    )
    assert page2.status_code == 200
    body2 = page2.json()
    assert body2["total"] == 12
    assert len(body2["items"]) == 2
