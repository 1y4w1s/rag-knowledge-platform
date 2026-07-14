"""G3-2.3 · Agent 精准模式 SSE（tool_* → citation → token → done · R4-4）。"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.agent.finalize import prepare_agent_generation, resolve_run_status
from app.services.audit.agent import audit_agent_run_completed
from app.services.agent.runs import finish_agent_run
from app.services.agent.runtime import ToolPlanner, run_react_loop
from app.models.agent_approval import AgentApproval
from app.models.enums import AgentRunMode
from app.services.agent.tools.generate_faq_draft import (
    GenerateFaqDraftFailure,
    GenerateFaqDraftToolResult,
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
from app.services.rag.generation import (
    build_messages,
    stream_deepseek_tokens,
    stream_no_context_reply,
)
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
) -> AsyncIterator[str]:
    citations = list(gen_plan.citations)

    for citation in citations:
        yield _sse_event("citation", citation)

    if gen_plan.refusal:
        token_stream = stream_no_context_reply(message)
    else:
        messages = build_messages(message, list(gen_plan.gated_chunks))
        token_stream = stream_deepseek_tokens(messages)

    token_parts: list[str] = []
    async for text in token_stream:
        if text:
            token_parts.append(text)
            yield _sse_event("token", {"text": text})

    assistant_content = "".join(token_parts)
    message_id = uuid.uuid4()
    retrieval_duration_ms = sum(step.latency_ms for step in outcome.steps) or None

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
    )

    for event_name, data in hooks.events:
        yield _sse_event(event_name, data)

    gen_plan = await prepare_agent_generation(
        db,
        query=message,
        steps=outcome.steps,
        workspace_mode=workspace_mode,
    )

    async for frame in _stream_generation_phase(
        db,
        message=message,
        gen_plan=gen_plan,
        outcome=outcome,
        user_id=user_id,
        save_turn=save_turn,
        save_kwargs=save_kwargs,
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
