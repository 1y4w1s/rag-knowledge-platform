"""P2-A2：库内模式 search_documents 的 kb_ids 透传与可见 kb 求交。

覆盖场景：
- runtime 将 args['kb_ids'] 透传给 run_search_documents；
- 单库 kb_ids 收窄到服务层 kb_id 过滤（filename / content）；
- 越权 kb_ids 直接 deny（G3-E2），search 服务不执行；
- 多库 kb_ids 逐库搜索后按创建时间合并并截断 limit；
- 库内对话不泄露同组织其他可见库的文档（集成）。
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import UUID

import pytest

from app.core.database import SessionLocal
from app.models.enums import DocumentStatus
from app.schemas.search import SearchDocumentItem, SearchDocumentsResponse
from app.services.agent.runtime import _dispatch_tool
from app.services.agent.tools.registry import ReadOnlyToolName
from app.services.agent.tools.scope import AgentToolScope
from app.services.agent.tools.search_documents import run_search_documents
from app.services.org.scope import resolve_org_scope_for_workspace
from app.services.workspace.scope import (
    WorkspaceKind,
    WorkspaceScope,
    resolve_workspace,
)
from tests.test_search_documents import _seed_document


def _personal_workspace(user_id: UUID | None = None) -> WorkspaceScope:
    return WorkspaceScope(
        kind=WorkspaceKind.personal,
        user_id=user_id or uuid.uuid4(),
        org_id=None,
    )


def _response(
    *,
    doc_id: UUID,
    kb_id: UUID,
    created_at: datetime,
    filename: str = "年度制度.pdf",
    mode: str = "filename",
) -> SearchDocumentsResponse:
    return SearchDocumentsResponse(
        items=[
            SearchDocumentItem(
                doc_id=doc_id,
                filename=filename,
                file_type="pdf",
                status=DocumentStatus.completed,
                kb_id=kb_id,
                kb_name="测试库",
                created_at=created_at,
            )
        ],
        query="年度",
        total=1,
        limit=50,
        offset=0,
        mode=mode,
    )


@pytest.mark.asyncio
async def test_runtime_forwards_kb_ids_to_search_documents(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    kb_id = uuid.uuid4()
    run_mock = AsyncMock(
        return_value=type(
            "R",
            (),
            {"ok": True, "summary": "ok", "data": None},
        )()
    )
    monkeypatch.setattr(
        "app.services.agent.runtime.run_search_documents", run_mock
    )

    ok, summary, _ = await _dispatch_tool(
        AsyncMock(),
        workspace=_personal_workspace(),
        tool_scope=AgentToolScope(
            visible_kb_ids=frozenset({kb_id}),
            default_kb_id=kb_id,
        ),
        org_scope=None,
        current_user=None,
        tool_name=ReadOnlyToolName.search_documents,
        args={"query": "年度", "kb_ids": [str(kb_id)]},
        run_id=uuid.uuid4(),
        thread_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
    )

    assert ok is True
    assert summary == "ok"
    assert run_mock.await_args.kwargs["kb_ids"] == [kb_id]
    assert run_mock.await_args.kwargs["query"] == "年度"


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["filename", "content"])
async def test_search_documents_single_kb_forwards_kb_filter(
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
) -> None:
    kb_id = uuid.uuid4()
    if mode == "content":
        service_mock = AsyncMock(
            return_value=_response(
                doc_id=uuid.uuid4(),
                kb_id=kb_id,
                created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                mode="content",
            )
        )
        other_mock = AsyncMock()
        monkeypatch.setattr(
            "app.services.agent.tools.search_documents.search_documents_by_content",
            service_mock,
        )
        monkeypatch.setattr(
            "app.services.agent.tools.search_documents.search_documents_by_filename",
            other_mock,
        )
    else:
        service_mock = AsyncMock(
            return_value=_response(
                doc_id=uuid.uuid4(),
                kb_id=kb_id,
                created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            )
        )
        other_mock = AsyncMock()
        monkeypatch.setattr(
            "app.services.agent.tools.search_documents.search_documents_by_filename",
            service_mock,
        )
        monkeypatch.setattr(
            "app.services.agent.tools.search_documents.search_documents_by_content",
            other_mock,
        )

    async with SessionLocal() as db:
        result = await run_search_documents(
            db,
            _personal_workspace(),
            query="年度",
            mode=mode,
            tool_scope=AgentToolScope(
                visible_kb_ids=frozenset({kb_id}),
                default_kb_id=kb_id,
            ),
            kb_ids=[kb_id],
        )

    assert result.ok is True
    assert result.data is not None
    assert result.data.total == 1
    assert result.data.items[0].kb_id == kb_id
    service_mock.assert_awaited_once()
    assert service_mock.await_args.kwargs["kb_id"] == kb_id
    other_mock.assert_not_called()


@pytest.mark.asyncio
async def test_search_documents_forbidden_kb_ids_denied(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    visible_kb = uuid.uuid4()
    forbidden_kb = uuid.uuid4()
    search_by_filename = AsyncMock()
    monkeypatch.setattr(
        "app.services.agent.tools.search_documents.search_documents_by_filename",
        search_by_filename,
    )

    async with SessionLocal() as db:
        result = await run_search_documents(
            db,
            _personal_workspace(),
            query="年度",
            tool_scope=AgentToolScope(
                visible_kb_ids=frozenset({visible_kb}),
            ),
            kb_ids=[visible_kb, forbidden_kb],
        )

    assert result.ok is False
    assert result.data is None
    assert result.summary == "无权限"
    search_by_filename.assert_not_awaited()


@pytest.mark.asyncio
async def test_search_documents_multi_kb_merges_sorted_and_capped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    kb_a = uuid.uuid4()
    kb_b = uuid.uuid4()
    old_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    new_at = datetime(2026, 2, 1, tzinfo=timezone.utc)

    async def _side_effect(
        db,
        workspace,
        query,
        limit,
        *,
        org_scope,
        hide_admin_only,
        kb_id,
    ):
        del db, workspace, query, limit, org_scope, hide_admin_only
        if kb_id == kb_a:
            return _response(
                doc_id=uuid.uuid4(),
                kb_id=kb_a,
                created_at=old_at,
            )
        return _response(
            doc_id=uuid.uuid4(),
            kb_id=kb_b,
            created_at=new_at,
        )

    search_by_filename = AsyncMock(side_effect=_side_effect)
    monkeypatch.setattr(
        "app.services.agent.tools.search_documents.search_documents_by_filename",
        search_by_filename,
    )

    async with SessionLocal() as db:
        result = await run_search_documents(
            db,
            _personal_workspace(),
            query="年度",
            limit=1,
            tool_scope=AgentToolScope(
                visible_kb_ids=frozenset({kb_a, kb_b}),
            ),
            kb_ids=[kb_a, kb_b],
        )

    assert result.ok is True
    assert result.data is not None
    assert result.data.total == 2
    assert len(result.data.items) == 1
    assert result.data.items[0].kb_id == kb_b
    assert search_by_filename.await_count == 2


@pytest.mark.asyncio
async def test_kb_scoped_search_does_not_leak_sibling_kb_docs(
    org_iso,
) -> None:
    """库内模式只搜 default_kb_id，不泄露同组织其他可见库的同名文档。"""
    marker = f"P2_A2_SIBLING_MARKER_{uuid.uuid4().hex[:8]}"
    await _seed_document(
        kb_id=org_iso.rd_kb_id,
        user_id=org_iso.owner.id,
        filename=f"{marker}.pdf",
    )
    await _seed_document(
        kb_id=org_iso.mkt_kb_id,
        user_id=org_iso.owner.id,
        filename=f"{marker}.pdf",
    )

    async with SessionLocal() as db:
        workspace = await resolve_workspace(
            db, org_iso.owner, str(org_iso.org_id)
        )
        org_scope = await resolve_org_scope_for_workspace(
            db, org_iso.owner, workspace
        )
        assert org_iso.mkt_kb_id in org_scope.visible_kb_ids
        result = await run_search_documents(
            db,
            workspace,
            query=marker,
            org_scope=org_scope,
            tool_scope=AgentToolScope(
                visible_kb_ids=org_scope.visible_kb_ids,
                default_kb_id=org_iso.rd_kb_id,
            ),
            kb_ids=[org_iso.rd_kb_id],
        )

    assert result.ok is True
    assert result.data is not None
    assert result.data.total == 1
    assert len(result.data.items) == 1
    assert result.data.items[0].kb_id == org_iso.rd_kb_id
