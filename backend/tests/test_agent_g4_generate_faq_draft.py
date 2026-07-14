"""G4-1.2 + G4-1.3：generate_faq_draft 写·待审 tool。

G4-1.2：入参校验 + 落 agent_approvals(pending) + payload_json + 出参摘要无全文。
G4-1.3 收口：失败路径返回结构化 reason 码（kb_not_visible / invalid_filename /
no_source），供 G4-2.2 runtime 确定性生成「助手拒答/说明」。

覆盖 E 表：G4-E10（越权 kb）· G4-E11（无命中依据）· G4-E19（库内 edit 截断）· 非 .md 校验。
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_approval import AgentApproval
from app.models.document_chunk import DocumentChunk
from app.models.enums import ApprovalKind, ApprovalStatus
from app.models.knowledge_base import KnowledgeBase
from app.services.agent.tools.generate_faq_draft import (
    BAD_FILENAME_SUMMARY,
    NO_BASIS_SUMMARY,
    GenerateFaqDraftFailure,
    GenerateFaqDraftToolResult,
    run_generate_faq_draft,
)
from app.services.agent.tools.scope import AgentToolScope, FORBIDDEN_KB_SUMMARY


def _make_scope(
    visible: set[uuid.UUID], *, default_kb_id: uuid.UUID | None = None
) -> AgentToolScope:
    return AgentToolScope(
        visible_kb_ids=frozenset(visible),
        default_kb_id=default_kb_id,
    )


def _chunk(kb_id: uuid.UUID, content: str = "员工年假规定为 10 天，需提前申请") -> DocumentChunk:
    return DocumentChunk(
        id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        kb_id=kb_id,
        chunk_index=0,
        section_title="1.1 年假",
        content=content,
    )


def _mock_db_for_success(kb_id: uuid.UUID, chunk: DocumentChunk) -> AsyncSession:
    """db.execute → [chunk]；db.get(KB) → kb；db.add/flush 被记录。"""
    result = MagicMock()
    result.scalars.return_value.all.return_value = [chunk]
    kb = KnowledgeBase(id=kb_id, name="制度库", owner_user_id=uuid.uuid4())

    db: AsyncSession = AsyncMock(spec=AsyncSession)
    db.execute = AsyncMock(return_value=result)
    db.get = AsyncMock(
        side_effect=lambda model, pk: kb if model is KnowledgeBase else None
    )
    return db


@pytest.mark.asyncio
async def test_generate_faq_draft_forbidden_kb_g4_e10() -> None:
    """模型传越权 kb_id → tool ok=false · 不创建 approval（G4-E10）。"""
    visible = uuid.uuid4()
    forbidden = uuid.uuid4()
    chunk = _chunk(forbidden)
    db = _mock_db_for_success(forbidden, chunk)
    scope = _make_scope({visible})

    result = await run_generate_faq_draft(
        db,
        scope,
        kb_id=forbidden,
        filename="FAQ_年假.md",
        run_id=uuid.uuid4(),
        thread_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        source_chunk_ids=[chunk.id],
    )

    assert result.ok is False
    assert result.data is None
    assert result.summary == FORBIDDEN_KB_SUMMARY
    assert result.reason == GenerateFaqDraftFailure.kb_not_visible  # G4-1.3 拒答码
    db.add.assert_not_called()


@pytest.mark.asyncio
async def test_generate_faq_draft_non_md_filename() -> None:
    """文件名非 .md 后缀 → ok=false · 不创建 approval（G4-1.2 入参校验）。"""
    kb_id = uuid.uuid4()
    chunk = _chunk(kb_id)
    db = _mock_db_for_success(kb_id, chunk)
    scope = _make_scope({kb_id})

    result = await run_generate_faq_draft(
        db,
        scope,
        kb_id=kb_id,
        filename="FAQ_年假.txt",
        run_id=uuid.uuid4(),
        thread_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        source_chunk_ids=[chunk.id],
    )

    assert result.ok is False
    assert result.data is None
    assert result.summary == BAD_FILENAME_SUMMARY
    assert result.reason == GenerateFaqDraftFailure.invalid_filename  # G4-1.3 拒答码
    db.add.assert_not_called()


@pytest.mark.asyncio
async def test_generate_faq_draft_no_basis_g4_e11() -> None:
    """全无命中依据（source_chunk_ids 为空）→ ok=false · 不创建 approval（G4-E11）。"""
    kb_id = uuid.uuid4()
    db: AsyncSession = AsyncMock(spec=AsyncSession)
    scope = _make_scope({kb_id})

    result = await run_generate_faq_draft(
        db,
        scope,
        kb_id=kb_id,
        filename="FAQ_年假.md",
        run_id=uuid.uuid4(),
        thread_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        source_chunk_ids=[],  # 无依据
    )

    assert result.ok is False
    assert result.data is None
    assert result.summary == NO_BASIS_SUMMARY
    assert result.reason == GenerateFaqDraftFailure.no_source  # G4-1.3 拒答码
    db.add.assert_not_called()


@pytest.mark.asyncio
async def test_generate_faq_draft_creates_pending_approval() -> None:
    """有依据 → ok=true · 返回 approval_id · 落 agent_approvals(pending) · 出参无全文。"""
    kb_id = uuid.uuid4()
    chunk = _chunk(kb_id)
    db = _mock_db_for_success(kb_id, chunk)
    scope = _make_scope({kb_id})
    run_id, thread_id, user_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()

    result = await run_generate_faq_draft(
        db,
        scope,
        kb_id=kb_id,
        filename="FAQ_年假.md",
        run_id=run_id,
        thread_id=thread_id,
        user_id=user_id,
        source_chunk_ids=[chunk.id],
        title="年假 FAQ",
    )

    assert result.ok is True
    assert isinstance(result, GenerateFaqDraftToolResult)
    assert result.data is not None
    assert result.reason is None  # 成功无拒答码
    approval_id = result.data.approval_id
    assert isinstance(approval_id, uuid.UUID)
    assert result.data.filename == "FAQ_年假.md"
    assert result.data.kb_name == "制度库"
    assert result.data.draft_chars > 0
    assert result.data.citation_count == 1
    # 出参摘要不含草稿全文
    assert "员工年假规定为 10 天" not in result.summary

    # G4-3.5：generate_faq_draft 成功后追加一条 approval_created 审计写入，
    # 故 db.add 调用次数 >= 1；首个被 add 的对象仍是 AgentApproval（草稿行）。
    added = [c.args[0] for c in db.add.call_args_list]
    assert len(added) >= 1
    saved = next(obj for obj in added if isinstance(obj, AgentApproval))
    assert isinstance(saved, AgentApproval)
    assert saved.id == approval_id
    assert saved.run_id == run_id
    assert saved.thread_id == thread_id
    assert saved.user_id == user_id
    assert saved.kb_id == kb_id
    assert saved.filename == "FAQ_年假.md"
    assert saved.kind == ApprovalKind.adopt_faq
    assert saved.status == ApprovalStatus.pending

    payload = saved.payload_json
    assert payload is not None
    assert payload["filename"] == "FAQ_年假.md"
    assert payload["title"] == "年假 FAQ"
    assert "员工年假规定为 10 天" in payload["markdown"]
    assert payload["source_chunk_ids"] == [str(chunk.id)]
    db.flush.assert_awaited()


@pytest.mark.asyncio
async def test_generate_faq_draft_truncates_to_default_kb_g4_e19() -> None:
    """库内 edit：默认目标库已设，模型传别的 kb_id 被截断到路径 kb（G4-E19）。"""
    path_kb = uuid.uuid4()
    model_chosen = uuid.uuid4()
    chunk = _chunk(path_kb)
    db = _mock_db_for_success(path_kb, chunk)
    scope = _make_scope({path_kb, model_chosen}, default_kb_id=path_kb)

    result = await run_generate_faq_draft(
        db,
        scope,
        kb_id=model_chosen,  # 模型想写到别的库
        filename="FAQ_年假.md",
        run_id=uuid.uuid4(),
        thread_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        source_chunk_ids=[chunk.id],
    )

    assert result.ok is True
    assert result.data is not None
    saved = db.add.call_args[0][0]
    assert saved.kb_id == path_kb  # 截断到路径 kb，无视模型传的 id
