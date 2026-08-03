"""H1 可先行批：M6/M7（admin_only 泄露）· M8（scope None 防御）· L10（写纵深防御）· M17（Member 配额）。

验收口径（接力提示词）：
- member 检索 admin_only 文档断言为空（semantic_search / search_documents）；
- member get_chunk_excerpt / grep / compare 对 admin_only 拒答；
- visible_kb_ids=None 不再 TypeError / .in_(None)；
- run_*_document(commit=True) member → write_forbidden，不建审批；admin → pending；
- Member 生成配额超限 → quota_exceeded。
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from sqlalchemy import text

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.agent_run import AgentRun
from app.models.chat_thread import ChatThread
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.enums import (
    AgentRunMode,
    AgentRunStatus,
    ApprovalStatus,
    DocumentStatus,
    DocumentVisibility,
    ThreadKind,
    ThreadStatus,
)
from app.services.agent.dispatch import (
    build_kb_tool_scope,
    build_workspace_tool_scope,
)
from app.services.agent.tools.compare_chunks import run_compare_chunks
from app.services.agent.tools.document_write import (
    DocumentWriteFailure,
    run_delete_document,
)
from app.services.agent.tools.generate_faq_draft import (
    DAILY_QUOTA_SUMMARY,
    THREAD_QUOTA_SUMMARY,
    GenerateFaqDraftFailure,
    run_generate_faq_draft,
)
from app.services.agent.tools.get_chunk_excerpt import (
    NOT_FOUND_SUMMARY,
    run_get_chunk_excerpt,
)
from app.services.agent.tools.grep_in_document import run_grep_in_document
from app.services.agent.tools.scope import AgentToolScope
from app.services.agent.tools.search_documents import run_search_documents
from app.services.agent.tools.semantic_search import run_semantic_search
from app.services.org.scope import resolve_org_scope_for_workspace
from app.services.workspace.scope import WorkspaceKind, WorkspaceScope


@pytest.fixture
def rerank_mock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "rerank_enabled", True)
    monkeypatch.setattr(settings, "rerank_provider", "mock")


def _org_workspace(org_id: UUID, user_id: UUID) -> WorkspaceScope:
    return WorkspaceScope(
        kind=WorkspaceKind.organization,
        user_id=user_id,
        org_id=org_id,
    )


async def _seed_admin_only_doc(
    *,
    kb_id: UUID,
    user_id: UUID,
) -> tuple[UUID, UUID]:
    """seed 一个 admin_only 文档 + 唯一 marker chunk，返回 (doc_id, chunk_id)。"""
    doc_id = uuid.uuid4()
    chunk_id = uuid.uuid4()
    content = "H1_ADMIN_CONTENT_MARKER 薪酬与期权保密信息，仅管理员可见"
    async with SessionLocal() as db:
        db.add(
            Document(
                id=doc_id,
                kb_id=kb_id,
                filename="H1_ADMIN_ONLY_MARKER.txt",
                file_type="txt",
                file_size=len(content),
                storage_path=f"/tmp/{kb_id}/{doc_id}.txt",
                status=DocumentStatus.completed,
                chunk_count=1,
                uploaded_by=user_id,
                visibility=DocumentVisibility.admin_only,
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
        await db.commit()
    return doc_id, chunk_id


async def _insert_thread_run(user_id: UUID, kb_id: UUID) -> tuple[UUID, UUID]:
    """直插 chat_threads + agent_runs（AgentApproval 的 FK 父表）。"""
    thread_id = uuid.uuid4()
    run_id = uuid.uuid4()
    async with SessionLocal() as db:
        db.add(
            ChatThread(
                id=thread_id,
                thread_kind=ThreadKind.workspace,
                user_id=user_id,
                kb_id=kb_id,
                status=ThreadStatus.active,
            )
        )
        await db.flush()
        db.add(
            AgentRun(
                id=run_id,
                thread_id=thread_id,
                user_id=user_id,
                mode=AgentRunMode.edit,
                status=AgentRunStatus.completed,
            )
        )
        await db.commit()
    return thread_id, run_id


# ── M6 接线：build_*_tool_scope member 标志 ────────────────────────────────


def test_build_tool_scope_member_flag() -> None:
    kb_id = uuid.uuid4()
    assert build_kb_tool_scope(kb_id, None, member=True).member is True
    assert build_kb_tool_scope(kb_id, None).member is False
    assert build_workspace_tool_scope(None, member=True).member is True
    assert build_workspace_tool_scope(None).member is False
    assert build_workspace_tool_scope(None, member=True).hide_admin_only is True


# ── M6 单元：hide_admin_only 透传 ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_semantic_search_passes_hide_admin_only_for_member(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    kb_id = uuid.uuid4()
    retrieve_chunks = AsyncMock(return_value=[])
    monkeypatch.setattr(
        "app.services.agent.tools.semantic_search.retrieve_chunks",
        retrieve_chunks,
    )
    member_scope = AgentToolScope(
        visible_kb_ids=frozenset({kb_id}),
        default_kb_id=kb_id,
        member=True,
    )

    async with SessionLocal() as db:
        await run_semantic_search(
            db,
            _org_workspace(uuid.uuid4(), uuid.uuid4()),
            member_scope,
            query="薪酬",
        )

    assert retrieve_chunks.await_args.kwargs["hide_admin_only"] is True


@pytest.mark.asyncio
async def test_semantic_search_admin_passes_hide_admin_only_false(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    kb_id = uuid.uuid4()
    retrieve_chunks = AsyncMock(return_value=[])
    monkeypatch.setattr(
        "app.services.agent.tools.semantic_search.retrieve_chunks",
        retrieve_chunks,
    )
    admin_scope = AgentToolScope(
        visible_kb_ids=frozenset({kb_id}),
        default_kb_id=kb_id,
    )

    async with SessionLocal() as db:
        await run_semantic_search(
            db,
            _org_workspace(uuid.uuid4(), uuid.uuid4()),
            admin_scope,
            query="薪酬",
        )

    assert retrieve_chunks.await_args.kwargs["hide_admin_only"] is False


@pytest.mark.asyncio
async def test_search_documents_passes_hide_admin_only_for_member(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    search_by_filename = AsyncMock(
        return_value=type(
            "R",
            (),
            {"items": [], "total": 0},
        )()
    )
    monkeypatch.setattr(
        "app.services.agent.tools.search_documents.search_documents_by_filename",
        search_by_filename,
    )
    member_scope = AgentToolScope(member=True)

    async with SessionLocal() as db:
        await run_search_documents(
            db,
            _org_workspace(uuid.uuid4(), uuid.uuid4()),
            query="MARKER",
            tool_scope=member_scope,
        )

    assert search_by_filename.await_args.kwargs["hide_admin_only"] is True


# ── M6/M7 集成：member 检索 admin_only 文档 → 空 / 拒答 ───────────────────


@pytest.mark.asyncio
async def test_member_semantic_search_hides_admin_only_doc(
    org_iso,
    rerank_mock: None,
) -> None:
    """admin_only 文档对 member 检索不可见；admin 可见（M6）。"""
    _, chunk_id = await _seed_admin_only_doc(
        kb_id=org_iso.public_kb_id,
        user_id=org_iso.owner.id,
    )
    _ = chunk_id

    async with SessionLocal() as db:
        member_ws = _org_workspace(org_iso.org_id, org_iso.rd_member.id)
        member_org_scope = await resolve_org_scope_for_workspace(
            db, org_iso.rd_member, member_ws
        )
        member_result = await run_semantic_search(
            db,
            member_ws,
            AgentToolScope(
                visible_kb_ids=member_org_scope.visible_kb_ids,
                member=True,
            ),
            query="H1_ADMIN_CONTENT_MARKER",
        )

        admin_ws = _org_workspace(org_iso.org_id, org_iso.owner.id)
        admin_org_scope = await resolve_org_scope_for_workspace(
            db, org_iso.owner, admin_ws
        )
        admin_result = await run_semantic_search(
            db,
            admin_ws,
            AgentToolScope(
                visible_kb_ids=admin_org_scope.visible_kb_ids,
            ),
            query="H1_ADMIN_CONTENT_MARKER",
        )

    assert member_result.ok is True
    assert member_result.data is not None
    # member：命中集不允许出现 admin_only 文档（内容/文件名都不泄露）
    assert all(
        "H1_ADMIN_CONTENT_MARKER" not in hit.excerpt
        and hit.doc_name != "H1_ADMIN_ONLY_MARKER.txt"
        for hit in member_result.data.hits
    )
    assert admin_result.ok is True
    assert admin_result.data is not None


@pytest.mark.asyncio
async def test_member_search_documents_hides_admin_only_doc(
    org_iso,
) -> None:
    await _seed_admin_only_doc(
        kb_id=org_iso.public_kb_id,
        user_id=org_iso.owner.id,
    )

    async with SessionLocal() as db:
        member_ws = _org_workspace(org_iso.org_id, org_iso.rd_member.id)
        member_org_scope = await resolve_org_scope_for_workspace(
            db, org_iso.rd_member, member_ws
        )
        member_result = await run_search_documents(
            db,
            member_ws,
            query="H1_ADMIN_ONLY_MARKER",
            org_scope=member_org_scope,
            tool_scope=AgentToolScope(
                visible_kb_ids=member_org_scope.visible_kb_ids,
                member=True,
            ),
        )

        admin_ws = _org_workspace(org_iso.org_id, org_iso.owner.id)
        admin_org_scope = await resolve_org_scope_for_workspace(
            db, org_iso.owner, admin_ws
        )
        admin_result = await run_search_documents(
            db,
            admin_ws,
            query="H1_ADMIN_ONLY_MARKER",
            org_scope=admin_org_scope,
            tool_scope=AgentToolScope(
                visible_kb_ids=admin_org_scope.visible_kb_ids,
            ),
        )

    assert member_result.ok is True
    assert member_result.data is not None
    assert member_result.data.total == 0
    assert admin_result.data is not None
    assert admin_result.data.total >= 1


@pytest.mark.asyncio
async def test_member_get_chunk_excerpt_denies_admin_only(
    org_iso,
) -> None:
    _, chunk_id = await _seed_admin_only_doc(
        kb_id=org_iso.public_kb_id,
        user_id=org_iso.owner.id,
    )

    async with SessionLocal() as db:
        member_result = await run_get_chunk_excerpt(
            db,
            AgentToolScope(
                visible_kb_ids=frozenset({org_iso.public_kb_id}),
                member=True,
            ),
            chunk_id=chunk_id,
        )
        admin_result = await run_get_chunk_excerpt(
            db,
            AgentToolScope(
                visible_kb_ids=frozenset({org_iso.public_kb_id}),
            ),
            chunk_id=chunk_id,
        )

    assert member_result.ok is False
    assert member_result.summary == NOT_FOUND_SUMMARY
    assert admin_result.ok is True
    assert admin_result.data is not None
    assert "H1_ADMIN_CONTENT_MARKER" in admin_result.data.excerpt


# ── M7/M8：grep / compare（member 过滤 + None scope 防御）──────────────────


@pytest.mark.asyncio
async def test_grep_member_denies_admin_only_and_none_scope_no_typeerror(
    org_iso,
) -> None:
    doc_id, _ = await _seed_admin_only_doc(
        kb_id=org_iso.public_kb_id,
        user_id=org_iso.owner.id,
    )

    async with SessionLocal() as db:
        member_result = await run_grep_in_document(
            db,
            AgentToolScope(
                visible_kb_ids=frozenset({org_iso.public_kb_id}),
                member=True,
            ),
            document_id=doc_id,
            pattern="H1_ADMIN_CONTENT_MARKER",
        )
        # M8：visible_kb_ids=None（个人 workspace）不得抛 TypeError
        none_scope_result = await run_grep_in_document(
            db,
            AgentToolScope(visible_kb_ids=None),
            document_id=doc_id,
            pattern="H1_ADMIN_CONTENT_MARKER",
        )

    assert member_result.ok is False
    assert "no access" in member_result.summary
    assert none_scope_result.ok is True
    assert len(none_scope_result.data.matches) >= 1


@pytest.mark.asyncio
async def test_compare_member_filters_admin_only_and_none_scope_works(
    org_iso,
) -> None:
    _, chunk_id = await _seed_admin_only_doc(
        kb_id=org_iso.public_kb_id,
        user_id=org_iso.owner.id,
    )

    async with SessionLocal() as db:
        member_result = await run_compare_chunks(
            db,
            AgentToolScope(
                visible_kb_ids=frozenset({org_iso.public_kb_id}),
                member=True,
            ),
            chunk_ids=[str(chunk_id)],
        )
        # M8：None scope 不再 .in_(None)
        none_scope_result = await run_compare_chunks(
            db,
            AgentToolScope(visible_kb_ids=None),
            chunk_ids=[str(chunk_id)],
        )

    assert member_result.ok is False
    assert "no access" in member_result.summary
    assert none_scope_result.ok is True
    assert len(none_scope_result.data.chunks) == 1
    assert none_scope_result.data.chunks[0].chunk_id == chunk_id


# ── L10：commit 分支写权限纵深防御 ────────────────────────────────────────


@pytest.mark.asyncio
async def test_run_delete_commit_member_forbidden_no_approval(
    org_iso,
) -> None:
    """member 直调 run_delete_document(commit=True) → write_forbidden，不建审批。"""
    doc_id, _ = await _seed_admin_only_doc(
        kb_id=org_iso.public_kb_id,
        user_id=org_iso.owner.id,
    )
    thread_id, run_id = await _insert_thread_run(
        org_iso.owner.id, org_iso.public_kb_id
    )
    tool_scope = AgentToolScope(
        visible_kb_ids=frozenset({org_iso.public_kb_id}),
        member=True,
    )

    async with SessionLocal() as db:
        result = await run_delete_document(
            db,
            tool_scope,
            kb_id=org_iso.public_kb_id,
            document_id=doc_id,
            run_id=run_id,
            thread_id=thread_id,
            current_user=org_iso.rd_member,
            commit=True,
        )
        approval_count = await db.scalar(
            text("SELECT count(*) FROM agent_approvals WHERE run_id = :rid"),
            {"rid": run_id},
        )

    assert result.ok is False
    assert result.reason == DocumentWriteFailure.write_forbidden
    assert result.approval_id is None
    assert int(approval_count or 0) == 0


@pytest.mark.asyncio
async def test_run_delete_commit_admin_creates_pending(
    org_iso,
) -> None:
    """admin 同路径 → 建 pending 审批（L10 不误伤合法管理员）。"""
    doc_id, _ = await _seed_admin_only_doc(
        kb_id=org_iso.public_kb_id,
        user_id=org_iso.owner.id,
    )
    thread_id, run_id = await _insert_thread_run(
        org_iso.owner.id, org_iso.public_kb_id
    )
    tool_scope = AgentToolScope(
        visible_kb_ids=frozenset({org_iso.public_kb_id}),
    )

    async with SessionLocal() as db:
        result = await run_delete_document(
            db,
            tool_scope,
            kb_id=org_iso.public_kb_id,
            document_id=doc_id,
            run_id=run_id,
            thread_id=thread_id,
            current_user=org_iso.owner,
            commit=True,
        )
        approval = await db.scalar(
            text(
                "SELECT status FROM agent_approvals "
                "WHERE run_id = :rid AND kind = 'delete_document'"
            ),
            {"rid": run_id},
        )

    assert result.ok is True
    assert result.approval_id is not None
    assert approval == ApprovalStatus.pending.value


# ── M17：Member 生成配额 ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_member_faq_draft_thread_quota_exceeded(
    org_iso,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """member 每 thread pending 上限：超限 → quota_exceeded（M17）。"""
    monkeypatch.setattr(settings, "agent_member_faq_thread_quota", 1)
    monkeypatch.setattr(settings, "agent_member_faq_daily_quota", 100)
    _, chunk_id = await _seed_admin_only_doc(
        kb_id=org_iso.public_kb_id,
        user_id=org_iso.owner.id,
    )
    thread_id, run_id = await _insert_thread_run(
        org_iso.rd_member.id, org_iso.public_kb_id
    )
    tool_scope = AgentToolScope(
        visible_kb_ids=frozenset({org_iso.public_kb_id}),
        member=True,
    )

    async with SessionLocal() as db:
        first = await run_generate_faq_draft(
            db,
            tool_scope,
            kb_id=org_iso.public_kb_id,
            filename="FAQ_1.md",
            run_id=run_id,
            thread_id=thread_id,
            user_id=org_iso.rd_member.id,
            source_chunk_ids=[chunk_id],
            title="Q1",
        )
        second = await run_generate_faq_draft(
            db,
            tool_scope,
            kb_id=org_iso.public_kb_id,
            filename="FAQ_2.md",
            run_id=run_id,
            thread_id=thread_id,
            user_id=org_iso.rd_member.id,
            source_chunk_ids=[chunk_id],
            title="Q2",
        )

    assert first.ok is True
    assert first.data is not None
    assert second.ok is False
    assert second.reason == GenerateFaqDraftFailure.quota_exceeded
    assert second.summary == THREAD_QUOTA_SUMMARY


@pytest.mark.asyncio
async def test_member_faq_draft_daily_quota_exceeded(
    org_iso,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """member 每日创建上限：超限 → quota_exceeded（M17）。"""
    monkeypatch.setattr(settings, "agent_member_faq_thread_quota", 100)
    monkeypatch.setattr(settings, "agent_member_faq_daily_quota", 1)
    _, chunk_id = await _seed_admin_only_doc(
        kb_id=org_iso.public_kb_id,
        user_id=org_iso.owner.id,
    )
    thread_id, run_id = await _insert_thread_run(
        org_iso.rd_member.id, org_iso.public_kb_id
    )
    tool_scope = AgentToolScope(
        visible_kb_ids=frozenset({org_iso.public_kb_id}),
        member=True,
    )

    async with SessionLocal() as db:
        first = await run_generate_faq_draft(
            db,
            tool_scope,
            kb_id=org_iso.public_kb_id,
            filename="FAQ_1.md",
            run_id=run_id,
            thread_id=thread_id,
            user_id=org_iso.rd_member.id,
            source_chunk_ids=[chunk_id],
            title="Q1",
        )
        second = await run_generate_faq_draft(
            db,
            tool_scope,
            kb_id=org_iso.public_kb_id,
            filename="FAQ_2.md",
            run_id=run_id,
            thread_id=thread_id,
            user_id=org_iso.rd_member.id,
            source_chunk_ids=[chunk_id],
            title="Q2",
        )

    assert first.ok is True
    assert second.ok is False
    assert second.reason == GenerateFaqDraftFailure.quota_exceeded
    assert second.summary == DAILY_QUOTA_SUMMARY


@pytest.mark.asyncio
async def test_admin_faq_draft_not_quota_limited(
    org_iso,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """非 member（admin）不受配额闸限制（M17 仅 member）。"""
    monkeypatch.setattr(settings, "agent_member_faq_thread_quota", 1)
    monkeypatch.setattr(settings, "agent_member_faq_daily_quota", 1)
    _, chunk_id = await _seed_admin_only_doc(
        kb_id=org_iso.public_kb_id,
        user_id=org_iso.owner.id,
    )
    thread_id, run_id = await _insert_thread_run(
        org_iso.owner.id, org_iso.public_kb_id
    )
    admin_scope = AgentToolScope(
        visible_kb_ids=frozenset({org_iso.public_kb_id}),
        member=False,
    )

    async with SessionLocal() as db:
        first = await run_generate_faq_draft(
            db,
            admin_scope,
            kb_id=org_iso.public_kb_id,
            filename="FAQ_1.md",
            run_id=run_id,
            thread_id=thread_id,
            user_id=org_iso.owner.id,
            source_chunk_ids=[chunk_id],
            title="Q1",
        )
        second = await run_generate_faq_draft(
            db,
            admin_scope,
            kb_id=org_iso.public_kb_id,
            filename="FAQ_2.md",
            run_id=run_id,
            thread_id=thread_id,
            user_id=org_iso.owner.id,
            source_chunk_ids=[chunk_id],
            title="Q2",
        )

    assert first.ok is True
    assert second.ok is True
