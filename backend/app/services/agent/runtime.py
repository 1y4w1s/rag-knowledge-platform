"""G3-2.1/2.2 · Agent ReAct runtime — max 5 steps · budget · gate 前置循环。"""

from __future__ import annotations

import json
import time
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.retry import async_retry
from app.models.enums import AgentRunMode
from app.services.agent.finalize import finish_react_run
from app.services.agent.memory import (
    extract_and_store_memory,
    load_active_memories,
    format_memory_context,
)
from app.services.agent.planners import LLMPlanner
from app.services.audit.agent import (
    audit_agent_reflection,
    audit_agent_run_started,
    audit_agent_tool_denied,
    audit_agent_tool_executed,
)
from app.services.agent.runs import (
    DEFAULT_MAX_STEPS,
    create_agent_run,
    create_agent_step,
    finish_agent_step,
    update_agent_run_steps_used,
)
from app.services.agent.tools import (
    AgentToolName,
    ReadOnlyToolName,
    UnknownToolError,
    parse_agent_tool,
    run_compare_chunks,
    run_delete_document,
    run_generate_faq_draft,
    run_get_chunk_excerpt,
    run_grep_in_document,
    run_list_knowledge_bases,
    run_restore_document,
    run_search_documents,
    run_semantic_search,
)
from app.services.agent.tools.scope import FORBIDDEN_KB_SUMMARY, AgentToolScope
from app.services.agent.types import (
    AgentBudgetEvent,
    AgentRunOutcome,
    AgentStepRecord,
    ToolCallPlan,
    ToolResultEvent,
    ToolStartEvent,
)
from app.services.org.scope import OrgScope
from app.services.workspace.scope import WorkspaceScope

DEFAULT_RUN_TIMEOUT_SECONDS = 120


def _as_uuid_or_none(value: object) -> UUID | None:
    if value is None or value == "":
        return None
    return UUID(str(value))


def _as_uuid(value: object) -> UUID:
    return UUID(str(value))


class ToolPlanner(Protocol):
    async def next_tool_call(
        self,
        *,
        query: str,
        step_index: int,
        steps_used: int,
        max_steps: int,
        prior_steps: tuple[AgentStepRecord, ...],
    ) -> ToolCallPlan | None:
        """返回下一步 tool；None 表示 planner 主动结束 ReAct 循环。"""


class ToolRuntimeHooks(Protocol):
    async def on_tool_start(self, event: ToolStartEvent) -> None: ...

    async def on_tool_result(self, event: ToolResultEvent) -> None: ...

    async def on_agent_budget(self, event: AgentBudgetEvent) -> None: ...


class _NoopHooks:
    async def on_tool_start(self, event: ToolStartEvent) -> None:
        return None

    async def on_tool_result(self, event: ToolResultEvent) -> None:
        return None

    async def on_agent_budget(self, event: AgentBudgetEvent) -> None:
        return None


def build_args_summary(tool_name: str, args: dict[str, Any]) -> str:
    """tool_start SSE 用的人类可读 args 摘要。"""
    if tool_name == ReadOnlyToolName.semantic_search.value:
        query = str(args.get("query", "")).strip()
        return query[:120] if query else "语义检索"
    if tool_name == ReadOnlyToolName.search_documents.value:
        query = str(args.get("query", "")).strip()
        mode = args.get("mode", "filename")
        return f"{query[:80]} · {mode}" if query else f"文档搜索 · {mode}"
    if tool_name == ReadOnlyToolName.get_chunk_excerpt.value:
        chunk_id = args.get("chunk_id")
        return f"chunk {chunk_id}" if chunk_id else "读片段"
    if tool_name == ReadOnlyToolName.list_knowledge_bases.value:
        q = args.get("q")
        return f"列库 · {q}" if q else "列可见资料库"
    try:
        return json.dumps(args, ensure_ascii=False, default=str)[:120]
    except TypeError:
        return tool_name


async def _dispatch_tool(
    db: AsyncSession,
    *,
    workspace: WorkspaceScope,
    tool_scope: AgentToolScope,
    org_scope: OrgScope | None,
    tool_name: AgentToolName,
    args: dict[str, Any],
    run_id: UUID,
    thread_id: UUID,
    user_id: UUID,
) -> tuple[bool, str, Any]:
    if tool_name == ReadOnlyToolName.list_knowledge_bases:
        result = await run_list_knowledge_bases(
            db,
            workspace,
            org_scope=org_scope,
            q=args.get("q"),
            limit=args.get("limit"),
        )
    elif tool_name == ReadOnlyToolName.semantic_search:
        raw_kb_ids = args.get("kb_ids")
        kb_ids = (
            [UUID(str(item)) for item in raw_kb_ids]
            if raw_kb_ids
            else None
        )
        result = await run_semantic_search(
            db,
            workspace,
            tool_scope,
            query=str(args.get("query", "")),
            org_scope=org_scope,
            kb_ids=kb_ids,
            top_k=args.get("top_k"),
        )
    elif tool_name == ReadOnlyToolName.search_documents:
        result = await run_search_documents(
            db,
            workspace,
            query=str(args.get("query", "")),
            org_scope=org_scope,
            mode=args.get("mode"),
            limit=args.get("limit"),
        )
    elif tool_name == ReadOnlyToolName.get_chunk_excerpt:
        chunk_id = args.get("chunk_id")
        if chunk_id is None:
            return False, "缺少 chunk_id", None
        result = await run_get_chunk_excerpt(
            db,
            tool_scope,
            chunk_id=UUID(str(chunk_id)),
        )
    elif tool_name == ReadOnlyToolName.grep_in_document:
        doc_id = args.get("document_id")
        if doc_id is None:
            return False, "缺少 document_id", None
        result = await run_grep_in_document(
            db,
            tool_scope,
            document_id=UUID(str(doc_id)),
            pattern=str(args.get("pattern", "")),
            context_lines=args.get("context_lines"),
        )
    elif tool_name == ReadOnlyToolName.compare_chunks:
        result = await run_compare_chunks(
            db,
            tool_scope,
            chunk_ids=args.get("chunk_ids") or [],
        )
    elif tool_name == AgentToolName.generate_faq_draft:
        # G4-2.2：末步写·待审 tool（自身落 agent_approvals(pending)）。
        # 工具返回 GenerateFaqDraftToolResult，整体作为 data 透传，供 SSE 层取 ok/reason。
        result = await run_generate_faq_draft(
            db,
            tool_scope,
            kb_id=_as_uuid_or_none(args.get("kb_id")),
            filename=str(args.get("filename", "")),
            run_id=run_id,
            thread_id=thread_id,
            user_id=user_id,
            source_chunk_ids=[
                _as_uuid(c) for c in (args.get("source_chunk_ids") or [])
            ],
            title=args.get("title"),
        )
        return result.ok, result.summary, result
    elif tool_name == AgentToolName.delete_document:
        kb_id = _as_uuid_or_none(args.get("kb_id"))
        document_id = _as_uuid_or_none(args.get("document_id"))
        if kb_id is None or document_id is None:
            return False, "缺少 kb_id 或 document_id", None
        result = await run_delete_document(
            db,
            tool_scope,
            kb_id=kb_id,
            document_id=document_id,
            run_id=run_id,
            thread_id=thread_id,
            user_id=user_id,
            commit=bool(args.get("commit", False)),
        )
        return result.ok, result.summary, result
    elif tool_name == AgentToolName.restore_document:
        kb_id = _as_uuid_or_none(args.get("kb_id"))
        document_id = _as_uuid_or_none(args.get("document_id"))
        if kb_id is None or document_id is None:
            return False, "缺少 kb_id 或 document_id", None
        result = await run_restore_document(
            db,
            tool_scope,
            kb_id=kb_id,
            document_id=document_id,
            run_id=run_id,
            thread_id=thread_id,
            user_id=user_id,
            commit=bool(args.get("commit", False)),
        )
        return result.ok, result.summary, result
    elif tool_name == AgentToolName.web_search:
        from app.services.agent.tools.web_search import web_search as _ws
        result = await _ws(query=args.get("query", ""), num_results=args.get("num_results", 5))
        return result.ok, result.summary, result.data
    elif tool_name == AgentToolName.sql_query:
        from app.services.agent.tools.sql_query import sql_query as _sq
        result = await _sq(sql=args.get("sql", ""))
        return result.ok, result.summary, result.data
    else:
        return False, f"unknown or disallowed tool: {tool_name.value}", None

    return result.ok, result.summary, result.data


async def _execute_step(
    db: AsyncSession,
    *,
    workspace: WorkspaceScope,
    tool_scope: AgentToolScope,
    org_scope: OrgScope | None,
    tool_name: str,
    args: dict[str, Any],
    run_id: UUID,
    thread_id: UUID,
    user_id: UUID,
) -> tuple[bool, str, int, Any]:
    t0 = time.perf_counter()
    try:
        parsed = parse_agent_tool(tool_name)
    except UnknownToolError as exc:
        latency_ms = int((time.perf_counter() - t0) * 1000)
        return False, str(exc), latency_ms, None

    ok, summary, data = await async_retry(
        _dispatch_tool,
        db,
        workspace=workspace,
        tool_scope=tool_scope,
        org_scope=org_scope,
        tool_name=parsed,
        args=args,
        run_id=run_id,
        thread_id=thread_id,
        user_id=user_id,
        max_retries=settings.retry_max_attempts,
        base_delay=settings.retry_base_delay,
        breaker_name="agent_tool_dispatch",
    )
    latency_ms = int((time.perf_counter() - t0) * 1000)
    return ok, summary, latency_ms, data


# ═══════════════════════════════════════════════════════════════
# E2 迭代反思
# ═══════════════════════════════════════════════════════════════

async def _safe_audit(coro) -> None:
    """审计不阻塞主流程。"""
    try:
        await coro
    except Exception:
        pass


def _detect_reflection_signal(
    last_step: AgentStepRecord,
    query: str,
    reflection_count: int,
) -> str | None:
    """E2：检测反思信号，返回 'low_recall' / 'complex_query' / None。
    信号 B 在循环外检测。
    """
    from app.services.rag.confidence_reply import LOW_CONFIDENCE_SIM_CEILING

    # A：召回不足
    if last_step.tool_name in ("semantic_search", "search_documents"):
        output = last_step.data
        hits = output.hits if output else ()
        if not hits or all(h.score < LOW_CONFIDENCE_SIM_CEILING for h in hits):
            return "low_recall"

    # C：复合查询（仅首轮）
    if reflection_count == 0:
        from app.services.agent.planners import QueryDepth, query_depth
        if query_depth(query) == QueryDepth.complex:
            return "complex_query"

    return None


def _detect_low_confidence(records: list[AgentStepRecord]) -> bool:
    """E2 信号 B：遍历检索步骤，若所有 hit score 均低于阈值则标记低置信。"""
    from app.services.rag.confidence_reply import LOW_CONFIDENCE_SIM_CEILING

    all_scores: list[float] = []
    for step in records:
        if step.tool_name in ("semantic_search", "search_documents"):
            out = step.data
            if out and out.hits:
                all_scores.extend(h.score for h in out.hits)
    return bool(all_scores) and all(s < LOW_CONFIDENCE_SIM_CEILING for s in all_scores)


async def run_react_loop(
    db: AsyncSession,
    *,
    user_id: UUID,
    thread_id: UUID,
    query: str,
    workspace: WorkspaceScope,
    tool_scope: AgentToolScope,
    planner: ToolPlanner,
    org_scope: OrgScope | None = None,
    hooks: ToolRuntimeHooks | None = None,
    max_steps: int = DEFAULT_MAX_STEPS,
    timeout_seconds: float = DEFAULT_RUN_TIMEOUT_SECONDS,
    mode: AgentRunMode = AgentRunMode.thorough,
) -> AgentRunOutcome:
    """ReAct 只读 tool 循环 · 每步 agent_budget · 终态 capped/completed 落库。

    G4-2.2：可传入 mode=AgentRunMode.edit 以正确记录编辑 run。
    generate_faq_draft 末步经 _dispatch_tool 执行（自身落 agent_approvals）。
    """
    effective_hooks = hooks or _NoopHooks()
    run = await create_agent_run(
        db,
        thread_id=thread_id,
        user_id=user_id,
        max_steps=max_steps,
        mode=mode,
    )
    await audit_agent_run_started(
        db,
        actor_user_id=user_id,
        run_id=run.id,
        thread_id=thread_id,
        max_steps=max_steps,
    )

    records: list[AgentStepRecord] = []
    steps_used = 0
    capped = False
    timed_out = False
    deadline = time.monotonic() + timeout_seconds
    reflection_count = 0
    memory_ctx = ""
    external_calls = 0

    # E3：加载记忆注入 planner（仅 LLMPlanner 路径，受 ablation 开关控制）
    if isinstance(planner, LLMPlanner) and settings.agent_memory_enabled:
        memories = await load_active_memories(db, user_id)
        memory_ctx = format_memory_context(memories)
        if memory_ctx:
            planner._memory_context = memory_ctx

    while steps_used < max_steps:
        if time.monotonic() >= deadline:
            timed_out = True
            break

        step_index = steps_used + 1
        plan = await planner.next_tool_call(
            query=query,
            step_index=step_index,
            steps_used=steps_used,
            max_steps=max_steps,
            prior_steps=tuple(records),
        )
        if plan is None:
            break

        args_summary = build_args_summary(plan.tool_name, plan.args)
        await effective_hooks.on_tool_start(
            ToolStartEvent(step=step_index, tool=plan.tool_name, args_summary=args_summary)
        )

        db_step = await create_agent_step(
            db,
            run_id=run.id,
            user_id=user_id,
            step_index=step_index,
            tool_name=plan.tool_name,
            args_json=plan.args,
        )

        # E4：外部工具统一计数门禁（每轮 ≤AGENT_MAX_EXTERNAL_CALLS 次，覆盖 web_search + sql_query）
        _is_external = plan.tool_name in (AgentToolName.web_search.value, AgentToolName.sql_query.value)
        if _is_external and external_calls >= settings.agent_max_external_calls_per_conversation:
            logger.warning("外部工具已达上限（≤%d 次/轮），跳过 %s",
                           settings.agent_max_external_calls_per_conversation, plan.tool_name)
            ok, summary, latency_ms, data = False, "外部工具调用已达上限", 0, None
            db_step = None
            steps_used = step_index
            step_capped = steps_used >= max_steps
            if step_capped:
                capped = True
            await audit_agent_tool_denied(
                db,
                actor_user_id=user_id,
                run_id=run.id,
                tool=plan.tool_name,
                reason="external_tool_limit",
            )
            await update_agent_run_steps_used(
                db, run_id=run.id, user_id=user_id, steps_used=steps_used,
            )
            record = AgentStepRecord(step_index=step_index, tool_name=plan.tool_name, args=plan.args,
                                      ok=False, summary=summary, latency_ms=0, data=None)
            records.append(record)
            await effective_hooks.on_agent_budget(AgentBudgetEvent(steps_used=steps_used, max_steps=max_steps, capped=step_capped))
            if step_capped:
                break
            continue

        if _is_external:
            external_calls += 1

        ok, summary, latency_ms, data = await _execute_step(
            db,
            workspace=workspace,
            tool_scope=tool_scope,
            org_scope=org_scope,
            tool_name=plan.tool_name,
            args=plan.args,
            run_id=run.id,
            thread_id=thread_id,
            user_id=user_id,
        )

        steps_used = step_index
        step_capped = steps_used >= max_steps
        if step_capped:
            capped = True

        if db_step is not None:
            await finish_agent_step(
                db,
                step_id=db_step.id,
                user_id=user_id,
                ok=ok,
                result_summary=summary,
                latency_ms=latency_ms,
            )

        await audit_agent_tool_executed(
            db,
            actor_user_id=user_id,
            run_id=run.id,
            step=step_index,
            tool=plan.tool_name,
            ok=ok,
            latency_ms=latency_ms,
        )
        if not ok and summary == FORBIDDEN_KB_SUMMARY:
            await audit_agent_tool_denied(
                db,
                actor_user_id=user_id,
                run_id=run.id,
                tool=plan.tool_name,
            )

        await update_agent_run_steps_used(
            db,
            run_id=run.id,
            user_id=user_id,
            steps_used=steps_used,
        )

        record = AgentStepRecord(
            step_index=step_index,
            tool_name=plan.tool_name,
            args=plan.args,
            ok=ok,
            summary=summary,
            latency_ms=latency_ms,
            step_id=db_step.id if db_step is not None else None,
            data=data,
        )
        records.append(record)

        # ── E2 迭代反思（仅 LLMPlanner 路径）──
        if isinstance(planner, LLMPlanner) and reflection_count < settings.agent_max_reflections:
            signal = _detect_reflection_signal(record, query, reflection_count)
            if signal == "low_recall" and ok:
                from app.services.rag.generation import rewrite_query
                new_query = await rewrite_query(query)
                if new_query:
                    planner._cached_plan = None  # 清缓存强制重规划
                    planner._query = new_query
                    query = new_query
                    reflection_count += 1
                    await _safe_audit(audit_agent_reflection(
                        db, actor_user_id=user_id, run_id=run.id,
                        signal="low_recall", new_query=new_query,
                    ))
                    continue  # 重新规划
            elif signal == "complex_query":
                from app.services.rag.generation import decompose_query
                sub_queries = await decompose_query(query)
                if sub_queries and len(sub_queries) >= 2:
                    from app.services.agent.planners import LLMPlannerFactory
                    all_hits = []
                    for sq in sub_queries[:3]:
                        sub = LLMPlannerFactory.create(sq, default_kb_id=getattr(planner, "default_kb_id", None), memory_context=memory_ctx or "")
                        p = await sub.next_tool_call(query=sq, step_index=1, steps_used=0,
                                                      max_steps=max_steps, prior_steps=())
                        if p and p.tool_name in ("semantic_search", "search_documents"):
                            _ok2, _s2, _l2, _d2 = await _execute_step(
                                db, workspace=workspace, tool_scope=tool_scope,
                                org_scope=org_scope, tool_name=p.tool_name, args=p.args,
                                run_id=run.id, thread_id=thread_id, user_id=user_id,
                            )
                            if _ok2 and _d2:
                                all_hits.append(_d2)
                    reflection_count += 1
                    await _safe_audit(audit_agent_reflection(
                        db, actor_user_id=user_id, run_id=run.id,
                        signal="complex_query",
                    ))

        # E3：从检索步骤提取隐式偏好
        await _safe_audit(extract_and_store_memory(
            db, user_id, query,
            kb_id=getattr(planner, "default_kb_id", None),
            tool_name=plan.tool_name, tool_data=data,
        ))

        await effective_hooks.on_tool_result(
            ToolResultEvent(
                step=step_index,
                tool=plan.tool_name,
                ok=ok,
                summary=summary,
                latency_ms=latency_ms,
                capped=step_capped,
            )
        )
        await effective_hooks.on_agent_budget(
            AgentBudgetEvent(
                steps_used=steps_used,
                max_steps=max_steps,
                capped=step_capped,
            )
        )

        if step_capped:
            break

    outcome = AgentRunOutcome(
        run_id=run.id,
        steps_used=steps_used,
        max_steps=max_steps,
        capped=capped,
        timed_out=timed_out,
        steps=tuple(records),
        # E2 信号 B：低置信度标记（循环外，outcome 构造时判定）
        low_confidence=_detect_low_confidence(records),
    )
    await finish_react_run(
        db,
        run_id=run.id,
        user_id=user_id,
        outcome=outcome,
    )
    return outcome
