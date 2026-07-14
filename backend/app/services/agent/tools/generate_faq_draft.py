"""G4-min 写·待审 tool：generate_faq_draft（G4-1.2）。

基于只读查库得到的 source_chunk_ids，组装 FAQ Markdown 草稿，
INSERT agent_approvals(status=pending)，草稿正文存 payload_json。

本 tool 只创建「待审」审批行：
- 不 CREATE documents、不触发 ingestion（ingestion 在用户采纳后由
  adopt_draft_to_kb 触发，见 G4-3.2）。
- 出参 ToolResult.summary 仅给摘要，**不含** 草稿全文（全文走 SSE
  approval_required，payload_json 落库）。

runtime 调用契约（G4-2.x 接入）：run_id / thread_id / user_id 由
run_react_loop 透传；本函数只消费，不直接读 JWT / 当前用户。
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from enum import Enum

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_approval import AgentApproval
from app.models.document_chunk import DocumentChunk
from app.models.enums import ApprovalKind, ApprovalStatus
from app.models.knowledge_base import KnowledgeBase
from app.services.agent.tools.scope import AgentToolScope, ToolDenial
from app.services.audit.agent import (
    audit_agent_approval_created,
    safe_audit,
)
from app.services.audit.log import write_audit_log

NO_BASIS_SUMMARY = "库内无足够依据，未生成 FAQ 草稿"
BAD_FILENAME_SUMMARY = "filename 须以 .md 结尾"


class GenerateFaqDraftFailure(str, Enum):
    """失败原因码（G4-1.3）。

    runtime（G4-2.2）据 reason 确定性生成「助手拒答/说明」，而非靠字符串匹配
    summary。summary 仍保留给人读；reason 给机器分支。
    """

    kb_not_visible = "kb_not_visible"  # G4-E10：目标库越权 / 不可见
    invalid_filename = "invalid_filename"  # 文件名非 .md 后缀
    no_source = "no_source"  # G4-E11：无命中依据 / 依据片段不可读


@dataclass(frozen=True, slots=True)
class GenerateFaqDraftOutput:
    approval_id: uuid.UUID
    filename: str
    kb_name: str
    draft_chars: int
    citation_count: int


@dataclass(frozen=True, slots=True)
class GenerateFaqDraftToolResult:
    ok: bool
    data: GenerateFaqDraftOutput | None
    summary: str
    reason: GenerateFaqDraftFailure | None = None


async def run_generate_faq_draft(
    db: AsyncSession,
    tool_scope: AgentToolScope,
    *,
    kb_id: uuid.UUID,
    filename: str,
    run_id: uuid.UUID,
    thread_id: uuid.UUID,
    user_id: uuid.UUID,
    source_chunk_ids: list[uuid.UUID] | None = None,
    title: str | None = None,
) -> GenerateFaqDraftToolResult:
    # 1) 目标库解析：库内 edit 强制截断到 default_kb_id（G4-E19）；越权 deny（G4-E10）
    resolved = tool_scope.resolve_target_kb_for_edit(kb_id)
    if isinstance(resolved, ToolDenial):
        return GenerateFaqDraftToolResult(
            ok=False,
            data=None,
            summary=resolved.summary,
            reason=GenerateFaqDraftFailure.kb_not_visible,
        )

    # 2) 文件名须 .md 后缀（G4-1.2 入参校验）
    if not str(filename).endswith(".md"):
        return GenerateFaqDraftToolResult(
            ok=False,
            data=None,
            summary=BAD_FILENAME_SUMMARY,
            reason=GenerateFaqDraftFailure.invalid_filename,
        )

    # 3) 依据校验：无命中依据 → 不创建 approval（G4-E11）
    chunk_ids = [uuid.UUID(str(c)) for c in (source_chunk_ids or [])]
    if not chunk_ids:
        return GenerateFaqDraftToolResult(
            ok=False,
            data=None,
            summary=NO_BASIS_SUMMARY,
            reason=GenerateFaqDraftFailure.no_source,
        )

    # 4) 拉取依据片段（仅可见 kb 内的片段，避免跨库内容混入草稿）
    chunks = await _fetch_chunks(db, resolved, chunk_ids)
    if not chunks:
        return GenerateFaqDraftToolResult(
            ok=False,
            data=None,
            summary=NO_BASIS_SUMMARY,
            reason=GenerateFaqDraftFailure.no_source,
        )

    kb = await db.get(KnowledgeBase, resolved)
    kb_name = kb.name if kb is not None else ""

    # 5) 组装草稿（全文存 payload_json；出参仅摘要）
    draft = _compose_faq_draft(title=title, filename=filename, chunks=chunks)

    approval = AgentApproval(
        id=uuid.uuid4(),
        run_id=run_id,
        thread_id=thread_id,
        user_id=user_id,
        kind=ApprovalKind.adopt_faq,
        status=ApprovalStatus.pending,
        kb_id=resolved,
        filename=filename,
        payload_json={
            "title": title,
            "filename": filename,
            "markdown": draft,
            "source_chunk_ids": [str(c) for c in chunk_ids],
        },
    )
    db.add(approval)
    await db.flush()

    # G4-3.5 审计钩子：草稿生成（metadata 仅 draft_chars，无草稿全文；异常容忍）。
    await safe_audit(
        audit_agent_approval_created(
            db,
            actor_user_id=user_id,
            approval_id=approval.id,
            kb_id=resolved,
            filename=filename,
            draft_chars=len(draft),
        )
    )

    return GenerateFaqDraftToolResult(
        ok=True,
        data=GenerateFaqDraftOutput(
            approval_id=approval.id,
            filename=filename,
            kb_name=kb_name,
            draft_chars=len(draft),
            citation_count=len(chunks),
        ),
        summary=f"已生成 FAQ 草稿（{len(draft)} 字，依据 {len(chunks)} 段），待人工采纳",
    )


async def _fetch_chunks(
    db: AsyncSession,
    kb_id: uuid.UUID,
    chunk_ids: list[uuid.UUID],
) -> list[DocumentChunk]:
    stmt = select(DocumentChunk).where(
        DocumentChunk.id.in_(chunk_ids),
        DocumentChunk.kb_id == kb_id,
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


def _compose_faq_draft(
    *,
    title: str | None,
    filename: str,
    chunks: list[DocumentChunk],
) -> str:
    """依据检索片段组装 FAQ Markdown 草稿（确定性；LLM 润色在 G4-2.x 接入）。"""
    heading = (title or filename.removesuffix(".md")).strip() or "FAQ"
    lines: list[str] = [
        f"# FAQ：{heading}",
        "",
        "> 本草稿由 Agent 依据资料库检索片段生成，采纳前不落库，待人工审阅。",
        "",
    ]
    for i, ch in enumerate(chunks, start=1):
        section = ch.section_title or f"片段 {i}"
        lines.append(f"## 问：关于「{section}」")
        lines.append("")
        lines.append(f"答：{ch.content}")
        lines.append("")
    return "\n".join(lines)


__all__ = [
    "BAD_FILENAME_SUMMARY",
    "NO_BASIS_SUMMARY",
    "GenerateFaqDraftFailure",
    "GenerateFaqDraftOutput",
    "GenerateFaqDraftToolResult",
    "run_generate_faq_draft",
]
