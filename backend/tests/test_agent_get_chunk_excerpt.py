"""G3-1.5：get_chunk_excerpt tool · DocumentChunk 包装 · G3-E2 越权 forbidden。"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import SessionLocal
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.enums import DocumentStatus
from app.models.knowledge_base import KnowledgeBase
from app.services.agent.tools.get_chunk_excerpt import (
    NOT_FOUND_SUMMARY,
    build_result_summary,
    run_get_chunk_excerpt,
)
from app.services.agent.tools.scope import AgentToolScope, FORBIDDEN_KB_SUMMARY
from app.services.rag.retrieval import _excerpt
from tests.conftest import create_test_kb


def test_build_result_summary_matches_preview() -> None:
    assert build_result_summary("员工手册.pdf", 12) == "员工手册.pdf p.12 摘录"
    assert build_result_summary("制度.txt", None) == "制度.txt 摘录"


@pytest.mark.asyncio
async def test_get_chunk_excerpt_denies_forbidden_kb_g3_e2() -> None:
    """越权 chunk → ok=false · forbidden · 不抛异常（G3-E2）。"""
    visible_kb = uuid.uuid4()
    forbidden_kb = uuid.uuid4()
    chunk_id = uuid.uuid4()
    doc_id = uuid.uuid4()

    chunk = DocumentChunk(
        id=chunk_id,
        document_id=doc_id,
        kb_id=forbidden_kb,
        chunk_index=0,
        content="不可见库内容",
    )
    db = AsyncMock(spec=AsyncSession)
    db.get = AsyncMock(return_value=chunk)
    tool_scope = AgentToolScope(visible_kb_ids=frozenset({visible_kb}))

    result = await run_get_chunk_excerpt(db, tool_scope, chunk_id=chunk_id)

    assert result.ok is False
    assert result.data is None
    assert result.summary == FORBIDDEN_KB_SUMMARY
    db.get.assert_awaited_once_with(DocumentChunk, chunk_id)


@pytest.mark.asyncio
async def test_get_chunk_excerpt_not_found() -> None:
    db = AsyncMock(spec=AsyncSession)
    db.get = AsyncMock(return_value=None)
    tool_scope = AgentToolScope(visible_kb_ids=frozenset({uuid.uuid4()}))

    result = await run_get_chunk_excerpt(db, tool_scope, chunk_id=uuid.uuid4())

    assert result.ok is False
    assert result.data is None
    assert result.summary == NOT_FOUND_SUMMARY


@pytest.mark.asyncio
async def test_get_chunk_excerpt_success_maps_citation_fields() -> None:
    kb_id = uuid.uuid4()
    doc_id = uuid.uuid4()
    chunk_id = uuid.uuid4()
    content = "员工年假规定为 10 天，需提前申请"

    chunk = DocumentChunk(
        id=chunk_id,
        document_id=doc_id,
        kb_id=kb_id,
        chunk_index=0,
        page_number=12,
        section_title="1.1 年假",
        content=content,
    )
    doc = Document(
        id=doc_id,
        kb_id=kb_id,
        filename="员工手册.pdf",
        file_type="pdf",
        file_size=100,
        storage_path="/tmp/handbook.pdf",
        status=DocumentStatus.completed,
        chunk_count=1,
        uploaded_by=uuid.uuid4(),
    )
    kb = KnowledgeBase(
        id=kb_id,
        name="制度库",
        owner_user_id=uuid.uuid4(),
    )

    async def get_side_effect(model, pk):  # noqa: ANN001
        if model is DocumentChunk and pk == chunk_id:
            return chunk
        if model is Document and pk == doc_id:
            return doc
        if model is KnowledgeBase and pk == kb_id:
            return kb
        return None

    db = AsyncMock(spec=AsyncSession)
    db.get = AsyncMock(side_effect=get_side_effect)
    tool_scope = AgentToolScope(visible_kb_ids=frozenset({kb_id}))

    result = await run_get_chunk_excerpt(db, tool_scope, chunk_id=chunk_id)

    assert result.ok is True
    assert result.data is not None
    assert result.summary == "员工手册.pdf p.12 摘录"
    data = result.data
    assert data.chunk_id == chunk_id
    assert data.document_id == doc_id
    assert data.doc_name == "员工手册.pdf"
    assert data.page == 12
    assert data.section_title == "1.1 年假"
    assert data.excerpt == _excerpt(content)
    assert data.kb_id == kb_id
    assert data.kb_name == "制度库"


async def _seed_chunk(
    db: AsyncSession,
    *,
    kb_id: uuid.UUID,
    uploaded_by: uuid.UUID,
    filename: str,
    content: str,
    page_number: int | None = 12,
    section_title: str | None = "1.1 年假",
) -> uuid.UUID:
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
            page_number=page_number,
            section_title=section_title,
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
    return chunk_id


@pytest.mark.asyncio
async def test_get_chunk_excerpt_integration_reads_seeded_chunk(
    client: AsyncClient,
    register_and_login,
) -> None:
    """真实 DocumentChunk 路径 · visible kb 可读摘录。"""
    headers, user = await register_and_login(prefix="g3-chunk-excerpt")
    kb = await create_test_kb(client, headers, user, name="G3 摘录库")
    kb_id = uuid.UUID(kb["id"])
    user_id = uuid.UUID(user["id"])
    marker = "G3_CHUNK_EXCERPT_MARKER"
    content = f"{marker} 员工年假规定为 10 天"

    async with SessionLocal() as db:
        chunk_id = await _seed_chunk(
            db,
            kb_id=kb_id,
            uploaded_by=user_id,
            filename="handbook.txt",
            content=content,
        )
        await db.commit()

        tool_scope = AgentToolScope(visible_kb_ids=frozenset({kb_id}))
        result = await run_get_chunk_excerpt(db, tool_scope, chunk_id=chunk_id)

    assert result.ok is True
    assert result.data is not None
    assert marker in result.data.excerpt
    assert result.data.kb_id == kb_id
    assert result.data.kb_name == "G3 摘录库"
    assert result.data.doc_name == "handbook.txt"
    assert result.data.page == 12
    assert result.data.section_title == "1.1 年假"


@pytest.mark.asyncio
async def test_get_chunk_excerpt_integration_denies_invisible_kb_g3_e2(
    client: AsyncClient,
    register_and_login,
) -> None:
    """seed 真实 chunk · visible_kb_ids 不含其 kb → forbidden（G3-E2）。"""
    headers, user = await register_and_login(prefix="g3-chunk-deny")
    kb = await create_test_kb(client, headers, user, name="G3 越权库")
    kb_id = uuid.UUID(kb["id"])
    user_id = uuid.UUID(user["id"])

    async with SessionLocal() as db:
        chunk_id = await _seed_chunk(
            db,
            kb_id=kb_id,
            uploaded_by=user_id,
            filename="secret.txt",
            content="G3_FORBIDDEN_CHUNK_CONTENT",
        )
        await db.commit()

        other_visible = uuid.uuid4()
        tool_scope = AgentToolScope(visible_kb_ids=frozenset({other_visible}))
        result = await run_get_chunk_excerpt(db, tool_scope, chunk_id=chunk_id)

    assert result.ok is False
    assert result.data is None
    assert result.summary == FORBIDDEN_KB_SUMMARY
