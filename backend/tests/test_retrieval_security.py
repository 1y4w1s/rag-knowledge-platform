"""Plan-RAG R3-4：kb_id + workspace 检索安全复核（R3-2 rerank 后）。"""

from __future__ import annotations

import uuid
from pathlib import Path
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.enums import DocumentStatus
from app.services.ingestion.pipeline import process_document_ingestion
from app.services.rag.retrieval import _enforce_kb_scope, retrieve_chunks
from app.services.rag.types import RetrievedChunk
from tests.conftest import create_test_kb as _create_kb

FIXTURES = Path(__file__).parent / "fixtures"
GOLDEN_MD = FIXTURES / "golden_handbook.md"


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


@pytest.fixture
def upload_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    return tmp_path


@pytest.fixture
def rerank_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """显式开启 rerank（R3-2 后 SA-3 复核）。"""
    monkeypatch.setattr(settings, "rerank_enabled", True)
    monkeypatch.setattr(settings, "rerank_provider", "mock")


def _make_chunk(*, kb_id: UUID, content: str) -> RetrievedChunk:
    return RetrievedChunk(
        kb_id=kb_id,
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        doc_name="test.md",
        content=content,
        page_number=1,
        section_title=None,
        heading_path=None,
        similarity=0.5,
    )


def test_enforce_kb_scope_drops_foreign_chunks() -> None:
    kb_a = uuid.uuid4()
    kb_b = uuid.uuid4()
    chunks = [
        _make_chunk(kb_id=kb_a, content="合法片段"),
        _make_chunk(kb_id=kb_b, content="跨库泄漏"),
        _make_chunk(kb_id=kb_a, content="另一条合法"),
    ]

    scoped = _enforce_kb_scope(chunks, kb_id=kb_a)

    assert len(scoped) == 2
    assert all(c.kb_id == kb_a for c in scoped)
    assert all("跨库" not in c.content for c in scoped)


@pytest.mark.asyncio
async def test_sa3_kb_isolation_with_rerank_enabled(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
    tmp_path: Path,
    rerank_enabled: None,
) -> None:
    """SA-3 + R3-2：rerank 开启时检索结果 kb_id 仍须与请求一致。"""
    headers, user = await register_and_login(prefix="sec-sa3-rerank")
    user_id = uuid.UUID(user["id"])

    kb_a = await _create_kb(client, headers, user, name="安全库 A")
    kb_b = await _create_kb(client, headers, user, name="安全库 B")
    kb_a_id = UUID(kb_a["id"])
    kb_b_id = UUID(kb_b["id"])

    await _ingest_fixture(
        kb_id=kb_a_id,
        user_id=user_id,
        source=GOLDEN_MD,
        file_type="md",
        upload_dir=upload_dir,
    )

    secret = tmp_path / "secret.txt"
    secret.write_text("SECRET_ORG_MARKER 唯一标识符", encoding="utf-8")
    await _ingest_fixture(
        kb_id=kb_b_id,
        user_id=user_id,
        source=secret,
        file_type="txt",
        upload_dir=upload_dir,
    )

    async with SessionLocal() as db:
        chunks = await retrieve_chunks(
            db,
            kb_id=kb_a_id,
            query="SECRET_ORG_MARKER 在哪里",
        )

    assert all(c.kb_id == kb_a_id for c in chunks)
    assert all("SECRET_ORG_MARKER" not in c.content for c in chunks)

    async with SessionLocal() as db:
        chunk_ids = [c.chunk_id for c in chunks]
        if chunk_ids:
            rows = (
                await db.execute(
                    select(DocumentChunk).where(DocumentChunk.id.in_(chunk_ids))
                )
            ).scalars().all()
            assert all(row.kb_id == kb_a_id for row in rows)


@pytest.mark.asyncio
async def test_workspace_personal_kb_excludes_org_secret(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
    tmp_path: Path,
    rerank_enabled: None,
) -> None:
    """企业用户：查 personal 库不得泄漏 organization 库正文（workspace 隔离复核）。"""
    headers, user = await register_and_login(
        prefix="sec-ws-personal",
        account_type="enterprise",
        org_name="安全隔离公司",
    )
    user_id = uuid.UUID(user["id"])

    personal_kb = await _create_kb(
        client, headers, user, name="个人空间库", workspace_kind="personal"
    )
    org_kb = await _create_kb(
        client, headers, user, name="团队空间库", workspace_kind="organization"
    )
    personal_id = UUID(personal_kb["id"])
    org_id = UUID(org_kb["id"])

    await _ingest_fixture(
        kb_id=personal_id,
        user_id=user_id,
        source=GOLDEN_MD,
        file_type="md",
        upload_dir=upload_dir,
    )

    org_secret = tmp_path / "org_secret.txt"
    org_secret.write_text("WORKSPACE_ORG_SECRET 团队专属", encoding="utf-8")
    await _ingest_fixture(
        kb_id=org_id,
        user_id=user_id,
        source=org_secret,
        file_type="txt",
        upload_dir=upload_dir,
    )

    async with SessionLocal() as db:
        chunks = await retrieve_chunks(
            db,
            kb_id=personal_id,
            query="WORKSPACE_ORG_SECRET 团队",
        )

    assert all(c.kb_id == personal_id for c in chunks)
    assert all("WORKSPACE_ORG_SECRET" not in c.content for c in chunks)
