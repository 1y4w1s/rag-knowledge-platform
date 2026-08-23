"""G3-2.3 · Agent 精准模式 SSE（tool_* → citation → token → done · R4-4）。"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import replace
from functools import partial
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.degradation import assess_degradation, degradation_requires_llm
from app.core.deps import CurrentUser
from app.models.chat_thread import ChatThread
from app.models.enums import AgentRunStatus, MessageStatus, ThreadKind
from app.services.agent.finalize import prepare_agent_generation, resolve_run_status
from app.services.audit.agent import (
    audit_agent_recovery_action,
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
from app.services.agent.runtime import (
    ToolPlanner,
    execute_accounted_recovery_step,
    run_react_loop,
)
from app.services.agent.working_memory import build_windowed_prompt_history
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
from app.services.agent.tools.registry import AgentToolName
from app.services.agent.tools.scope import FORBIDDEN_KB_SUMMARY, AgentToolScope
from app.services.agent.types import (
    AgentActionKind,
    AgentBudgetEvent,
    AgentDecision,
    AgentRunOutcome,
    AgentStepRecord,
    CriticActionRecord,
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
from app.services.rag.chat_llm import has_available_chat_provider_key
from app.services.rag.degraded_answer import stream_degraded_fragment_reply
from app.services.rag.executor import chunk_to_citation, workspace_chunk_to_citation
from app.services.rag.generation import (
    build_messages,
    stream_deepseek_tokens,
    stream_no_context_reply,
)
from app.services.rag.multi_turn import prepare_multi_turn_query
from app.services.rag.persistence import save_chat_turn
from app.services.rag.thread_persistence import (
    normalize_workspace_department_key,
    resolve_thread_for_message,
)
from app.services.rag.turn_writer import (
    TurnMessage,
    finalize_turn,
    precommit_turn_shell,
)
from app.services.workspace.scope import WorkspaceScope


logger = logging.getLogger(__name__)


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


async def _finalize_agent_turn(
    db: AsyncSession,
    *,
    thread: ChatThread,
    user_id: UUID,
    user_message_id: UUID,
    user_content: str,
    assistant_message_id: UUID,
    assistant_content: str,
    citations: list[dict],
    status: MessageStatus,
    common: dict[str, Any],
    retrieval_duration_ms: int | None,
    run_id: UUID | None,
    run_status: AgentRunStatus | None,
    audit_events: tuple = (),
) -> UUID:
    """A2：agent 三渲染路径统一收口到 turn_writer（DWC）——一次 commit。

    顺序契约：user 消息 → assistant 消息 → run 终态 → 审计事件 → 一次 db.commit()；
    run 终态经 finish_agent_run 条件更新幂等（B1），assistant_message_id 回填由
    runs.py 补充（终态已落时仅回填该字段）。
    """
    return await finalize_turn(
        db,
        thread=thread,
        user_id=user_id,
        user_msg=TurnMessage(content=user_content, message_id=user_message_id),
        assistant_msg=TurnMessage(
            content=assistant_content,
            citations=citations,
            status=status,
            message_id=assistant_message_id,
            retrieval_duration_ms=retrieval_duration_ms,
        ),
        common=common,
        run_id=run_id,
        run_status=run_status,
        audit_events=audit_events,
    )


def _agent_shell_from_save_kwargs(
    *,
    save_kwargs: dict[str, Any],
    user_id: UUID,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """从 save_kwargs 推导 (common, pending_kwargs, thread_resolve_kwargs)。

    库内（save_kwargs 含 kb_id）→ knowledge_base；否则按工作区键解析。
    thread_resolve_kwargs 即 resolve_thread_for_message 的剩余关键字（不含
    thread_id / thread_kind / kb_id / user_id）。
    """
    kb_id = save_kwargs.get("kb_id")
    if kb_id is not None:
        common: dict[str, Any] = {
            "thread_kind": ThreadKind.knowledge_base,
            "kb_id": kb_id,
            "user_id": user_id,
        }
        pending_kwargs: dict[str, Any] = {
            "thread_kind": ThreadKind.knowledge_base,
            "kb_id": kb_id,
        }
        return common, pending_kwargs, {}

    department_key = normalize_workspace_department_key(
        save_kwargs.get("department_id")
    )
    workspace_kind = save_kwargs.get("workspace_kind")
    workspace_org_id = save_kwargs.get("workspace_org_id")
    common = {
        "thread_kind": ThreadKind.workspace,
        "kb_id": None,
        "user_id": user_id,
        "workspace_kind": (
            workspace_kind.value if hasattr(workspace_kind, "value") else workspace_kind
        ),
        "workspace_org_id": workspace_org_id,
        "workspace_department_key": department_key,
    }
    pending_kwargs = {
        "thread_kind": ThreadKind.workspace,
        "workspace_kind": (
            workspace_kind.value if hasattr(workspace_kind, "value") else workspace_kind
        ),
        "workspace_org_id": workspace_org_id,
        "workspace_department_key": department_key,
    }
    return common, pending_kwargs, {
        "workspace_kind": workspace_kind,
        "workspace_org_id": workspace_org_id,
        "department_key": department_key,
    }


async def _precommit_for_save_kwargs(
    db: AsyncSession,
    *,
    save_kwargs: dict[str, Any],
    user_id: UUID,
    message: str,
    thread_id: UUID | None = None,
) -> tuple[ChatThread, UUID, UUID, dict[str, Any]]:
    """edit/document_write 共用：解析 thread（库内/工作区）→ 预提交外壳。

    返回 (thread, user_message_id, assistant_message_id, common)。
    """
    common, pending_kwargs, resolve_kwargs = _agent_shell_from_save_kwargs(
        save_kwargs=save_kwargs,
        user_id=user_id,
    )
    resolved_thread_id = thread_id or save_kwargs.get("thread_id")
    thread = await resolve_thread_for_message(
        db,
        thread_id=resolved_thread_id,
        thread_kind=common["thread_kind"],
        kb_id=common.get("kb_id"),
        user_id=user_id,
        **resolve_kwargs,
    )
    common = {**common, "thread_id": thread.id}
    user_message_id, assistant_message_id = await precommit_turn_shell(
        db,
        thread=thread,
        user_id=user_id,
        user_content=message,
        common=common,
        pending_kwargs=pending_kwargs,
    )
    return thread, user_message_id, assistant_message_id, common


async def _stream_generation_phase(
    db: AsyncSession,
    *,
    message: str,
    gen_plan,
    outcome: AgentRunOutcome,
    user_id: UUID,
    history: list[dict[str, str]] | None = None,
    assistant_message_id: UUID,
    state: dict[str, Any],
    workspace: WorkspaceScope | None = None,
    tool_scope: AgentToolScope | None = None,
    org_scope: OrgScope | None = None,
    workspace_mode: bool = False,
    retrieval_query: str | None = None,
    default_kb_id: UUID | None = None,
    thread_id: UUID | None = None,
    hooks: _BufferingToolHooks | None = None,
    current_user: CurrentUser | None = None,
) -> AsyncIterator[str]:
    """生成阶段事件流（citation → token → done；A2：纯渲染，落库由 core finally 统一收口）。"""
    citations = list(gen_plan.citations)
    active_plan = gen_plan
    query_for_gen = retrieval_query or message

    # H1：thorough 终态置信度（classify 后立刻；不改拒答阈值）
    if active_plan.refusal:
        inc_chat_answer(AnswerConfidence.refuse.value, "thorough")
    else:
        gated_for_conf = list(active_plan.gated_chunks)
        conf = classify_answer_confidence(gated_for_conf, message)
        inc_chat_answer(conf.value, "thorough")

    if not settings.rag_critic_enabled:
        for citation in citations:
            yield _sse_event("citation", citation)

    token_parts: list[str] = []
    if active_plan.refusal:
        token_stream = stream_no_context_reply(message)
    else:
        gated = list(active_plan.gated_chunks)
        confidence = classify_answer_confidence(gated, message)
        if (
            not degradation_requires_llm(assess_degradation())
            or not has_available_chat_provider_key()
        ):
            # L1：LLM 全挂 / 未配置任何 chat provider key 时
            # 跳过历史窗口化/build_messages，直接返回原文片段
            token_stream = stream_degraded_fragment_reply(message, gated)
        else:
            if confidence is AnswerConfidence.low:
                disclaimer = partial_answer_disclaimer_for(message)
                token_parts.append(disclaimer)
                token_parts.append("\n\n")
                if not settings.rag_critic_enabled:
                    yield _sse_event("token", {"text": disclaimer + "\n\n"})

            if history:
                windowed = build_windowed_prompt_history(
                    history,
                    max_messages=settings.agent_memory_window_max_messages,
                    token_budget=settings.agent_memory_window_token_budget,
                    min_keep=settings.agent_memory_window_min_keep,
                    summary_prefix=settings.agent_memory_window_summary_prefix,
                    summary_max=settings.agent_memory_window_summary_max,
                )
                history = windowed.history

            # E4：外部工具结果注入 prompt
            enriched_message = message
            if active_plan.external_context:
                enriched_message += f"\n\n{active_plan.external_context}"

            messages = build_messages(
                enriched_message,
                gated,
                history=history,
                compressed_summary=None,
                answer_confidence=confidence,
            )
            token_stream = stream_deepseek_tokens(messages)

    try:
        async for text in token_stream:
            if text:
                token_parts.append(text)
                if not settings.rag_critic_enabled:
                    yield _sse_event("token", {"text": text})
    except Exception as exc:
        # L1 异常兜底：provider 双失败把熔断器打开后的竞争窗口切到降级流
        if active_plan.refusal:
            raise
        logger.warning(
            "module=rag_degradation operation=llm_all_down mode=thorough error=%s",
            exc,
        )
        async for text in stream_degraded_fragment_reply(
            message, list(active_plan.gated_chunks)
        ):
            if text:
                token_parts.append(text)
                if not settings.rag_critic_enabled:
                    yield _sse_event("token", {"text": text})

    assistant_content = "".join(token_parts)

    # ── G1-W1b Critic（默认关）+ L3-W7 定向再检索回流（另 flag，默认关）──
    critic_fail_closed = False
    force_critic_fail_closed = False
    if (
        settings.rag_critic_enabled
        and not active_plan.refusal
        and active_plan.gated_chunks
    ):
        from app.services.rag.confidence_reply import with_partial_disclaimer
        from app.services.rag.critic import (
            CriticAction,
            CriticResult,
            run_critic,
        )
        from app.services.rag.feedback_attribution import LABEL_UNKNOWN
        from app.services.rag.generation import (
            no_context_reply_for,
            revise_answer_from_existing_evidence,
        )

        gated = list(active_plan.gated_chunks)
        confidence = classify_answer_confidence(gated, message)
        body_for_critic = assistant_content
        if confidence is AnswerConfidence.low:
            prefix = partial_answer_disclaimer_for(message) + "\n\n"
            if body_for_critic.startswith(prefix):
                body_for_critic = body_for_critic[len(prefix) :]
        action_count_before = len(getattr(outcome, "critic_actions", ()))
        validation_attempt_count = 1
        try:
            deadline_monotonic = getattr(outcome, "deadline_monotonic", None)
            remaining = (
                deadline_monotonic - time.monotonic()
                if deadline_monotonic is not None
                else None
            )
            if remaining is not None and remaining <= 0:
                validation_attempt_count = 0
                raise TimeoutError("initial critic deadline exhausted")
            if remaining is not None:
                critic_result = await asyncio.wait_for(
                    run_critic(body_for_critic, gated, message),
                    timeout=remaining,
                )
            else:
                critic_result = await run_critic(body_for_critic, gated, message)
            if isinstance(outcome, AgentRunOutcome):
                outcome = replace(
                    outcome,
                    critic_validation_count=outcome.critic_validation_count + 1,
                )
        except Exception as exc:
            validation_status = (
                "deadline_exhausted"
                if isinstance(exc, TimeoutError)
                else "failed"
            )
            critic_result = CriticResult(
                ok=False,
                claims=(),
                label=LABEL_UNKNOWN,
                rationale="initial semantic validation unavailable",
                method="control_plane_failure",
                recommended_action=CriticAction.REFUSE,
            )
            if isinstance(outcome, AgentRunOutcome):
                outcome = replace(
                    outcome,
                    timed_out=(
                        outcome.timed_out
                        or validation_status == "deadline_exhausted"
                    ),
                    critic_actions=(
                        *outcome.critic_actions,
                        CriticActionRecord(
                            action="SEMANTIC_VALIDATION",
                            status=validation_status,
                            attempt_count=validation_attempt_count,
                            reason_code="deadline_or_critic_failure",
                        ),
                    ),
                )
                await audit_agent_recovery_action(
                    db,
                    actor_user_id=user_id,
                    run_id=outcome.run_id,
                    action="SEMANTIC_VALIDATION",
                    status=validation_status,
                    budget_before=1,
                    budget_after=0,
                    attempt_count=validation_attempt_count,
                )

        # Outer owner executes one named action; critic remains advisory.
        recommendation_handled = False
        if (
            not critic_result.ok
            and critic_result.recommended_action
            is CriticAction.RETRIEVE_MISSING_EVIDENCE
            and settings.agent_l3_critic_retrieval_enabled
            and workspace is not None
            and tool_scope is not None
            and thread_id is not None
        ):
            hook_offset = len(hooks.events) if hooks is not None else 0
            revised = await _maybe_critic_retrieve_and_revise(
                db,
                message=message,
                query_for_gen=query_for_gen,
                critic_result=critic_result,
                outcome=outcome,
                active_plan=active_plan,
                history=history,
                workspace=workspace,
                tool_scope=tool_scope,
                org_scope=org_scope,
                workspace_mode=workspace_mode,
                default_kb_id=default_kb_id,
                user_id=user_id,
                thread_id=thread_id,
                hooks=hooks,
                current_user=current_user,
            )
            if hooks is not None:
                for event_name, data in hooks.events[hook_offset:]:
                    yield _sse_event(event_name, data)
            if revised is not None:
                outcome, revised_plan, revised_content, revised_critic = revised
                recommendation_handled = any(
                    record.action
                    == CriticAction.RETRIEVE_MISSING_EVIDENCE.value
                    for record in outcome.critic_actions[action_count_before:]
                )
                if (
                    revised_plan is None
                    and outcome.steps
                    and not outcome.steps[-1].ok
                    and outcome.steps[-1].summary == FORBIDDEN_KB_SUMMARY
                ):
                    force_critic_fail_closed = True
                if revised_plan is not None and revised_content is not None:
                    active_plan = revised_plan
                    assistant_content = revised_content
                    critic_result = revised_critic
                    recommendation_handled = False
                    gated = list(active_plan.gated_chunks)
                    citations = list(active_plan.citations)
                    confidence = classify_answer_confidence(gated, message)
        elif (
            not critic_result.ok
            and critic_result.recommended_action
            is CriticAction.REVISE_FROM_EXISTING_EVIDENCE
            and getattr(outcome, "critic_revision_count", 0) < 1
        ):
            issues = critic_result.metadata.get("critic.issues") or [
                critic_result.rationale
            ]
            revised_content = None
            revision_status = "failed"
            revision_attempt_count = 1
            try:
                remaining = (
                    outcome.deadline_monotonic - time.monotonic()
                    if isinstance(outcome, AgentRunOutcome)
                    and outcome.deadline_monotonic is not None
                    else None
                )
                if remaining is not None and remaining <= 0:
                    revision_status = "deadline_exhausted"
                    revision_attempt_count = 0
                elif remaining is not None:
                    revised_content = await asyncio.wait_for(
                        revise_answer_from_existing_evidence(
                            body_for_critic,
                            gated,
                            message,
                            "\n".join(str(item) for item in issues),
                        ),
                        timeout=max(0.001, remaining),
                    )
                else:
                    revised_content = await revise_answer_from_existing_evidence(
                        body_for_critic,
                        gated,
                        message,
                        "\n".join(str(item) for item in issues),
                    )
            except TimeoutError:
                revision_status = "deadline_exhausted"
                logger.warning(
                    "module=rag_critic operation=revise_existing_deadline",
                    exc_info=True,
                )
            except Exception:
                logger.warning(
                    "module=rag_critic operation=revise_existing_failed",
                    exc_info=True,
                )
            if revised_content:
                revision_status = "executed"
            if isinstance(outcome, AgentRunOutcome):
                outcome = replace(
                    outcome,
                    timed_out=(
                        outcome.timed_out
                        or revision_status == "deadline_exhausted"
                    ),
                    critic_revision_count=outcome.critic_revision_count + 1,
                    critic_actions=(
                        *outcome.critic_actions,
                        CriticActionRecord(
                            action="REVISE_FROM_EXISTING_EVIDENCE",
                            status=revision_status,
                            attempt_count=revision_attempt_count,
                            reason_code="critic_recommended_revision",
                        ),
                    ),
                )
                await audit_agent_recovery_action(
                    db,
                    actor_user_id=user_id,
                    run_id=outcome.run_id,
                    action="REVISE_FROM_EXISTING_EVIDENCE",
                    status=revision_status,
                    budget_before=1,
                    budget_after=0,
                    attempt_count=revision_attempt_count,
                )
                recommendation_handled = True
            if revised_content:
                if confidence is AnswerConfidence.low:
                    revised_content = with_partial_disclaimer(
                        message, revised_content
                    )
                assistant_content = revised_content
                body = revised_content
                if confidence is AnswerConfidence.low:
                    prefix = partial_answer_disclaimer_for(message) + "\n\n"
                    if body.startswith(prefix):
                        body = body[len(prefix) :]
                post_revision_critic = None
                post_validation_attempt_count = 1
                try:
                    remaining = (
                        outcome.deadline_monotonic - time.monotonic()
                        if isinstance(outcome, AgentRunOutcome)
                        and outcome.deadline_monotonic is not None
                        else None
                    )
                    if remaining is not None and remaining <= 0:
                        post_validation_attempt_count = 0
                        raise TimeoutError(
                            "post-revision critic deadline exhausted"
                        )
                    if remaining is not None:
                        post_revision_critic = await asyncio.wait_for(
                            run_critic(body, gated, message),
                            timeout=max(0.001, remaining),
                        )
                    else:
                        post_revision_critic = await run_critic(
                            body, gated, message
                        )
                except Exception as exc:
                    validation_status = (
                        "deadline_exhausted"
                        if isinstance(exc, TimeoutError)
                        else "failed"
                    )
                    logger.warning(
                        "module=rag_critic operation=post_revision_validation_failed",
                        exc_info=True,
                    )
                    if isinstance(outcome, AgentRunOutcome):
                        outcome = replace(
                            outcome,
                            timed_out=(
                                outcome.timed_out
                                or validation_status == "deadline_exhausted"
                            ),
                            critic_actions=(
                                *outcome.critic_actions,
                                CriticActionRecord(
                                    action="POST_REVISION_VALIDATION",
                                    status=validation_status,
                                    attempt_count=post_validation_attempt_count,
                                    reason_code="deadline_or_critic_failure",
                                ),
                            ),
                        )
                        await audit_agent_recovery_action(
                            db,
                            actor_user_id=user_id,
                            run_id=outcome.run_id,
                            action="POST_REVISION_VALIDATION",
                            status=validation_status,
                            budget_before=1,
                            budget_after=0,
                            attempt_count=post_validation_attempt_count,
                        )
                if post_revision_critic is not None:
                    critic_result = post_revision_critic
                    recommendation_handled = False
                if (
                    post_revision_critic is not None
                    and isinstance(outcome, AgentRunOutcome)
                ):
                    outcome = replace(
                        outcome,
                        critic_validation_count=(
                            outcome.critic_validation_count + 1
                        ),
                    )

        if not critic_result.ok and isinstance(outcome, AgentRunOutcome):
            recommendation = critic_result.recommended_action
            action_name = recommendation.value
            handled = recommendation_handled
            status: str | None = None
            reason_code = "critic_recommendation_unavailable"
            if recommendation is CriticAction.REFUSE:
                status = "executed"
                reason_code = "critic_recommended_refuse"
                force_critic_fail_closed = True
                outcome = replace(
                    outcome,
                    terminal_decision=AgentDecision(
                        action=AgentActionKind.refuse,
                        reason_code=reason_code,
                    ),
                )
            elif recommendation is CriticAction.CLARIFY:
                status = "mapped_to_refuse"
                reason_code = "critic_clarify_fail_closed"
                force_critic_fail_closed = True
                outcome = replace(
                    outcome,
                    terminal_decision=AgentDecision(
                        action=AgentActionKind.refuse,
                        reason_code=reason_code,
                    ),
                )
            elif not handled:
                if recommendation is CriticAction.RETRIEVE_MISSING_EVIDENCE:
                    status = "skipped_disabled"
                    reason_code = "critic_retrieval_unavailable"
                elif recommendation is CriticAction.REVISE_FROM_EXISTING_EVIDENCE:
                    status = "skipped_unavailable"
                    reason_code = "critic_revision_unavailable"

            if status is not None and not handled:
                outcome = replace(
                    outcome,
                    critic_actions=(
                        *outcome.critic_actions,
                        CriticActionRecord(
                            action=action_name,
                            status=status,
                            attempt_count=0,
                            reason_code=reason_code,
                        ),
                    ),
                )
                await audit_agent_recovery_action(
                    db,
                    actor_user_id=user_id,
                    run_id=outcome.run_id,
                    action=action_name,
                    status=status,
                    budget_before=0,
                    budget_after=0,
                    attempt_count=0,
                )

        if not critic_result.ok:
            on_fail = (settings.rag_critic_on_fail or "fail_closed").strip().lower()
            if on_fail == "annotate_only" and not force_critic_fail_closed:
                logger.info(
                    "module=rag_critic operation=annotate_only label=%s rationale=%s",
                    critic_result.label,
                    critic_result.rationale,
                )
            else:
                assistant_content = no_context_reply_for(message)
                citations = []
                critic_fail_closed = True

    # F1：流式 citation 为候选；done/落库按正文 [片段N] 硬对齐（拒答跳过；漏标 keep-all）
    if (
        not critic_fail_closed
        and not active_plan.refusal
        and active_plan.gated_chunks
    ):
        gated = list(active_plan.gated_chunks)
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

    if settings.rag_critic_enabled:
        for citation in citations:
            yield _sse_event("citation", citation)
        yield _sse_event("token", {"text": assistant_content})

    message_id = assistant_message_id
    retrieval_duration_ms = sum(step.latency_ms for step in outcome.steps) or None
    if retrieval_duration_ms is not None:
        get_tracker("retrieval.retrieval_e2e").record(float(retrieval_duration_ms))

    # A2：落库信息交给 core finally（finalize_turn 单次 commit），此处仅记录状态。
    state["content"] = assistant_content
    state["citations"] = citations
    state["retrieval_duration_ms"] = retrieval_duration_ms
    state["outcome"] = outcome

    yield _sse_event(
        "done",
        {
            "message_id": str(message_id),
            "citations": citations,
            "agent_run_id": str(outcome.run_id),
        },
    )


async def _maybe_critic_retrieve_and_revise(
    db: AsyncSession,
    *,
    message: str,
    query_for_gen: str,
    critic_result,
    outcome: AgentRunOutcome,
    active_plan,
    history: list[dict[str, str]] | None,
    workspace: WorkspaceScope,
    tool_scope: AgentToolScope,
    org_scope: OrgScope | None,
    workspace_mode: bool,
    default_kb_id: UUID | None,
    user_id: UUID,
    thread_id: UUID,
    hooks: _BufferingToolHooks | None,
    current_user: CurrentUser | None,
):
    """Outer-owned bounded retrieve/revise/revalidate action."""
    from app.services.agent.finalize import gate_agent_chunks, merge_step_hits_to_chunks
    from app.services.agent.planners import plan_critic_directed_retrieval
    from app.services.rag.critic import build_critic_retrieval_gap, run_critic

    gap = build_critic_retrieval_gap(critic_result, original_query=message)
    decision = plan_critic_directed_retrieval(
        gap,
        steps_used=outcome.steps_used,
        max_steps=outcome.max_steps,
        default_kb_id=default_kb_id,
        already_used=outcome.critic_recovery_count,
    )
    if decision is None:
        if (
            gap is not None
            and (
                outcome.critic_recovery_count >= 1
                or outcome.steps_used >= outcome.max_steps
            )
        ):
            remaining = max(0, outcome.max_steps - outcome.steps_used)
            await audit_agent_recovery_action(
                db,
                actor_user_id=user_id,
                run_id=outcome.run_id,
                action="RETRIEVE_MISSING_EVIDENCE",
                status="budget_exhausted",
                budget_before=remaining,
                budget_after=remaining,
            )
            outcome = replace(
                outcome,
                critic_actions=(
                    *outcome.critic_actions,
                    CriticActionRecord(
                        action="RETRIEVE_MISSING_EVIDENCE",
                        status="budget_exhausted",
                        attempt_count=0,
                        reason_code="critic_directed_retrieve",
                    ),
                ),
            )
            return outcome, None, None, None
        return None

    updated_outcome = await execute_accounted_recovery_step(
        db,
        outcome=outcome,
        decision=decision,
        user_id=user_id,
        thread_id=thread_id,
        workspace=workspace,
        tool_scope=tool_scope,
        hooks=hooks,
        org_scope=org_scope,
        current_user=current_user,
    )
    if len(updated_outcome.steps) == len(outcome.steps):
        if updated_outcome is not outcome:
            return updated_outcome, None, None, None
        return None
    recover_record = updated_outcome.steps[-1]
    if not recover_record.ok or recover_record.data is None:
        return updated_outcome, None, None, None
    new_chunks = await merge_step_hits_to_chunks(db, (recover_record,))
    if not new_chunks:
        return updated_outcome, None, None, None

    combined = {c.chunk_id: c for c in active_plan.gated_chunks}
    for chunk in new_chunks:
        combined[chunk.chunk_id] = chunk
    revised_plan = gate_agent_chunks(
        query_for_gen,
        list(combined.values()),
        workspace_mode=workspace_mode,
    )
    if revised_plan.refusal or not revised_plan.gated_chunks:
        return updated_outcome, None, None, None

    gated = list(revised_plan.gated_chunks)
    confidence = classify_answer_confidence(gated, message)
    updated_outcome = replace(
        updated_outcome,
        critic_revision_count=updated_outcome.critic_revision_count + 1,
    )

    async def _collect_revised_parts() -> list[str]:
        parts: list[str] = []
        if (
            not degradation_requires_llm(assess_degradation())
            or not has_available_chat_provider_key()
        ):
            async for text in stream_degraded_fragment_reply(message, gated):
                if text:
                    parts.append(text)
        else:
            if confidence is AnswerConfidence.low:
                parts.append(partial_answer_disclaimer_for(message))
                parts.append("\n\n")
            enriched = message
            if revised_plan.external_context:
                enriched += f"\n\n{revised_plan.external_context}"
            messages = build_messages(
                enriched,
                gated,
                history=history,
                compressed_summary=None,
                answer_confidence=confidence,
            )
            async for text in stream_deepseek_tokens(messages):
                if text:
                    parts.append(text)
        return parts

    revision_attempt_count = 1
    try:
        remaining = (
            updated_outcome.deadline_monotonic - time.monotonic()
            if updated_outcome.deadline_monotonic is not None
            else None
        )
        if remaining is not None and remaining <= 0:
            revision_attempt_count = 0
            raise TimeoutError("critic recovery revision deadline exhausted")
        if remaining is not None:
            revised_parts = await asyncio.wait_for(
                _collect_revised_parts(),
                timeout=max(0.001, remaining),
            )
        else:
            revised_parts = await _collect_revised_parts()
    except Exception as exc:
        revision_status = (
            "deadline_exhausted" if isinstance(exc, TimeoutError) else "failed"
        )
        logger.warning(
            "module=rag_critic operation=revise_llm_failed",
            exc_info=True,
        )
        updated_outcome = replace(
            updated_outcome,
            timed_out=(
                updated_outcome.timed_out
                or revision_status == "deadline_exhausted"
            ),
            critic_actions=(
                *updated_outcome.critic_actions,
                CriticActionRecord(
                    action="REVISE_FROM_EXISTING_EVIDENCE",
                    status=revision_status,
                    attempt_count=revision_attempt_count,
                    reason_code="critic_retrieval_revision",
                ),
            ),
        )
        await audit_agent_recovery_action(
            db,
            actor_user_id=user_id,
            run_id=updated_outcome.run_id,
            action="REVISE_FROM_EXISTING_EVIDENCE",
            status=revision_status,
            budget_before=1,
            budget_after=0,
            attempt_count=revision_attempt_count,
        )
        return updated_outcome, None, None, None

    revised_content = "".join(revised_parts)
    if not revised_content:
        updated_outcome = replace(
            updated_outcome,
            critic_actions=(
                *updated_outcome.critic_actions,
                CriticActionRecord(
                    action="REVISE_FROM_EXISTING_EVIDENCE",
                    status="failed",
                    attempt_count=1,
                    reason_code="critic_retrieval_revision",
                ),
            ),
        )
        await audit_agent_recovery_action(
            db,
            actor_user_id=user_id,
            run_id=updated_outcome.run_id,
            action="REVISE_FROM_EXISTING_EVIDENCE",
            status="failed",
            budget_before=1,
            budget_after=0,
            attempt_count=1,
        )
        return updated_outcome, None, None, None
    body = revised_content
    if confidence is AnswerConfidence.low:
        prefix = partial_answer_disclaimer_for(message) + "\n\n"
        if body.startswith(prefix):
            body = body[len(prefix) :]
    updated_outcome = replace(
        updated_outcome,
        critic_actions=(
            *updated_outcome.critic_actions,
            CriticActionRecord(
                action="REVISE_FROM_EXISTING_EVIDENCE",
                status="executed",
                attempt_count=1,
                reason_code="critic_retrieval_revision",
            ),
        ),
    )
    await audit_agent_recovery_action(
        db,
        actor_user_id=user_id,
        run_id=updated_outcome.run_id,
        action="REVISE_FROM_EXISTING_EVIDENCE",
        status="executed",
        budget_before=1,
        budget_after=0,
        attempt_count=1,
    )
    remaining = (
        updated_outcome.deadline_monotonic - time.monotonic()
        if updated_outcome.deadline_monotonic is not None
        else None
    )
    post_validation_attempt_count = 1
    try:
        if remaining is not None and remaining <= 0:
            post_validation_attempt_count = 0
            raise TimeoutError("post-revision critic deadline exhausted")
        if remaining is not None:
            new_critic = await asyncio.wait_for(
                run_critic(body, gated, message),
                timeout=max(0.001, remaining),
            )
        else:
            new_critic = await run_critic(body, gated, message)
    except Exception as exc:
        validation_status = (
            "deadline_exhausted" if isinstance(exc, TimeoutError) else "failed"
        )
        updated_outcome = replace(
            updated_outcome,
            timed_out=(
                updated_outcome.timed_out
                or validation_status == "deadline_exhausted"
            ),
            critic_actions=(
                *updated_outcome.critic_actions,
                CriticActionRecord(
                    action="POST_REVISION_VALIDATION",
                    status=validation_status,
                    attempt_count=post_validation_attempt_count,
                    reason_code="deadline_or_critic_failure",
                ),
            ),
        )
        await audit_agent_recovery_action(
            db,
            actor_user_id=user_id,
            run_id=updated_outcome.run_id,
            action="POST_REVISION_VALIDATION",
            status=validation_status,
            budget_before=1,
            budget_after=0,
            attempt_count=post_validation_attempt_count,
        )
        return updated_outcome, None, None, None
    updated_outcome = replace(
        updated_outcome,
        critic_validation_count=updated_outcome.critic_validation_count + 1,
    )
    return updated_outcome, revised_plan, revised_content, new_critic


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
    current_user: CurrentUser | None = None,
    workspace_mode: bool,
    thread: ChatThread,
    user_message_id: UUID,
    assistant_message_id: UUID,
    common: dict[str, Any],
) -> AsyncIterator[str]:
    """thorough 精准模式核心流（A2：预提交外壳 → 事件流 → finally 单一提交兜底）。"""
    inc_chats_total()
    hooks = _BufferingToolHooks()
    state: dict[str, Any] = {
        "content": "",
        "citations": [],
        "retrieval_duration_ms": None,
        "done_yielded": False,
    }
    token_parts: list[str] = []
    outcome: AgentRunOutcome | None = None
    try:
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
            current_user=current_user,
            hooks=hooks,
            # The outer owner keeps the run open for every critic action,
            # including revision-only paths that do not enable retrieval.
            defer_finish=settings.rag_critic_enabled,
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

        # 补发 LLM planner 审计（紧跟在 run 结束后，随 finalize 单一提交落库）
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
            history=history,
            assistant_message_id=assistant_message_id,
            state=state,
            workspace=workspace,
            tool_scope=tool_scope,
            org_scope=org_scope,
            workspace_mode=workspace_mode,
            retrieval_query=retrieval_query,
            default_kb_id=getattr(planner, "default_kb_id", None)
            or getattr(planner, "_default_kb_id", None),
            thread_id=thread_id,
            hooks=hooks,
            current_user=current_user,
        ):
            if frame.startswith("event: token"):
                try:
                    payload = json.loads(frame.split("data: ", 1)[1].strip())
                    text = payload.get("text", "")
                    if text:
                        token_parts.append(text)
                except Exception:
                    pass
            if frame.startswith("event: done"):
                state["done_yielded"] = True
            yield frame
        outcome = state.get("outcome", outcome)
    finally:
        # A2（P1-08）：正常完成 / 断线（GeneratorExit）/ 异常均收敛到单一提交。
        status = (
            MessageStatus.completed
            if state["done_yielded"]
            else MessageStatus.interrupted
        )
        content = state["content"] or "".join(token_parts)
        citations = state["citations"] or []
        retrieval_ms = state["retrieval_duration_ms"]
        run_status = (
            resolve_run_status(outcome)
            if outcome is not None
            else AgentRunStatus.failed
        )
        audit_events: tuple = ()
        if outcome is not None:
            audit_events = (
                partial(
                    audit_agent_run_completed,
                    actor_user_id=user_id,
                    run_id=outcome.run_id,
                    steps_used=outcome.steps_used,
                    capped=outcome.capped,
                    citation_count=len(citations),
                ),
            )
        await _finalize_agent_turn(
            db,
            thread=thread,
            user_id=user_id,
            user_message_id=user_message_id,
            user_content=message,
            assistant_message_id=assistant_message_id,
            assistant_content=content,
            citations=citations,
            status=status,
            common=common,
            retrieval_duration_ms=retrieval_ms,
            run_id=outcome.run_id if outcome is not None else None,
            run_status=run_status,
            audit_events=audit_events,
        )


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
    current_user: CurrentUser | None = None,
) -> AsyncIterator[str]:
    """库内精准模式 SSE（G3-E9 · semantic_search 默认 kb；A2 DWC 预提交 + 兜底）。"""
    thread = await resolve_thread_for_message(
        db,
        thread_id=thread_id,
        thread_kind=ThreadKind.knowledge_base,
        kb_id=kb_id,
        user_id=user_id,
    )
    common = {
        "thread_kind": ThreadKind.knowledge_base,
        "kb_id": kb_id,
        "user_id": user_id,
        "thread_id": thread.id,
    }
    user_message_id, assistant_message_id = await precommit_turn_shell(
        db,
        thread=thread,
        user_id=user_id,
        user_content=message,
        common=common,
        pending_kwargs={
            "thread_kind": ThreadKind.knowledge_base,
            "kb_id": kb_id,
        },
    )
    stream = _stream_agent_core(
        db,
        user_id=user_id,
        message=message,
        thread_id=thread.id,
        workspace=workspace,
        tool_scope=tool_scope,
        planner=planner,
        org_scope=org_scope,
        current_user=current_user,
        workspace_mode=False,
        thread=thread,
        user_message_id=user_message_id,
        assistant_message_id=assistant_message_id,
        common=common,
    )
    try:
        async for frame in stream:
            yield frame
    finally:
        # 外层 GeneratorExit（客户端断开）不会自动传入内层生成器；
        # 显式 aclose 让 _stream_agent_core 的 finally 兜底落库（P1-08）。
        await stream.aclose()


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
    current_user: CurrentUser | None = None,
) -> AsyncIterator[str]:
    """工作区精准模式 SSE（跨库 tool · workspace citation；A2 DWC 预提交 + 兜底）。"""
    department_key = normalize_workspace_department_key(department_id)
    thread = await resolve_thread_for_message(
        db,
        thread_id=thread_id,
        thread_kind=ThreadKind.workspace,
        kb_id=None,
        user_id=user_id,
        workspace_kind=scope.kind,
        workspace_org_id=scope.org_id,
        department_key=department_key,
    )
    common = {
        "thread_kind": ThreadKind.workspace,
        "kb_id": None,
        "user_id": user_id,
        "workspace_kind": scope.kind.value,
        "workspace_org_id": scope.org_id,
        "workspace_department_key": department_key,
        "thread_id": thread.id,
    }
    user_message_id, assistant_message_id = await precommit_turn_shell(
        db,
        thread=thread,
        user_id=user_id,
        user_content=message,
        common=common,
        pending_kwargs={
            "thread_kind": ThreadKind.workspace,
            "workspace_kind": scope.kind.value,
            "workspace_org_id": scope.org_id,
            "workspace_department_key": department_key,
        },
    )
    stream = _stream_agent_core(
        db,
        user_id=user_id,
        message=message,
        thread_id=thread.id,
        workspace=scope,
        tool_scope=tool_scope,
        planner=planner,
        org_scope=org_scope,
        current_user=current_user,
        workspace_mode=True,
        thread=thread,
        user_message_id=user_message_id,
        assistant_message_id=assistant_message_id,
        common=common,
    )
    try:
        async for frame in stream:
            yield frame
    finally:
        await stream.aclose()


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
    if reason is GenerateFaqDraftFailure.quota_exceeded:
        return "今日或本对话的 FAQ 草稿生成次数已达上限，请稍后再试。"
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
    assistant_message_id: UUID,
    state: dict[str, Any],
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
    本函数仅渲染事件并记录 state（落库由 stream_agent_edit_events 的 finally 统一收口，A2）。
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

    # 6) done（approval_required / refusal 均在 done 之前；落库由调用方 finally 收口）
    retrieval_duration_ms = sum(step.latency_ms for step in outcome.steps) or None
    state["content"] = token_text
    state["citations"] = citations
    state["retrieval_duration_ms"] = retrieval_duration_ms
    yield _sse_event(
        "done",
        {
            "message_id": str(assistant_message_id),
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
    current_user: CurrentUser | None = None,
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

    A2（DWC）：入口预提交 user + pending assistant（P1-08）；finally 经
    finalize_turn 单次 commit（断线/异常以 partial + interrupted 兜底）。
    """
    del save_turn  # A2：落库统一走 finalize_turn，save_turn 仅保留签名兼容
    thread, user_message_id, assistant_message_id, common = (
        await _precommit_for_save_kwargs(
            db,
            save_kwargs=save_kwargs,
            user_id=user_id,
            message=message,
            thread_id=thread_id,
        )
    )
    hooks = _BufferingToolHooks()
    state: dict[str, Any] = {
        "content": "",
        "citations": [],
        "retrieval_duration_ms": None,
        "done_yielded": False,
    }
    outcome: AgentRunOutcome | None = None
    try:
        outcome = await run_react_loop(
            db,
            user_id=user_id,
            thread_id=thread.id,
            query=message,
            workspace=workspace,
            tool_scope=tool_scope,
            planner=planner,
            org_scope=org_scope,
            current_user=current_user,
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
            assistant_message_id=assistant_message_id,
            state=state,
        ):
            if frame.startswith("event: done"):
                state["done_yielded"] = True
            yield frame
    finally:
        status = (
            MessageStatus.completed
            if state["done_yielded"]
            else MessageStatus.interrupted
        )
        run_status = (
            resolve_run_status(outcome)
            if outcome is not None
            else AgentRunStatus.failed
        )
        audit_events: tuple = ()
        if outcome is not None:
            audit_events = (
                partial(
                    audit_agent_run_completed,
                    actor_user_id=user_id,
                    run_id=outcome.run_id,
                    steps_used=outcome.steps_used,
                    capped=outcome.capped,
                    citation_count=len(state["citations"]),
                ),
            )
        await _finalize_agent_turn(
            db,
            thread=thread,
            user_id=user_id,
            user_message_id=user_message_id,
            user_content=message,
            assistant_message_id=assistant_message_id,
            assistant_content=state["content"],
            citations=state["citations"],
            status=status,
            common=common,
            retrieval_duration_ms=state["retrieval_duration_ms"],
            run_id=outcome.run_id if outcome is not None else None,
            run_status=run_status,
            audit_events=audit_events,
        )


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
    current_user: CurrentUser | None = None,
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
        current_user=current_user,
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
    planner: ToolPlanner | None = None,
    double_confirm: bool = False,
    assistant_message_id: UUID,
    state: dict[str, Any],
) -> AsyncIterator[str]:
    """文档操作模式 SSE 渲染（纯渲染 · 顺序硬约束）。

    顺序：tool_* → token → proposal_preview / clarify / refusal → done。
    - 提案成功 → proposal_preview（含 operation/kb_id/document_id/impact/conflict/run_id）；
      不建 pending（pending 由前端确认后 POST submit 创建 · 比 FAQ 多一轮确认）。
      B 路径（fast 模式自动识别）`double_confirm=True`，前端需两次点击确认。
    - 候选多篇（B 路径歧义 · 情景 5）→ clarify（含 operation/run_id/options），
      前端点选后 POST /agent/document-write/clarify 取回提案。
    - 越权 / 文档未命中 / 操作无法解析 → refusal（带 G5-1.3 reason 码文案）。
    不写库：本函数仅渲染事件并记录 state（落库由 stream_agent_document_write_events
    的 finally 统一收口，A2）。
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

    # 3) done（proposal_preview / clarify / refusal 均在 done 之前；落库由调用方 finally 收口）
    retrieval_duration_ms = sum(step.latency_ms for step in outcome.steps) or None
    state["content"] = token_text
    state["citations"] = []
    state["retrieval_duration_ms"] = retrieval_duration_ms
    yield _sse_event(
        "done",
        {
            "message_id": str(assistant_message_id),
            "citations": [],
            "agent_run_id": str(outcome.run_id),
        },
    )


async def stream_agent_document_write_events(
    db: AsyncSession,
    *,
    kb_id: UUID | None = None,
    user_id: UUID,
    message: str,
    thread_id: UUID,
    workspace: WorkspaceScope,
    tool_scope: AgentToolScope,
    planner: ToolPlanner,
    org_scope: OrgScope | None = None,
    current_user: CurrentUser | None = None,
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

    A2（DWC）：入口预提交 user + pending assistant（P1-08）；finally 经
    finalize_turn 单次 commit。``kb_id`` 仅库内调用方（kb_threads.py）传入，
    供 thread 解析；跨库 /ask 走 save_kwargs 工作区键解析。
    """
    # 文档操作无 chunk 引用；kb 归属由 save_kwargs/planner 决定；落库统一走 finalize_turn
    del workspace_mode, kb_id, save_turn
    thread, user_message_id, assistant_message_id, common = (
        await _precommit_for_save_kwargs(
            db,
            save_kwargs=save_kwargs,
            user_id=user_id,
            message=message,
            thread_id=thread_id,
        )
    )
    hooks = _BufferingToolHooks()
    state: dict[str, Any] = {
        "content": "",
        "citations": [],
        "retrieval_duration_ms": None,
        "done_yielded": False,
    }
    outcome: AgentRunOutcome | None = None
    try:
        outcome = await run_react_loop(
            db,
            user_id=user_id,
            thread_id=thread.id,
            query=message,
            workspace=workspace,
            tool_scope=tool_scope,
            planner=planner,
            org_scope=org_scope,
            current_user=current_user,
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
            assistant_message_id=assistant_message_id,
            state=state,
        ):
            if frame.startswith("event: done"):
                state["done_yielded"] = True
            yield frame
    finally:
        status = (
            MessageStatus.completed
            if state["done_yielded"]
            else MessageStatus.interrupted
        )
        run_status = (
            resolve_run_status(outcome)
            if outcome is not None
            else AgentRunStatus.failed
        )
        audit_events: tuple = ()
        if outcome is not None:
            audit_events = (
                partial(
                    audit_agent_run_completed,
                    actor_user_id=user_id,
                    run_id=outcome.run_id,
                    steps_used=outcome.steps_used,
                    capped=outcome.capped,
                    citation_count=0,
                ),
            )
        await _finalize_agent_turn(
            db,
            thread=thread,
            user_id=user_id,
            user_message_id=user_message_id,
            user_content=message,
            assistant_message_id=assistant_message_id,
            assistant_content=state["content"],
            citations=state["citations"],
            status=status,
            common=common,
            retrieval_duration_ms=state["retrieval_duration_ms"],
            run_id=outcome.run_id if outcome is not None else None,
            run_status=run_status,
            audit_events=audit_events,
        )
