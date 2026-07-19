"""G3-1.3：semantic_search tool · retrieve_* 包装 · G3-E9 库内默认 kb。"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock
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
from app.schemas.auth import UserPublic
from app.services.agent.tools.scope import AgentToolScope, FORBIDDEN_KB_SUMMARY
from app.services.agent.tools.semantic_search import (
    AGENT_DEFAULT_TOP_K,
    AGENT_MAX_TOP_K,
    build_result_summary,
    normalize_top_k,
    run_semantic_search,
)
from app.services.rag.types import RetrievedChunk
from app.services.workspace.scope import WorkspaceKind, WorkspaceScope, resolve_workspace
from tests.conftest import create_test_kb, workspace_query


def _personal_workspace(user_id: uuid.UUID | None = None) -> WorkspaceScope:
    return WorkspaceScope(
        kind=WorkspaceKind.personal,
        user_id=user_id or uuid.uuid4(),
        org_id=None,
    )


def _sample_chunk(*, kb_id: UUID, kb_name: str | None = None) -> RetrievedChunk:
    return RetrievedChunk(
        kb_id=kb_id,
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        doc_name="handbook.md",
        content="员工年假规定为 10 天",
        page_number=2,
        section_title="1.1 年假",
        heading_path=None,
        similarity=0.91,
        kb_name=kb_name,
    )


def test_normalize_top_k_defaults_and_caps() -> None:
    assert normalize_top_k(None) == AGENT_DEFAULT_TOP_K
    assert normalize_top_k(3) == 3
    assert normalize_top_k(10) == AGENT_MAX_TOP_K
    assert normalize_top_k(0) == 1


def test_build_result_summary_matches_preview() -> None:
    assert build_result_summary(0) == "无命中"
    assert build_result_summary(3) == "命中 3 条"


@pytest.fixture
def rerank_mock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "rerank_enabled", True)
    monkeypatch.setattr(settings, "rerank_provider", "mock")


@pytest.mark.asyncio
async def test_semantic_search_denies_forbidden_kb_g3_e2(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    retrieve_chunks = AsyncMock()
    monkeypatch.setattr(
        "app.services.agent.tools.semantic_search.retrieve_chunks",
        retrieve_chunks,
    )
    visible = uuid.uuid4()
    forbidden = uuid.uuid4()
    tool_scope = AgentToolScope(visible_kb_ids=frozenset({visible}))

    async with SessionLocal() as db:
        result = await run_semantic_search(
            db,
            _personal_workspace(),
            tool_scope,
            query="年假",
            kb_ids=[visible, forbidden],
        )

    assert result.ok is False
    assert result.data is None
    assert result.summary == FORBIDDEN_KB_SUMMARY
    retrieve_chunks.assert_not_called()


@pytest.mark.asyncio
async def test_semantic_search_kb_default_uses_retrieve_chunks_g3_e9(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    default_kb = uuid.uuid4()
    chunk = _sample_chunk(kb_id=default_kb)
    retrieve_chunks = AsyncMock(return_value=[chunk])
    retrieve_workspace = AsyncMock(return_value=[])
    monkeypatch.setattr(
        "app.services.agent.tools.semantic_search.retrieve_chunks",
        retrieve_chunks,
    )
    monkeypatch.setattr(
        "app.services.agent.tools.semantic_search.retrieve_workspace_chunks",
        retrieve_workspace,
    )
    tool_scope = AgentToolScope(
        visible_kb_ids=frozenset({default_kb}),
        default_kb_id=default_kb,
    )

    async with SessionLocal() as db:
        result = await run_semantic_search(
            db,
            _personal_workspace(),
            tool_scope,
            query="年假",
        )

    assert result.ok is True
    assert result.data is not None
    assert result.summary == "命中 1 条"
    retrieve_chunks.assert_awaited_once()
    assert retrieve_chunks.await_args.kwargs["kb_id"] == default_kb
    retrieve_workspace.assert_not_called()


@pytest.mark.asyncio
async def test_semantic_search_workspace_uses_retrieve_workspace_chunks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    kb_id = uuid.uuid4()
    chunk = _sample_chunk(kb_id=kb_id, kb_name="人事库")
    retrieve_chunks = AsyncMock(return_value=[])
    retrieve_workspace = AsyncMock(return_value=[chunk])
    monkeypatch.setattr(
        "app.services.agent.tools.semantic_search.retrieve_chunks",
        retrieve_chunks,
    )
    monkeypatch.setattr(
        "app.services.agent.tools.semantic_search.retrieve_workspace_chunks",
        retrieve_workspace,
    )
    tool_scope = AgentToolScope(visible_kb_ids=None)

    async with SessionLocal() as db:
        result = await run_semantic_search(
            db,
            _personal_workspace(),
            tool_scope,
            query="年假",
        )

    assert result.ok is True
    assert result.data is not None
    assert len(result.data.hits) == 1
    hit = result.data.hits[0]
    assert hit.kb_name == "人事库"
    assert hit.excerpt == "员工年假规定为 10 天"
    assert hit.page == 2
    assert hit.section_title == "1.1 年假"
    retrieve_workspace.assert_awaited_once()
    retrieve_chunks.assert_not_called()


@pytest.mark.asyncio
async def test_semantic_search_single_kb_arg_uses_retrieve_chunks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    kb_id = uuid.uuid4()
    chunk = _sample_chunk(kb_id=kb_id)
    retrieve_chunks = AsyncMock(return_value=[chunk])
    retrieve_workspace = AsyncMock(return_value=[])
    monkeypatch.setattr(
        "app.services.agent.tools.semantic_search.retrieve_chunks",
        retrieve_chunks,
    )
    monkeypatch.setattr(
        "app.services.agent.tools.semantic_search.retrieve_workspace_chunks",
        retrieve_workspace,
    )
    tool_scope = AgentToolScope(visible_kb_ids=frozenset({kb_id}))

    async with SessionLocal() as db:
        result = await run_semantic_search(
            db,
            _personal_workspace(),
            tool_scope,
            query="年假",
            kb_ids=[kb_id],
        )

    assert result.ok is True
    retrieve_chunks.assert_awaited_once()
    retrieve_workspace.assert_not_called()


async def _seed_chunk(
    db: AsyncSession,
    *,
    kb_id: uuid.UUID,
    uploaded_by: uuid.UUID,
    filename: str,
    content: str,
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
async def test_semantic_search_integration_hits_seeded_content(
    client: AsyncClient,
    register_and_login,
    rerank_mock: None,
) -> None:
    """真实 retrieve_chunks 路径 · 库内默认 kb（G3-E9）。"""
    headers, user = await register_and_login(prefix="g3-semantic-kb")
    kb = await create_test_kb(client, headers, user, name="年假制度库")
    kb_id = uuid.UUID(kb["id"])
    user_id = uuid.UUID(user["id"])
    marker = "G3_SEMANTIC_KB_MARKER"

    async with SessionLocal() as db:
        await _seed_chunk(
            db,
            kb_id=kb_id,
            uploaded_by=user_id,
            filename="leave.txt",
            content=f"{marker} 员工年假规定为 10 天，需提前申请",
        )
        await db.commit()

        current_user = UserPublic.model_validate(user)
        workspace = await resolve_workspace(db, current_user, "personal")
        tool_scope = AgentToolScope(
            visible_kb_ids=frozenset({kb_id}),
            default_kb_id=kb_id,
        )
        result = await run_semantic_search(
            db,
            workspace,
            tool_scope,
            query=marker,
        )

    assert result.ok is True
    assert result.data is not None
    assert result.data.retrieval_ms >= 0
    assert len(result.data.hits) >= 1
    hit = result.data.hits[0]
    assert hit.kb_id == kb_id
    assert hit.kb_name == "年假制度库"
    assert "年假" in hit.excerpt


@pytest.mark.asyncio
async def test_semantic_search_workspace_integration(
    client: AsyncClient,
    register_and_login,
    rerank_mock: None,
) -> None:
    headers, user = await register_and_login(prefix="g3-semantic-ws")
    kb = await create_test_kb(client, headers, user, name="跨库检索库")
    kb_id = uuid.UUID(kb["id"])
    user_id = uuid.UUID(user["id"])
    marker = "G3_SEMANTIC_WS_MARKER"

    async with SessionLocal() as db:
        await _seed_chunk(
            db,
            kb_id=kb_id,
            uploaded_by=user_id,
            filename="policy.txt",
            content=f"{marker} 远程办公每周最多 2 天",
        )
        await db.commit()

        current_user = UserPublic.model_validate(user)
        workspace = await resolve_workspace(
            db,
            current_user,
            workspace_query(user)["workspace"],
        )
        result = await run_semantic_search(
            db,
            workspace,
            AgentToolScope(visible_kb_ids=None),
            query=marker,
        )

    assert result.ok is True
    assert result.data is not None
    assert len(result.data.hits) >= 1
    assert result.data.hits[0].kb_name == "跨库检索库"


@pytest.mark.asyncio
async def test_semantic_search_respects_top_k_cap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    kb_id = uuid.uuid4()
    chunks = [_sample_chunk(kb_id=kb_id) for _ in range(5)]
    retrieve_chunks = AsyncMock(return_value=chunks)
    monkeypatch.setattr(
        "app.services.agent.tools.semantic_search.retrieve_chunks",
        retrieve_chunks,
    )
    tool_scope = AgentToolScope(
        visible_kb_ids=frozenset({kb_id}),
        default_kb_id=kb_id,
    )

    async with SessionLocal() as db:
        await run_semantic_search(
            db,
            _personal_workspace(),
            tool_scope,
            query="年假",
            top_k=100,
        )

    assert retrieve_chunks.await_args.kwargs["top_k"] == AGENT_MAX_TOP_K
