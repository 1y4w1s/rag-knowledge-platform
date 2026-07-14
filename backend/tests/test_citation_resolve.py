"""Plan-3E-3 / EW-D3：引用失效解析测试。"""

from __future__ import annotations

import json
import re
import uuid
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import delete

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.enums import DocumentStatus
from app.services.ingestion.pipeline import process_document_ingestion
from tests.conftest import create_test_kb as _create_kb

FIXTURES = Path(__file__).parent / "fixtures"
GOLDEN_MD = FIXTURES / "golden_handbook.md"


def _parse_sse_events(raw: str) -> list[tuple[str, dict]]:
    events: list[tuple[str, dict]] = []
    blocks = re.split(r"\n\n+", raw.strip())
    for block in blocks:
        if not block.strip():
            continue
        event_name = "message"
        data_str = ""
        for line in block.splitlines():
            if line.startswith("event: "):
                event_name = line.removeprefix("event: ").strip()
            elif line.startswith("data: "):
                data_str = line.removeprefix("data: ").strip()
        if data_str:
            events.append((event_name, json.loads(data_str)))
    return events


async def _ingest_fixture(
    *,
    kb_id: uuid.UUID,
    user_id: uuid.UUID,
    source: Path,
    file_type: str,
    upload_dir: Path,
) -> Document:
    doc_id = uuid.uuid4()
    storage_dir = upload_dir / str(kb_id) / str(doc_id)
    storage_dir.mkdir(parents=True, exist_ok=True)
    storage_path = storage_dir / f"{uuid.uuid4()}.{file_type}"
    storage_path.write_bytes(source.read_bytes())

    async with SessionLocal() as db:
        doc = Document(
            id=doc_id,
            kb_id=kb_id,
            filename=source.name,
            file_type=file_type,
            file_size=storage_path.stat().st_size,
            storage_path=str(storage_path),
            status=DocumentStatus.queued,
            uploaded_by=user_id,
        )
        db.add(doc)
        await db.commit()

    await process_document_ingestion(doc_id)

    async with SessionLocal() as db:
        row = await db.get(Document, doc_id)
        assert row is not None
        assert row.status == DocumentStatus.completed
        return row


async def _chat_citations(
    client: AsyncClient,
    headers: dict[str, str],
    kb_id: str,
) -> list[dict]:
    async with client.stream(
        "POST",
        f"/api/v1/knowledge-bases/{kb_id}/chat",
        headers=headers,
        json={"message": "员工年假有几天？"},
    ) as resp:
        body = await resp.aread()
        assert resp.status_code == 200
        events = _parse_sse_events(body.decode("utf-8"))
    return [data for name, data in events if name == "citation"]


@pytest.fixture
def upload_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    return tmp_path


@pytest.mark.asyncio
async def test_resolve_citation_available(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
) -> None:
    headers, user = await register_and_login(prefix="cite-avail")
    kb = await _create_kb(client, headers, user)
    await _ingest_fixture(
        kb_id=uuid.UUID(kb["id"]),
        user_id=uuid.UUID(user["id"]),
        source=GOLDEN_MD,
        file_type="md",
        upload_dir=upload_dir,
    )

    citations = await _chat_citations(client, headers, kb["id"])
    assert citations
    cite = citations[0]

    resp = await client.get(
        f"/api/v1/knowledge-bases/{kb['id']}/citations/resolve",
        headers=headers,
        params={
            "document_id": cite["document_id"],
            "chunk_id": cite["chunk_id"],
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["source_status"] == "available"
    assert body["doc_name"] == GOLDEN_MD.name


@pytest.mark.asyncio
async def test_resolve_citation_after_document_deleted(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
) -> None:
    headers, user = await register_and_login(prefix="cite-del")
    kb = await _create_kb(client, headers, user)
    doc = await _ingest_fixture(
        kb_id=uuid.UUID(kb["id"]),
        user_id=uuid.UUID(user["id"]),
        source=GOLDEN_MD,
        file_type="md",
        upload_dir=upload_dir,
    )

    citations = await _chat_citations(client, headers, kb["id"])
    assert citations
    cite = citations[0]

    delete_resp = await client.delete(
        f"/api/v1/knowledge-bases/{kb['id']}/documents/{doc.id}",
        headers=headers,
    )
    assert delete_resp.status_code == 204

    resolve_resp = await client.get(
        f"/api/v1/knowledge-bases/{kb['id']}/citations/resolve",
        headers=headers,
        params={
            "document_id": cite["document_id"],
            "chunk_id": cite["chunk_id"],
        },
    )
    assert resolve_resp.status_code == 200
    body = resolve_resp.json()
    assert body["source_status"] == "document_deleted"
    assert body["doc_name"] is None

    preview_resp = await client.get(
        f"/api/v1/knowledge-bases/{kb['id']}/documents/{cite['document_id']}/preview",
        headers=headers,
    )
    assert preview_resp.status_code == 404


@pytest.mark.asyncio
async def test_resolve_citation_chunk_stale(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
) -> None:
    headers, user = await register_and_login(prefix="cite-stale")
    kb = await _create_kb(client, headers, user)
    doc = await _ingest_fixture(
        kb_id=uuid.UUID(kb["id"]),
        user_id=uuid.UUID(user["id"]),
        source=GOLDEN_MD,
        file_type="md",
        upload_dir=upload_dir,
    )

    citations = await _chat_citations(client, headers, kb["id"])
    assert citations
    cite = citations[0]

    async with SessionLocal() as db:
        await db.execute(
            delete(DocumentChunk).where(
                DocumentChunk.id == uuid.UUID(cite["chunk_id"])
            )
        )
        await db.commit()

    resp = await client.get(
        f"/api/v1/knowledge-bases/{kb['id']}/citations/resolve",
        headers=headers,
        params={
            "document_id": cite["document_id"],
            "chunk_id": cite["chunk_id"],
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["source_status"] == "chunk_stale"
    assert body["doc_name"] == doc.filename
