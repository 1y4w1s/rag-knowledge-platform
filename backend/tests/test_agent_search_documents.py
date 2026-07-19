"""G3-1.4：search_documents tool · filename/content 包装 · EW-E1 scope。"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import SessionLocal
from app.models.enums import DocumentStatus
from app.schemas.auth import UserPublic
from app.schemas.search import SearchDocumentItem, SearchDocumentsResponse
from app.services.agent.tools.search_documents import (
    DEFAULT_MODE,
    build_result_summary,
    normalize_mode,
    run_search_documents,
)
from app.services.org.scope import resolve_org_scope_for_workspace
from app.services.workspace.scope import WorkspaceKind, WorkspaceScope, resolve_workspace
from tests.conftest import create_test_kb, workspace_query
from tests.test_search_documents import _search, _seed_document


def _personal_workspace(user_id: uuid.UUID | None = None) -> WorkspaceScope:
    return WorkspaceScope(
        kind=WorkspaceKind.personal,
        user_id=user_id or uuid.uuid4(),
        org_id=None,
    )


def test_normalize_mode_defaults_and_fallback() -> None:
    assert normalize_mode(None) == DEFAULT_MODE
    assert normalize_mode("filename") == "filename"
    assert normalize_mode("content") == "content"
    assert normalize_mode("invalid") == DEFAULT_MODE


def test_build_result_summary_matches_preview() -> None:
    assert build_result_summary(0, "filename") == "无命中"
    assert build_result_summary(2, "filename") == "文件名匹配 2 篇"
    assert build_result_summary(1, "content") == "正文匹配 1 篇"


@pytest.mark.asyncio
async def test_search_documents_rejects_empty_query() -> None:
    async with SessionLocal() as db:
        result = await run_search_documents(
            db,
            _personal_workspace(),
            query="   ",
        )

    assert result.ok is False
    assert result.data is None
    assert result.summary == "搜索关键词不能为空"


@pytest.mark.asyncio
async def test_search_documents_filename_mode_uses_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    kb_id = uuid.uuid4()
    doc_id = uuid.uuid4()
    search_by_filename = AsyncMock(
        return_value=SearchDocumentsResponse(
            items=[
                SearchDocumentItem(
                    doc_id=doc_id,
                    filename="采购合同.pdf",
                    file_type="pdf",
                    status=DocumentStatus.completed,
                    kb_id=kb_id,
                    kb_name="合同库",
                    created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                )
            ],
            query="合同",
            total=1,
            mode="filename",
        )
    )
    search_by_content = AsyncMock()
    monkeypatch.setattr(
        "app.services.agent.tools.search_documents.search_documents_by_filename",
        search_by_filename,
    )
    monkeypatch.setattr(
        "app.services.agent.tools.search_documents.search_documents_by_content",
        search_by_content,
    )

    async with SessionLocal() as db:
        result = await run_search_documents(
            db,
            _personal_workspace(),
            query="合同",
        )

    assert result.ok is True
    assert result.data is not None
    assert result.summary == "文件名匹配 1 篇"
    assert len(result.data.items) == 1
    item = result.data.items[0]
    assert item.document_id == doc_id
    assert item.kb_id == kb_id
    assert item.kb_name == "合同库"
    assert item.filename == "采购合同.pdf"
    assert item.snippet is None
    search_by_filename.assert_awaited_once()
    search_by_content.assert_not_called()


@pytest.mark.asyncio
async def test_search_documents_content_mode_uses_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    kb_id = uuid.uuid4()
    doc_id = uuid.uuid4()
    search_by_content = AsyncMock(
        return_value=SearchDocumentsResponse(
            items=[
                SearchDocumentItem(
                    doc_id=doc_id,
                    filename="手册.pdf",
                    file_type="pdf",
                    status=DocumentStatus.completed,
                    kb_id=kb_id,
                    kb_name="制度库",
                    created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                    snippet="员工<mark>年假</mark>规定",
                )
            ],
            query="年假",
            total=1,
            mode="content",
        )
    )
    search_by_filename = AsyncMock()
    monkeypatch.setattr(
        "app.services.agent.tools.search_documents.search_documents_by_content",
        search_by_content,
    )
    monkeypatch.setattr(
        "app.services.agent.tools.search_documents.search_documents_by_filename",
        search_by_filename,
    )

    async with SessionLocal() as db:
        result = await run_search_documents(
            db,
            _personal_workspace(),
            query="年假",
            mode="content",
        )

    assert result.ok is True
    assert result.data is not None
    assert result.summary == "正文匹配 1 篇"
    assert result.data.items[0].snippet == "员工<mark>年假</mark>规定"
    search_by_content.assert_awaited_once()
    search_by_filename.assert_not_called()


async def _seed_chunk(
    db: AsyncSession,
    *,
    doc,
    content: str,
) -> None:
    from app.models.document_chunk import DocumentChunk

    chunk_id = uuid.uuid4()
    db.add(
        DocumentChunk(
            id=chunk_id,
            document_id=doc.id,
            kb_id=doc.kb_id,
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


@pytest.mark.asyncio
async def test_search_documents_filename_integration(
    client: AsyncClient,
    register_and_login,
) -> None:
    """真实 search_documents_by_filename 路径 · personal workspace。"""
    headers, user = await register_and_login(prefix="g3-search-doc-fn")
    user_id = uuid.UUID(user["id"])
    kb = await create_test_kb(client, headers, user, name="G3 文件名库")
    await _seed_document(
        kb_id=uuid.UUID(kb["id"]),
        user_id=user_id,
        filename="G3_AGENT_FILENAME_MARKER.pdf",
    )

    async with SessionLocal() as db:
        current_user = UserPublic.model_validate(user)
        workspace = await resolve_workspace(db, current_user, "personal")
        result = await run_search_documents(
            db,
            workspace,
            query="G3_AGENT_FILENAME_MARKER",
        )

    assert result.ok is True
    assert result.data is not None
    assert result.data.total >= 1
    assert len(result.data.items) >= 1
    item = result.data.items[0]
    assert item.kb_id == uuid.UUID(kb["id"])
    assert item.kb_name == "G3 文件名库"
    assert "G3_AGENT_FILENAME_MARKER" in item.filename


@pytest.mark.asyncio
async def test_search_documents_content_integration(
    client: AsyncClient,
    register_and_login,
) -> None:
    headers, user = await register_and_login(prefix="g3-search-doc-ct")
    user_id = uuid.UUID(user["id"])
    kb = await create_test_kb(client, headers, user, name="G3 正文库")
    doc = await _seed_document(
        kb_id=uuid.UUID(kb["id"]),
        user_id=user_id,
        filename="hidden-name.pdf",
    )
    marker = "G3_AGENT_CONTENT_MARKER"

    async with SessionLocal() as db:
        await _seed_chunk(db, doc=doc, content=f"{marker} 员工年假规定为 10 天")
        await db.commit()

        current_user = UserPublic.model_validate(user)
        workspace = await resolve_workspace(db, current_user, "personal")
        result = await run_search_documents(
            db,
            workspace,
            query=marker,
            mode="content",
        )

    assert result.ok is True
    assert result.data is not None
    assert result.data.total >= 1
    item = result.data.items[0]
    assert item.document_id == doc.id
    assert item.snippet is not None
    assert marker in item.snippet or "年假" in item.snippet


@pytest.mark.asyncio
async def test_search_documents_org_scope_integration(
    client: AsyncClient,
    register_and_login,
) -> None:
    headers, user = await register_and_login(
        prefix="g3-search-doc-org",
        account_type="enterprise",
        org_name="G3 Search Org",
    )
    user_id = uuid.UUID(user["id"])
    kb = await create_test_kb(client, headers, user, name="G3 团队库")
    await _seed_document(
        kb_id=uuid.UUID(kb["id"]),
        user_id=user_id,
        filename="G3_ORG_SCOPE_MARKER.pdf",
    )

    async with SessionLocal() as db:
        current_user = UserPublic.model_validate(user)
        org_id = str(user["org_id"])
        workspace = await resolve_workspace(db, current_user, org_id)
        org_scope = await resolve_org_scope_for_workspace(db, current_user, workspace)
        result = await run_search_documents(
            db,
            workspace,
            query="G3_ORG_SCOPE_MARKER",
            org_scope=org_scope,
        )

    assert result.ok is True
    assert result.data is not None
    assert result.data.total >= 1


@pytest.mark.asyncio
async def test_search_documents_matches_api_total(
    client: AsyncClient,
    register_and_login,
) -> None:
    """tool 与 GET /search/documents 同 scope 下 total 一致。"""
    headers, user = await register_and_login(prefix="g3-search-doc-parity")
    user_id = uuid.UUID(user["id"])
    kb = await create_test_kb(client, headers, user, name="对齐搜索库")
    await _seed_document(
        kb_id=uuid.UUID(kb["id"]),
        user_id=user_id,
        filename="对齐合同.pdf",
    )

    api_resp = await _search(
        client,
        headers,
        q="对齐合同",
        workspace=workspace_query(user)["workspace"],
    )
    assert api_resp.status_code == 200
    api_body = api_resp.json()

    async with SessionLocal() as db:
        current_user = UserPublic.model_validate(user)
        workspace = await resolve_workspace(
            db,
            current_user,
            workspace_query(user)["workspace"],
        )
        result = await run_search_documents(db, workspace, query="对齐合同")

    assert result.ok is True
    assert result.data is not None
    assert result.data.total == api_body["total"]
    assert len(result.data.items) == len(api_body["items"])
