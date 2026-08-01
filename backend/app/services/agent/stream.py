"""G3-2.3 · Agent 精准模式 SSE（tool_* → citation → token → done · R4-4）。"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.agent.finalize import prepare_agent_generation, resolve_run_status
from app.services.audit.agent import (
    audit_agent_run_completed,
    audit_llm_plan_fallback,
    audit_llm_plan_success,
)
from app.services.agent.dispatch import (
    LLMPlanner,
    LLMPlannerFactory,
    ThoroughReadPlanner,
    create_tool_planner,
)
from app.services.agent.runs import finish_agent_run
from app.services.agent.runtime import ToolPlanner, run_react_loop
from app.models.agent_approval import AgentApproval
from app.models.enums import AgentRunMode
from app.services.agent.tools.generate_faq_draft import (
    GenerateFaqDraftFailure,
    GenerateFaqDraftToolResult,
)
from app.services.agent.tools.document_write import (
    DocumentWriteFailure,
    DocumentWriteToolResult,
)
from app.services.agent.planners import (
    DocumentWritePlanner,
    create_document_write_planner,
)
from app.services.agent.tools.registry import AgentToolName
from app.services.agent.tools.scope import AgentToolScope
from app.services.agent.types import (
    AgentBudgetEvent,
    AgentRunOutcome,
    AgentStepRecord,
    ToolResultEvent,
    ToolStartEvent,
)
from app.services.org.scope import OrgScope
from app.core.latency import get_tracker
from app.services.observability.metrics_registry import inc_chat_answer, inc_chats_total
from app.services.rag.citation_align import align_citations_to_answer
from app.services.rag.confidence_reply import (
    AnswerConfidence,
    classify_answer_confidence,
    partial_answer_disclaimer_for,
)
from app.services.rag.executor import chunk_to_citation, workspace_chunk_to_citation
from app.services.rag.generation import (
    build_messages,
    compress_history,
    stream_deepseek_tokens,
    stream_no_context_reply,
)
from app.services.rag.multi_turn import prepare_multi_turn_query
from app.services.rag.persistence import save_chat_turn, save_workspace_chat_turn
from app.services.workspace.scope import WorkspaceScope


def _sse_event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


class _BufferingToolHooks:
    """收集 tool 阶段 SSE 载荷（单会话顺序执行 · 避免并发 db）。"""

    def __init__(self) -> None:
        self.events: list[tuple[str, dict]] = []

    async def on_tool_start(self, event: ToolStartEvent) -> None:
        self.events.append(
            (
                "tool_start",
                {
                    "step": event.step,
                    "tool": event.tool,
                    "args_summary": event.args_summary,
                },
            )
        )

    async def on_tool_result(self, event: ToolResultEvent) -> None:
        payload: dict[str, Any] = {
            "step": event.step,
            "tool": event.tool,
            "ok": event.ok,
            "summary": event.summary,
            "latency_ms": event.latency_ms,
        }
        if event.capped:
            payload["capped"] = True
        self.events.append(("tool_result", payload))

    async def on_agent_budget(self, event: AgentBudgetEvent) -> None:
        self.events.append(
            (
                "agent_budget",
                {
                    "steps_used": event.steps_used,
                    "max_steps": event.max_steps,
                    "capped": event.capped,
                },
            )
        )


SaveTurnFn = Callable[..., Awaitable[UUID]]


async def _stream_generation_phase(
    db: AsyncSession,
    *,
    message: str,
    gen_plan,
    outcome: AgentRunOutcome,
    user_id: UUID,
    save_turn: SaveTurnFn,
    save_kwargs: dict[str, Any],
    history: list[dict[str, str]] | None = None,
) -> AsyncIterator[str]:
    citations = list(gen_plan.citations)

    # H1：thorough 终态置信度（classify 后立刻；不改拒答阈值）
    if gen_plan.refusal:
        inc_chat_answer(AnswerConfidence.refuse.value, "thorough")
    else:
        gated_for_conf = list(gen_plan.gated_chunks)
        conf = classify_answer_confidence(gated_for_conf, message)
        inc_chat_answer(conf.value, "thorough")

    for citation in citations:
        yield _sse_event("citation", citation)

    token_parts: list[str] = []
    if gen_plan.refusal:
        token_stream = stream_no_context_reply(message)
    else:
        gated = list(gen_plan.gated_chunks)
        confidence = classify_answer_confidence(gated, message)
        if confidence is AnswerConfidence.low:
            disclaimer = partial_answer_disclaimer_for(message)
            token_parts.append(disclaimer)
            token_parts.append("\n\n")
            yield _sse_event("token", {"text": disclaimer + "\n\n"})

        compressed = await compress_history(history) if history else None

        # E4：外部工具结果注入 prompt
        enriched_message = message
        if gen_plan.external_context:
            enriched_message += f"\n\n{gen_plan.external_context}"

        messages = build_messages(
            enriched_message,
            gated,
            history=history,
            compressed_summary=compressed,
            answer_confidence=confidence,
        )
        token_stream = stream_deepseek_tokens(messages)

    async for text in token_stream:
        if text:
            token_parts.append(text)
            yield _sse_event("token", {"text": text})

    assistant_content = "".join(token_parts)

    # F1：流式 citation 为候选；done/落库按正文 [片段N] 硬对齐（拒答跳过；漏标 keep-all）
    if not gen_plan.refusal and gen_plan.gated_chunks:
        gated = list(gen_plan.gated_chunks)
        confidence = classify_answer_confidence(gated, message)
        use_workspace = bool(citations and "kb_id" in citations[0])
        to_cite = workspace_chunk_to_citation if use_workspace else chunk_to_citation
        strip = (
            partial_answer_disclaimer_for(message)
            if confidence is AnswerConfidence.low
            else None
        )
        citations = align_citations_to_answer(
            assistant_content,
            gated,
            to_citation=to_cite,
            strip_prefix=strip,
        )

    message_id = uuid.uuid4()
    retrieval_duration_ms = sum(step.latency_ms for step in outcome.steps) or None
    if retrieval_duration_ms is not None:
        get_tracker("retrieval.retrieval_e2e").record(float(retrieval_duration_ms))

    await save_turn(
        db,
        user_id=user_id,
        user_content=message,
        assistant_content=assistant_content,
        citations=citations,
        assistant_message_id=message_id,
        retrieval_duration_ms=retrieval_duration_ms,
        **save_kwargs,
    )

    await finish_agent_run(
        db,
        run_id=outcome.run_id,
        user_id=user_id,
        status=resolve_run_status(outcome),
        assistant_message_id=message_id,
    )
    await audit_agent_run_completed(
        db,
        actor_user_id=user_id,
        run_id=outcome.run_id,
        steps_used=outcome.steps_used,
        capped=outcome.capped,
        citation_count=len(citations),
    )

    yield _sse_event(
        "done",
        {
            "message_id": str(message_id),
            "citations": citations,
            "agent_run_id": str(outcome.run_id),
        },
    )


def _planner_with_retrieval_query(
    planner: ToolPlanner,
    retrieval_query: str,
) -> ToolPlanner:
    """Thorough/LLM planner 在构造时固化 query；多轮改写后须重建（不改 D2/LLM 深度逻辑）。"""
    if isinstance(planner, ThoroughReadPlanner):
        return create_tool_planner(
            retrieval_query,
            default_kb_id=planner._default_kb_id,
        )
    if isinstance(planner, LLMPlanner):
        return LLMPlannerFactory.create(
            retrieval_query,
            default_kb_id=planner.default_kb_id,
        )
    return planner


async def _stream_agent_core(
    db: AsyncSession,
    *,
    user_id: UUID,
    message: str,
    thread_id: UUID,
    workspace: WorkspaceScope,
    tool_scope: AgentToolScope,
    planner: ToolPlanner,
    org_scope: OrgScope | None,
    workspace_mode: bool,
    save_turn: SaveTurnFn,
    save_kwargs: dict[str, Any],
) -> AsyncIterator[str]:
    inc_chats_total()
    hooks = _BufferingToolHooks()

    history, retrieval_query = await prepare_multi_turn_query(
        db,
        message=message,
        user_id=user_id,
        thread_id=thread_id,
    )
    planner = _planner_with_retrieval_query(planner, retrieval_query)

    outcome = await run_react_loop(
        db,
        user_id=user_id,
        thread_id=thread_id,
        query=retrieval_query,
        workspace=workspace,
        tool_scope=tool_scope,
        planner=planner,
        org_scope=org_scope,
        hooks=hooks,
    )

    for event_name, data in hooks.events:
        yield _sse_event(event_name, data)

    gen_plan = await prepare_agent_generation(
        db,
        query=retrieval_query,
        steps=outcome.steps,
        workspace_mode=workspace_mode,
        outcome=outcome,
    )

    # 补发 LLM planner 审计（紧跟在 run 结束后，此时 outcome.run_id 已生成）
    if isinstance(planner, LLMPlanner):
        if planner.fallback_reason is not None:
            await audit_llm_plan_fallback(
                db,
                actor_user_id=user_id,
                run_id=outcome.run_id,
                reason=planner.fallback_reason,
                llm_raw=planner.last_llm_raw,
            )
        else:
            await audit_llm_plan_success(
                db,
                actor_user_id=user_id,
                run_id=outcome.run_id,
                tool_count=(
                    len(planner._cached_plan.plan)
                    if planner._cached_plan and planner._cached_plan.plan
                    else 0
                ),
                llm_raw=planner.last_llm_raw,
            )

    async for frame in _stream_generation_phase(
        db,
        message=message,
        gen_plan=gen_plan,
        outcome=outcome,
        user_id=user_id,
        save_turn=save_turn,
        save_kwargs=save_kwargs,
        history=history,
    ):
        yield frame


async def stream_agent_kb_events(
    db: AsyncSession,
    *,
    kb_id: UUID,
    user_id: UUID,
    message: str,
    thread_id: UUID,
    workspace: WorkspaceScope,
    tool_scope: AgentToolScope,
    planner: ToolPlanner,
    org_scope: OrgScope | None = None,
) -> AsyncIterator[str]:
    """库内精准模式 SSE（G3-E9 · semantic_search 默认 kb）。"""
    async for frame in _stream_agent_core(
        db,
        user_id=user_id,
        message=message,
        thread_id=thread_id,
        workspace=workspace,
        tool_scope=tool_scope,
        planner=planner,
        org_scope=org_scope,
        workspace_mode=False,
        save_turn=save_chat_turn,
        save_kwargs={"kb_id": kb_id, "thread_id": thread_id},
    ):
        yield frame


async def stream_agent_workspace_events(
    db: AsyncSession,
    *,
    scope: WorkspaceScope,
    org_scope: OrgScope | None,
    user_id: UUID,
    message: str,
    department_id: str | None,
    thread_id: UUID,
    tool_scope: AgentToolScope,
    planner: ToolPlanner,
) -> AsyncIterator[str]:
    """工作区精准模式 SSE（跨库 tool · workspace citation）。"""
    async for frame in _stream_agent_core(
        db,
        user_id=user_id,
        message=message,
        thread_id=thread_id,
        workspace=scope,
        tool_scope=tool_scope,
        planner=planner,
        org_scope=org_scope,
        workspace_mode=True,
        save_turn=save_workspace_chat_turn,
        save_kwargs={
            "workspace_kind": scope.kind,
            "workspace_org_id": scope.org_id,
            "department_id": department_id,
            "thread_id": thread_id,
        },
    ):
        yield frame


# --- G4-2.2 · 编辑模式 SSE 事件流 ----------------------------------------------

_EDIT_SUCCESS_DEBRIEF = "已根据资料库内容生成 FAQ 草稿，请在下方卡片中审阅并决定是否采纳入库。"

# approval_required 草稿预览截断上限（出参只给摘要/前段 · 不背全文）
_EDIT_DRAFT_PREVIEW_MAX = 800


def _edit_refusal_message(
    reason: GenerateFaqDraftFailure | None, summary: str
) -> str:
    """据 G4-1.3 reason 码确定性生成「助手拒答/说明」（不靠字符串匹配）。"""
    if reason is GenerateFaqDraftFailure.no_source:
        return "库内未检索到与该问题相关的依据，未能生成 FAQ 草稿。建议换一个更具体的资料库，或调整问题措辞后再试。"
    if reason is GenerateFaqDraftFailure.kb_not_visible:
        return "目标资料库不可见或无访问权限，未能生成 FAQ 草稿。请确认资料库后重试。"
    if reason is GenerateFaqDraftFailure.invalid_filename:
        return "草稿文件名格式不正确（须以 .md 结尾），未能生成 FAQ 草稿。"
    return summary or "未能生成 FAQ 草稿。"


def _find_edit_draft_step(outcome: AgentRunOutcome) -> AgentStepRecord | None:
    """末步 generate_faq_draft（编辑 planner 结构保证其在最后）。"""
    for record in reversed(outcome.steps):
        if record.tool_name == AgentToolName.generate_faq_draft.value:
            return record
    return None


def _extract_draft_result(
    step: AgentStepRecord | None,
) -> GenerateFaqDraftToolResult | None:
    if step is None:
        return None
    data = step.data
    if isinstance(data, GenerateFaqDraftToolResult):
        return data
    return None


async def _load_draft_preview(
    db: AsyncSession, approval_id: UUID
) -> tuple[UUID | None, str, str]:
    """读回 agent_approvals 取其 kb_id + 文件名 + 草稿预览（前段 · 不背全文）。"""
    approval = await db.get(AgentApproval, approval_id)
    if approval is None:
        return None, "", ""
    payload = approval.payload_json or {}
    markdown = str(payload.get("markdown", ""))
    preview = markdown[:_EDIT_DRAFT_PREVIEW_MAX] if markdown else ""
    return approval.kb_id, approval.filename, preview


async def _render_edit_sse(
    db: AsyncSession,
    *,
    outcome: AgentRunOutcome,
    tool_events: list[tuple[str, dict]],
    message: str,
    user_id: UUID,
    workspace_mode: bool,
    can_adopt: bool,
    save_turn: SaveTurnFn,
    save_kwargs: dict[str, Any],
) -> AsyncIterator[str]:
    """编辑模式 SSE 渲染（纯渲染 · 顺序硬约束）。

    顺序：tool_* → citation → token → approval_required/refusal → done。
    - 所有 tool_* 在首条 citation 之前（R4-4）；
    - citation 在首条 token 之前（R4-4）；
    - approval_required（成功）或 refusal（拒答）在 done 之前。

    草稿成功 → approval_required（含 approval_id / 草稿预览 / 来源引用 / can_adopt）；
    全无命中（G4-E11）/ 越权 / 文件名非法 → 不发 approval_required，
    改发 refusal（带 G4-1.3 reason 码文案）。

    不写库：generate_faq_draft 自身已落 agent_approvals(pending)；
    本函数仅读回预览、保存对话轮次（与 G3 同构）、结束 run。
    """
    # 1) tool 阶段事件（tool_start/tool_result/agent_budget）—— 首条 citation 之前
    for event_name, data in tool_events:
        yield _sse_event(event_name, data)

    # 2) 草稿结果（成功 / 拒答分支判定）
    draft_step = _find_edit_draft_step(outcome)
    draft_result = _extract_draft_result(draft_step)
    draft_ok = draft_result is not None and draft_result.ok
    draft_reason = draft_result.reason if draft_result is not None else None

    # 3) citation（基于只读检索命中 · R4-4：先于 token）
    gen_plan = await prepare_agent_generation(
        db,
        query=message,
        steps=outcome.steps,
        workspace_mode=workspace_mode,
        outcome=outcome,
    )
    citations = list(gen_plan.citations)
    for citation in citations:
        yield _sse_event("citation", citation)

    # 4) 助手说明 token（确定性 debrief · 不依赖 LLM 生成延迟）
    if draft_ok:
        token_text = _EDIT_SUCCESS_DEBRIEF
    else:
        summary = draft_step.summary if draft_step is not None else ""
        token_text = _edit_refusal_message(draft_reason, summary)
    yield _sse_event("token", {"text": token_text})

    # 5) 草稿成功 → approval_required；失败/拒答 → refusal（G4-E11）
    approval_id: UUID | None = None
    if draft_ok and draft_result.data is not None:
        out = draft_result.data
        approval_id = out.approval_id
        kb_id, _filename, preview = await _load_draft_preview(db, approval_id)
        yield _sse_event(
            "approval_required",
            {
                "approval_id": str(approval_id),
                "draft_type": "faq",
                "filename": out.filename,
                "kb_id": str(kb_id) if kb_id is not None else "",
                "kb_name": out.kb_name,
                "draft_preview": preview,
                "citations": citations,
                "can_adopt": can_adopt,
            },
        )
    else:
        yield _sse_event(
            "refusal",
            {
                "reason": draft_reason.value if draft_reason is not None else None,
                "message": token_text,
            },
        )

    # 6) 落库助手消息 + 结束 run + done（approval_required / refusal 均在 done 之前）
    message_id = uuid.uuid4()
    retrieval_duration_ms = sum(step.latency_ms for step in outcome.steps) or None
    await save_turn(
        db,
        user_id=user_id,
        user_content=message,
        assistant_content=token_text,
        citations=citations,
        assistant_message_id=message_id,
        retrieval_duration_ms=retrieval_duration_ms,
        **save_kwargs,
    )
    await finish_agent_run(
        db,
        run_id=outcome.run_id,
        user_id=user_id,
        status=resolve_run_status(outcome),
        assistant_message_id=message_id,
    )
    await audit_agent_run_completed(
        db,
        actor_user_id=user_id,
        run_id=outcome.run_id,
        steps_used=outcome.steps_used,
        capped=outcome.capped,
        citation_count=len(citations),
    )
    yield _sse_event(
        "done",
        {
            "message_id": str(message_id),
            "citations": citations,
            "agent_run_id": str(outcome.run_id),
            "approval_id": str(approval_id) if approval_id is not None else None,
            "approval_status": "pending" if approval_id is not None else None,
        },
    )


async def stream_agent_edit_events(
    db: AsyncSession,
    *,
    user_id: UUID,
    message: str,
    thread_id: UUID,
    workspace: WorkspaceScope,
    tool_scope: AgentToolScope,
    planner: ToolPlanner,
    org_scope: OrgScope | None = None,
    workspace_mode: bool = False,
    can_adopt: bool = False,
    save_turn: SaveTurnFn,
    save_kwargs: dict[str, Any],
) -> AsyncIterator[str]:
    """G4-2.2 · 编辑模式 SSE：驱动 planner 序列（只读步 + 末步 generate_faq_draft）

    并将过程以严格顺序推给前端：tool → citation → token → approval_required → done。

    事件顺序硬约束（R4-4 / G4 §3.3）：
    - 所有 tool_* 在首条 citation 之前；
    - citation 在首条 token 之前；
    - approval_required（或拒答 refusal）在 done 之前。

    草稿成功 → approval_required（含 approval_id / 草稿预览 / 来源引用 / can_adopt）；
    全无命中（G4-E11）或越权 / 文件名非法 → 不发 approval_required，改发 refusal
    并带 G4-1.3 reason 码文案。

    不写库：generate_faq_draft 自身已落 agent_approvals(pending)；
    本函数仅读回预览、保存对话轮次（与 G3 同构）、结束 run。

    G4-2.3 已落地：API 路由（`ask_threads.py` / `kb_threads.py`）按 `mode=edit`
    选择本函数；库内入口经 `stream_agent_kb_edit_events` 薄封装（默认目标库 =
    路径 kb · G4-E19 · `workspace_mode=False` + `save_chat_turn`）。本函数已参数化
    workspace_mode / save_turn / save_kwargs / can_adopt，调用方按入口选择即可。
    """
    hooks = _BufferingToolHooks()
    outcome = await run_react_loop(
        db,
        user_id=user_id,
        thread_id=thread_id,
        query=message,
        workspace=workspace,
        tool_scope=tool_scope,
        planner=planner,
        org_scope=org_scope,
        hooks=hooks,
        mode=AgentRunMode.edit,
    )
    async for frame in _render_edit_sse(
        db,
        outcome=outcome,
        tool_events=hooks.events,
        message=message,
        user_id=user_id,
        workspace_mode=workspace_mode,
        can_adopt=can_adopt,
        save_turn=save_turn,
        save_kwargs=save_kwargs,
    ):
        yield frame


# --- G4-2.3 · 库内编辑模式 SSE 事件流（默认目标库 = 路径 kb · G4-E19） --------


async def stream_agent_kb_edit_events(
    db: AsyncSession,
    *,
    kb_id: UUID,
    user_id: UUID,
    message: str,
    thread_id: UUID,
    workspace: WorkspaceScope,
    tool_scope: AgentToolScope,
    planner: ToolPlanner,
    org_scope: OrgScope | None = None,
    can_adopt: bool = False,
) -> AsyncIterator[str]:
    """G4-2.3 / 2.4 · 库内编辑模式 SSE（H4-2-B · 默认目标库 = 路径 kb）。

    复刻 `stream_agent_edit_events` 的编辑渲染，但固定为库内语义：
    - `workspace_mode=False` → citation 无库名前缀（同 G3-E9）；
    - `save_turn=save_chat_turn` · `save_kwargs={"kb_id","thread_id"}`；
    - 默认目标库由调用方经 `planner=create_edit_tool_planner(query, default_kb_id=kb_id)`
      截断到路径 kb（G4-E19），`generate_faq_draft` 由此落到正确库。

    事件顺序与 `approval_required`/`refusal` 语义与 `stream_agent_edit_events`
    完全一致（二者共用 `_render_edit_sse`），本函数仅封装库内落库适配器。
    """
    async for frame in stream_agent_edit_events(
        db,
        user_id=user_id,
        message=message,
        thread_id=thread_id,
        workspace=workspace,
        tool_scope=tool_scope,
        planner=planner,
        org_scope=org_scope,
        workspace_mode=False,
        can_adopt=can_adopt,
        save_turn=save_chat_turn,
        save_kwargs={"kb_id": kb_id, "thread_id": thread_id},
    ):
        yield frame


# --- G5 · 文档操作模式 SSE 事件流（delete/restore · 先提案后确认） ------------

_DOC_WRITE_SUCCESS_DEBRIEF = (
    "已在下方卡片生成操作提案，请确认是否应用。确认后将进入管理员审批流程。"
)


def _find_doc_write_step(outcome: AgentRunOutcome) -> AgentStepRecord | None:
    """末步 delete_document / restore_document（文档操作 planner 结构保证其在最后）。"""
    for record in reversed(outcome.steps):
        if record.tool_name in (
            AgentToolName.delete_document.value,
            AgentToolName.restore_document.value,
        ):
            return record
    return None


def _extract_doc_write_result(
    step: AgentStepRecord | None,
) -> DocumentWriteToolResult | None:
    if step is None:
        return None
    data = step.data
    if isinstance(data, DocumentWriteToolResult):
        return data
    return None


def _doc_write_refusal_message(
    reason: DocumentWriteFailure | None, summary: str
) -> str:
    """据 G5-1.3 reason 码确定性生成「助手说明」（不靠字符串匹配）。"""
    if reason is DocumentWriteFailure.kb_not_visible:
        return "目标资料库不可见或无访问权限，未能生成操作提案。请确认资料库后重试。"
    if reason is DocumentWriteFailure.doc_not_found:
        return "未找到匹配的目标文档（删除需 active 文档、恢复需回收站文档）。请核对文档名后重试。"
    if reason is DocumentWriteFailure.bad_request:
        return "无法理解的操作请求，请明确「删除」或「恢复」并指定文档名。"
    return summary or "未能生成操作提案。"


async def _render_document_write_sse(
    db: AsyncSession,
    *,
    outcome: AgentRunOutcome,
    tool_events: list[tuple[str, dict]],
    message: str,
    user_id: UUID,
    can_adopt: bool,
    save_turn: SaveTurnFn,
    save_kwargs: dict[str, Any],
    planner: ToolPlanner | None = None,
    double_confirm: bool = False,
) -> AsyncIterator[str]:
    """文档操作模式 SSE 渲染（纯渲染 · 顺序硬约束）。

    顺序：tool_* → token → proposal_preview / clarify / refusal → done。
    - 提案成功 → proposal_preview（含 operation/kb_id/document_id/impact/conflict/run_id）；
      不建 pending（pending 由前端确认后 POST submit 创建 · 比 FAQ 多一轮确认）。
      B 路径（fast 模式自动识别）`double_confirm=True`，前端需两次点击确认。
    - 候选多篇（B 路径歧义 · 情景 5）→ clarify（含 operation/run_id/options），
      前端点选后 POST /agent/document-write/clarify 取回提案。
    - 越权 / 文档未命中 / 操作无法解析 → refusal（带 G5-1.3 reason 码文案）。
    不写库：本函数仅保存对话轮次、结束 run。
    """
    # 1) tool 阶段事件（tool_start/tool_result/agent_budget）
    for event_name, data in tool_events:
        yield _sse_event(event_name, data)

    # 2) 提案结果（成功 / 歧义 / 拒答分支判定）
    step = _find_doc_write_step(outcome)
    result = _extract_doc_write_result(step)
    ok = result is not None and result.ok
    reason = result.reason if result is not None else None

    token_text = ""
    sse_tail: list[str] = []  # 提案/澄清/拒答事件（done 之前）

    # 2a) 歧义澄清优先（0 写结果 + planner 标记 ambiguous + 有多篇候选）
    if (
        not ok
        and planner is not None
        and getattr(planner, "ambiguous", False)
        and getattr(planner, "candidates", None)
    ):
        token_text = "检测到多篇名称相近的文档，请选择要操作的目标："
        yield _sse_event("token", {"text": token_text})
        options = [
            {
                "document_id": str(c.document_id),
                "filename": c.filename,
                "kb_id": str(c.kb_id),
            }
            for c in planner.candidates
        ]
        yield _sse_event(
            "clarify",
            {
                "operation": getattr(planner, "_op", None),
                "run_id": str(outcome.run_id),
                "options": options,
            },
        )
    elif ok and result is not None and result.proposal is not None:
        p = result.proposal
        token_text = _DOC_WRITE_SUCCESS_DEBRIEF
        yield _sse_event("token", {"text": token_text})
        yield _sse_event(
            "proposal_preview",
            {
                "operation": p.operation,
                "document_id": str(p.document_id),
                "kb_id": str(p.kb_id),
                "filename": p.filename,
                "kb_name": p.kb_name,
                "impact": p.impact,
                "conflict": p.conflict,
                "run_id": str(outcome.run_id),
                "can_adopt": can_adopt,
                "double_confirm": double_confirm,
            },
        )
    else:
        summary = step.summary if step is not None else ""
        token_text = _doc_write_refusal_message(reason, summary)
        yield _sse_event("token", {"text": token_text})
        yield _sse_event(
            "refusal",
            {
                "reason": reason.value if reason is not None else None,
                "message": token_text,
            },
        )

    # 3) 落库助手消息 + 结束 run + done（proposal_preview / clarify / refusal 均在 done 之前）
    message_id = uuid.uuid4()
    retrieval_duration_ms = sum(step.latency_ms for step in outcome.steps) or None
    await save_turn(
        db,
        user_id=user_id,
        user_content=message,
        assistant_content=token_text,
        citations=[],
        assistant_message_id=message_id,
        retrieval_duration_ms=retrieval_duration_ms,
        **save_kwargs,
    )
    await finish_agent_run(
        db,
        run_id=outcome.run_id,
        user_id=user_id,
        status=resolve_run_status(outcome),
        assistant_message_id=message_id,
    )
    await audit_agent_run_completed(
        db,
        actor_user_id=user_id,
        run_id=outcome.run_id,
        steps_used=outcome.steps_used,
        capped=outcome.capped,
        citation_count=0,
    )
    yield _sse_event(
        "done",
        {
            "message_id": str(message_id),
            "citations": [],
            "agent_run_id": str(outcome.run_id),
        },
    )


async def stream_agent_document_write_events(
    db: AsyncSession,
    *,
    user_id: UUID,
    message: str,
    thread_id: UUID,
    workspace: WorkspaceScope,
    tool_scope: AgentToolScope,
    planner: ToolPlanner,
    org_scope: OrgScope | None = None,
    workspace_mode: bool = False,
    can_adopt: bool = False,
    save_turn: SaveTurnFn,
    save_kwargs: dict[str, Any],
    double_confirm: bool = False,
) -> AsyncIterator[str]:
    """G5 · 文档操作模式 SSE：驱动 DocumentWritePlanner（search → 末步 write tool）。

    事件顺序硬约束：tool → token → proposal_preview / clarify / refusal → done。
    提案成功 → proposal_preview（不建 pending）；用户确认后由 submit 端点建 pending。
    `double_confirm=True`（B 路径）时 proposal_preview 携带该标志，前端需两次点击确认。
    """
    del workspace_mode  # 文档操作无 chunk 引用，不需 workspace/跨库 citation 模式
    hooks = _BufferingToolHooks()
    outcome = await run_react_loop(
        db,
        user_id=user_id,
        thread_id=thread_id,
        query=message,
        workspace=workspace,
        tool_scope=tool_scope,
        planner=planner,
        org_scope=org_scope,
        hooks=hooks,
        mode=AgentRunMode.document_write,
    )
    async for frame in _render_document_write_sse(
        db,
        outcome=outcome,
        tool_events=hooks.events,
        message=message,
        user_id=user_id,
        can_adopt=can_adopt,
        planner=planner,
        double_confirm=double_confirm,
        save_turn=save_turn,
        save_kwargs=save_kwargs,
    ):
        yield frame
