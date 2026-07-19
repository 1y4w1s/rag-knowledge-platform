"""G-1 Wave 1：跨库 retrieve_workspace_chunks + diversity + workspace citation。"""

from __future__ import annotations

import uuid
from pathlib import Path
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.enums import DocumentStatus
from app.schemas.chat import CitationPayload
from app.services.ingestion.pipeline import process_document_ingestion
from app.services.org.scope import resolve_org_scope
from app.services.rag.diversity import apply_kb_diversity
from app.services.rag.retrieval import (
    chunk_to_citation,
    retrieve_workspace_chunks,
    workspace_chunk_to_citation,
)
from app.services.rag.types import RetrievedChunk
from app.services.workspace.scope import WorkspaceKind, WorkspaceScope
from tests.conftest import create_test_kb as _create_kb
from tests.fixtures.org_isolation import OrgIsolationFixture

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


async def _seed_chunk(
    db: AsyncSession,
    *,
    kb_id: uuid.UUID,
    uploaded_by: uuid.UUID,
    filename: str,
    content: str,
) -> None:
    doc_id = uuid.uuid4()
    chunk_id = uuid.uuid4()
    db.add(
        Document(
            id=doc_id,
            kb_id=kb_id,
            filename=filename,
            file_type="txt",
            file_size=len(content),
            storage_path=f"/tmp/{kb_id}/{doc_id}.txt",
            status=DocumentStatus.completed,
            chunk_count=1,
            uploaded_by=uploaded_by,
        )
    )
    db.add(
        DocumentChunk(
            id=chunk_id,
            document_id=doc_id,
            kb_id=kb_id,
            chunk_index=0,
            content=content,
            embedding=None,
        )
    )
    await db.flush()
    await db.execute(
        text(
            "UPDATE document_chunks SET content_tsv = to_tsvector('simple', :src) "
            "WHERE id = :chunk_id"
        ),
        {"src": content, "chunk_id": chunk_id},
    )


def _chunk(
    *,
    kb_id: UUID,
    kb_name: str,
    content: str,
    chunk_id: UUID | None = None,
) -> RetrievedChunk:
    return RetrievedChunk(
        kb_id=kb_id,
        chunk_id=chunk_id or uuid.uuid4(),
        document_id=uuid.uuid4(),
        doc_name="doc.txt",
        content=content,
        page_number=1,
        section_title=None,
        heading_path=None,
        similarity=0.5,
        kb_name=kb_name,
    )


@pytest.fixture
def upload_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    return tmp_path


@pytest.fixture
def rerank_mock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "rerank_enabled", True)
    monkeypatch.setattr(settings, "rerank_provider", "mock")


def test_apply_kb_diversity_ensures_each_kb_represented() -> None:
    """T-ask-6 核心：两库同主题时 Top-5 须含不同 kb。"""
    kb_a = uuid.uuid4()
    kb_b = uuid.uuid4()
    query = "年假规定 10 天"
    chunks = [
        _chunk(kb_id=kb_a, kb_name="库 A", content=f"年假规定 10 天 A{i}")
        for i in range(5)
    ] + [
        _chunk(kb_id=kb_b, kb_name="库 B", content="年假规定 10 天 B0"),
    ]

    result = apply_kb_diversity(chunks, query, top_k=5)

    assert len(result) == 5
    kb_names = {c.kb_name for c in result}
    assert len(kb_names) >= 2
    assert "库 A" in kb_names
    assert "库 B" in kb_names


def test_apply_kb_diversity_skips_single_kb() -> None:
    kb_a = uuid.uuid4()
    query = "年假规定"
    chunks = [
        _chunk(kb_id=kb_a, kb_name="仅 A", content=f"年假规定 片段{i}")
        for i in range(5)
    ]

    result = apply_kb_diversity(chunks, query, top_k=5)

    assert len(result) == 5
    assert all(c.kb_id == kb_a for c in result)


def test_workspace_chunk_to_citation_includes_kb_fields() -> None:
    kb_id = uuid.uuid4()
    chunk = _chunk(kb_id=kb_id, kb_name="研发库", content="年假 10 天")
    raw = workspace_chunk_to_citation(chunk)

    assert raw["kb_id"] == str(kb_id)
    assert raw["kb_name"] == "研发库"
    payload = CitationPayload.model_validate(
        {
            **raw,
            "chunk_id": uuid.UUID(raw["chunk_id"]),
            "document_id": uuid.UUID(raw["document_id"]),
            "kb_id": kb_id,
        }
    )
    assert payload.kb_name == "研发库"


def test_chunk_to_citation_unchanged_without_kb_fields() -> None:
    chunk = _chunk(kb_id=uuid.uuid4(), kb_name="忽略", content="正文")
    raw = chunk_to_citation(chunk)
    assert "kb_id" not in raw
    assert "kb_name" not in raw
    CitationPayload.model_validate(
        {
            **raw,
            "chunk_id": uuid.UUID(raw["chunk_id"]),
            "document_id": uuid.UUID(raw["document_id"]),
        }
    )


@pytest.mark.asyncio
async def test_personal_workspace_two_kbs_hits_only_target(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
    tmp_path: Path,
    rerank_mock: None,
) -> None:
    """personal 两库：问 A 专属内容仅命中 A。"""
    headers, user = await register_and_login(prefix="ws-personal-2kb")
    user_id = uuid.UUID(user["id"])

    kb_a = await _create_kb(client, headers, user, name="WS 库 A", workspace_kind="personal")
    kb_b = await _create_kb(client, headers, user, name="WS 库 B", workspace_kind="personal")
    kb_a_id = UUID(kb_a["id"])
    kb_b_id = UUID(kb_b["id"])

    await _ingest_fixture(
        kb_id=kb_a_id,
        user_id=user_id,
        source=GOLDEN_MD,
        file_type="md",
        upload_dir=upload_dir,
    )

    secret = tmp_path / "b-only.txt"
    secret.write_text("WS_B_ONLY_MARKER 仅 B 库可见", encoding="utf-8")
    await _ingest_fixture(
        kb_id=kb_b_id,
        user_id=user_id,
        source=secret,
        file_type="txt",
        upload_dir=upload_dir,
    )

    scope = WorkspaceScope(
        kind=WorkspaceKind.personal,
        user_id=user_id,
        org_id=None,
    )

    async with SessionLocal() as db:
        hits = await retrieve_workspace_chunks(
            db,
            query="员工年假有多少天",
            scope=scope,
            org_scope=None,
        )

    assert hits
    assert all(h.kb_id == kb_a_id for h in hits)
    assert all(h.kb_name == "WS 库 A" for h in hits)
    assert all("WS_B_ONLY_MARKER" not in h.content for h in hits)


@pytest.mark.asyncio
async def test_org_member_excludes_sibling_department_chunks(
    org_iso: OrgIsolationFixture,
    rerank_mock: None,
) -> None:
    """团队 member 检索不得含兄弟部门库 chunk。"""
    async with SessionLocal() as db:
        await _seed_chunk(
            db,
            kb_id=org_iso.mkt_kb_id,
            uploaded_by=org_iso.mkt_member.id,
            filename="mkt-ws.txt",
            content="市场部工作区关键词 alpha 机密",
        )
        await _seed_chunk(
            db,
            kb_id=org_iso.rd_kb_id,
            uploaded_by=org_iso.rd_member.id,
            filename="rd-ws.txt",
            content="研发部工作区关键词 beta 内容",
        )
        await db.commit()

        org_scope = await resolve_org_scope(db, org_iso.rd_member)
        scope = WorkspaceScope(
            kind=WorkspaceKind.organization,
            user_id=org_iso.rd_member.id,
            org_id=org_iso.org_id,
        )

        hits = await retrieve_workspace_chunks(
            db,
            query="市场部工作区关键词 alpha",
            scope=scope,
            org_scope=org_scope,
        )

    assert all(h.kb_id != org_iso.mkt_kb_id for h in hits)
    assert all("市场部工作区" not in h.content for h in hits)

    async with SessionLocal() as db:
        org_scope = await resolve_org_scope(db, org_iso.rd_member)
        scope = WorkspaceScope(
            kind=WorkspaceKind.organization,
            user_id=org_iso.rd_member.id,
            org_id=org_iso.org_id,
        )
        rd_hits = await retrieve_workspace_chunks(
            db,
            query="研发部工作区关键词 beta",
            scope=scope,
            org_scope=org_scope,
        )

    assert rd_hits
    assert all(h.kb_id == org_iso.rd_kb_id for h in rd_hits)


@pytest.mark.asyncio
async def test_workspace_diversity_two_kbs_same_topic(
    org_iso: OrgIsolationFixture,
    rerank_mock: None,
) -> None:
    """两库同主题 → 引用 kb_name 可不同（T-ask-6）。"""
    async with SessionLocal() as db:
        for i in range(4):
            await _seed_chunk(
                db,
                kb_id=org_iso.rd_kb_id,
                uploaded_by=org_iso.rd_member.id,
                filename=f"rd-leave-{i}.txt",
                content=f"年假统一主题 研发库 片段{i} 10天",
            )
        await _seed_chunk(
            db,
            kb_id=org_iso.public_kb_id,
            uploaded_by=org_iso.owner.id,
            filename="public-leave.txt",
            content="年假统一主题 公共库 片段 10天",
        )
        await db.commit()

        org_scope = await resolve_org_scope(db, org_iso.rd_member)
        scope = WorkspaceScope(
            kind=WorkspaceKind.organization,
            user_id=org_iso.rd_member.id,
            org_id=org_iso.org_id,
        )
        hits = await retrieve_workspace_chunks(
            db,
            query="年假统一主题 10天",
            scope=scope,
            org_scope=org_scope,
        )

    assert hits
    assert len(hits) <= 5
    kb_ids = {h.kb_id for h in hits}
    assert len(kb_ids) >= 2
    kb_names = {h.kb_name for h in hits if h.kb_name}
    assert len(kb_names) >= 2
