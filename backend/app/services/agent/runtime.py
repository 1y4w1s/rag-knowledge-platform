"""G3-2.1/2.2 · Agent ReAct runtime — max 5 steps · budget · gate 前置循环。"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import replace
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import CurrentUser
from app.core.retry import async_retry
from app.models.agent_run import AgentRun
from app.models.agent_step import AgentStep
from app.models.enums import AgentRunMode, AgentRunStatus, AgentStepStatus
from app.services.agent.finalize import finish_react_run
from app.services.agent.memory import (
    extract_and_store_memory,
    load_active_memories,
    format_memory_context,
)
from app.services.agent.planners import LLMPlanner, NextActionPlanner
from app.services.agent.state import init_agent_state, reduce_observation
from app.services.audit.agent import (
    audit_agent_reflection,
    audit_agent_run_started,
    audit_agent_tool_denied,
    audit_agent_tool_executed,
    audit_agent_tool_replanned,
)
from app.services.agent.runs import (
    DEFAULT_MAX_STEPS,
    create_agent_run,
    create_agent_step,
    finish_agent_run,
    finish_agent_step,
    update_agent_run_steps_used,
)
from app.services.agent.tools import (
    AgentToolName,
    ReadOnlyToolName,
    SemanticSearchOutput,
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
from app.services.agent.tools.guard import (
    AGENT_TOOL_BREAKER_TOOL_NAMES,
    EXTERNAL_TOOL_NAMES,
    allow_tool_window,
    ensure_agent_tool_breakers,
    resolve_tool_run_limit,
    tool_breaker_name,
)
from app.services.agent.tools.scope import FORBIDDEN_KB_SUMMARY, AgentToolScope
from app.services.agent.tool_fallback import (
    ToolFallbackPlan,
    classify_tool_failure,
    find_equivalent_tool,
    materialize_fallback_step,
    should_replan,
)
from app.services.agent.types import (
    AgentActionKind,
    AgentBudgetEvent,
    AgentDecision,
    AgentRunOutcome,
    AgentStepRecord,
    StepExecution,
    ToolCallPlan,
    ToolFailure,
    ToolFailureKind,
    ToolResultEvent,
    ToolStartEvent,
)
from app.services.org.scope import OrgScope
from app.services.observability.metrics_registry import (
    inc_agent_tool_call,
    record_agent_tool_latency,
)
from app.services.workspace.scope import WorkspaceScope

DEFAULT_RUN_TIMEOUT_SECONDS = 120
_TOOL_EXECUTION_FAILED_SUMMARY = "工具执行失败，已尝试自动恢复"
MAX_FROZEN_TOOL_SKIPS = 3

logger = logging.getLogger(__name__)


def _as_uuid_or_none(value: object) -> UUID | None:
    if value is None or value == "":
        return None
    return UUID(str(value))


def _as_uuid(value: object) -> UUID:
    return UUID(str(value))


def _json_safe_args(value: Any) -> Any:
    """AgentStep.args_json 为 JSONB：替换计划中的 UUID 需转为字符串。"""
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, list):
        return [_json_safe_args(item) for item in value]
    if isinstance(value, dict):
        return {key: _json_safe_args(item) for key, item in value.items()}
    return value


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
    current_user: CurrentUser | None,
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
        raw_kb_ids = args.get("kb_ids")
        kb_ids = (
            [UUID(str(item)) for item in raw_kb_ids]
            if raw_kb_ids
            else None
        )
        result = await run_search_documents(
            db,
            workspace,
            query=str(args.get("query", "")),
            org_scope=org_scope,
            tool_scope=tool_scope,
            mode=args.get("mode"),
            limit=args.get("limit"),
            kb_ids=kb_ids,
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
        if current_user is None:
            # L10 fail-closed：无用户上下文时拒绝写 tool（不建审批）。
            return False, FORBIDDEN_KB_SUMMARY, None
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
            current_user=current_user,
            commit=bool(args.get("commit", False)),
        )
        return result.ok, result.summary, result
    elif tool_name == AgentToolName.restore_document:
        if current_user is None:
            # L10 fail-closed：无用户上下文时拒绝写 tool（不建审批）。
            return False, FORBIDDEN_KB_SUMMARY, None
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
            current_user=current_user,
            commit=bool(args.get("commit", False)),
        )
        return result.ok, result.summary, result
    elif tool_name == AgentToolName.web_search:
        # P2-A3 防御纵深：总开关除 planner 提示词层过滤外，runtime 分发层再拦一道。
        if not settings.external_tools_enabled:
            return False, "web_search 已关闭（EXTERNAL_TOOLS_ENABLED=false）", None
        from app.services.agent.tools.web_search import web_search as _ws
        result = await _ws(query=args.get("query", ""), num_results=args.get("num_results", 5))
        return result.ok, result.summary, result.data
    elif tool_name == AgentToolName.sql_query:
        # H2 权限收口：sql_query 已下线（P0-02/03），任何调用一律拒绝。
        # summary == FORBIDDEN_KB_SUMMARY 触发 runtime 自动写 agent.tool_denied 审计。
        return False, FORBIDDEN_KB_SUMMARY, None
    else:
        return False, f"unknown or disallowed tool: {tool_name.value}", None

    return result.ok, result.summary, result.data


def _record_tool_metric(tool_name: str, execution: StepExecution) -> None:
    """_execute_step 全路径统一计数与延迟指标。"""
    if execution.failure is not None and execution.failure.breaker_open:
        status = "breaker_open"
    elif execution.ok:
        status = "ok"
    else:
        status = "failed"
    inc_agent_tool_call(
        tool_name,
        status,
        external=tool_name in EXTERNAL_TOOL_NAMES,
    )
    record_agent_tool_latency(tool_name, float(execution.latency_ms))


async def _execute_step(
    db: AsyncSession,
    *,
    workspace: WorkspaceScope,
    tool_scope: AgentToolScope,
    org_scope: OrgScope | None,
    current_user: CurrentUser | None,
    tool_name: str,
    args: dict[str, Any],
    run_id: UUID,
    thread_id: UUID,
    user_id: UUID,
) -> StepExecution:
    t0 = time.perf_counter()
    try:
        parsed = parse_agent_tool(tool_name)
    except UnknownToolError as exc:
        latency_ms = int((time.perf_counter() - t0) * 1000)
        failure = classify_tool_failure(
            tool_name=tool_name,
            ok=False,
            summary=str(exc),
            data=None,
        )
        execution = StepExecution(
            ok=False,
            summary=str(exc),
            latency_ms=latency_ms,
            data=None,
            failure=failure,
        )
        _record_tool_metric(tool_name, execution)
        return execution

    breaker_name = (
        tool_breaker_name(parsed.value)
        if parsed.value in AGENT_TOOL_BREAKER_TOOL_NAMES
        else None
    )
    try:
        ok, summary, data = await async_retry(
            _dispatch_tool,
            db,
            workspace=workspace,
            tool_scope=tool_scope,
            org_scope=org_scope,
            current_user=current_user,
            tool_name=parsed,
            args=args,
            run_id=run_id,
            thread_id=thread_id,
            user_id=user_id,
            max_retries=settings.retry_max_attempts,
            base_delay=settings.retry_base_delay,
            breaker_name=breaker_name,
        )
    except Exception as exc:
        latency_ms = int((time.perf_counter() - t0) * 1000)
        failure = classify_tool_failure(
            tool_name=tool_name,
            ok=False,
            summary=_TOOL_EXECUTION_FAILED_SUMMARY,
            data=None,
            exception=exc,
        )
        logger.warning(
            "tool infra failure: tool=%s error=%s",
            tool_name,
            exc,
        )
        execution = StepExecution(
            ok=False,
            summary=_TOOL_EXECUTION_FAILED_SUMMARY,
            latency_ms=latency_ms,
            data=None,
            failure=failure,
        )
        _record_tool_metric(tool_name, execution)
        return execution
    latency_ms = int((time.perf_counter() - t0) * 1000)
    failure = classify_tool_failure(
        tool_name=tool_name,
        ok=ok,
        summary=summary,
        data=data,
    )
    execution = StepExecution(
        ok=ok,
        summary=summary,
        latency_ms=latency_ms,
        data=data,
        failure=failure,
    )
    _record_tool_metric(tool_name, execution)
    return execution


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
    # search_documents 返回 SearchDocumentsOutput（无 score），不做 low_recall 判定
    if last_step.tool_name == "semantic_search":
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
        if step.tool_name == "semantic_search":
            out = step.data
            if out and out.hits:
                all_scores.extend(h.score for h in out.hits)
    return bool(all_scores) and all(s < LOW_CONFIDENCE_SIM_CEILING for s in all_scores)


# ═══════════════════════════════════════════════════════════════
# M1-W2 候选① 漂移守卫（分解-检索联动闭环；默认关）
# ═══════════════════════════════════════════════════════════════


class _DriftHitChunk:
    """只读适配：SemanticSearchHit → relevance 词面重叠判定所需的片段形状（T3 复用只读逻辑）。"""

    __slots__ = (
        "doc_name",
        "section_title",
        "heading_path",
        "parent_content",
        "content",
        "similarity",
    )

    def __init__(self, hit: Any) -> None:
        self.doc_name = hit.doc_name
        self.section_title = hit.section_title
        self.heading_path = None
        self.parent_content = None
        self.content = hit.excerpt or ""
        self.similarity = float(hit.score or 0.0)


def _sub_query_drift_signal(original_query: str, hits: Any) -> str | None:
    """只读漂移判定（§10.4 修正：T3 词面重叠 + T2 sim 只读为主判据，T1 保留基频观测）。

    任一信号命中即判定该子查询漂移：
    - T1：检索 0 命中（最干净的漂移信号，同时是候选③ drift_search 基频观测对象）；
    - T2：top1 sim < relevance_low_sim_ceiling（0.5，只读配置不改值；只触发收敛、不触发拒答）；
    - T3：命中片段与原始 query 无词面重叠（复用 relevance.query_overlaps_chunk 只读逻辑——
      黄金/关键实体被丢在排名边缘的 ENT-097 型漂移即表现为「无词面重叠」）。
    """
    if not hits:
        return "T1"
    if float(hits[0].score or 0.0) < settings.relevance_low_sim_ceiling:
        return "T2"
    from app.services.rag.relevance import query_overlaps_chunk

    if any(query_overlaps_chunk(original_query, _DriftHitChunk(h)) for h in hits):
        return None
    return "T3"


async def _run_recovery_search(
    db: AsyncSession,
    *,
    workspace: WorkspaceScope,
    tool_scope: AgentToolScope,
    org_scope: OrgScope | None,
    current_user: CurrentUser | None,
    run_id: UUID,
    thread_id: UUID,
    user_id: UUID,
    query: str,
    args: dict[str, Any],
    step_index: int,
) -> tuple[StepExecution | None, AgentStepRecord | None]:
    """漂移守卫的收敛/直检搜索执行：复用 _execute_step + step 落库/审计路径。

    返回 (execution, record)；任何异常均以 (None, None) 安全回退，不阻断剩余子查询
    与 S3 终点判据（§2.6 异常回退）。
    """
    tool_name = "semantic_search"
    try:
        db_step = await create_agent_step(
            db,
            run_id=run_id,
            user_id=user_id,
            step_index=step_index,
            tool_name=tool_name,
            args_json=args,
        )
        execution = await _execute_step(
            db,
            workspace=workspace,
            tool_scope=tool_scope,
            org_scope=org_scope,
            current_user=current_user,
            tool_name=tool_name,
            args=args,
            run_id=run_id,
            thread_id=thread_id,
            user_id=user_id,
        )
        if db_step is not None:
            await finish_agent_step(
                db,
                step_id=db_step.id,
                user_id=user_id,
                ok=execution.ok,
                result_summary=execution.summary,
                latency_ms=execution.latency_ms,
            )
        await audit_agent_tool_executed(
            db,
            actor_user_id=user_id,
            run_id=run_id,
            step=step_index,
            tool=tool_name,
            ok=execution.ok,
            latency_ms=execution.latency_ms,
        )
        return execution, AgentStepRecord(
            step_index=step_index,
            tool_name=tool_name,
            args=args,
            ok=execution.ok,
            summary=execution.summary,
            latency_ms=execution.latency_ms,
            step_id=db_step.id if db_step is not None else None,
            data=execution.data,
        )
    except Exception:
        logger.warning("漂移守卫恢复搜索失败，跳过（不影响终点判据）", exc_info=True)
        return None, None


async def execute_critic_directed_retrieval(
    db: AsyncSession,
    *,
    decision: AgentDecision,
    workspace: WorkspaceScope,
    tool_scope: AgentToolScope,
    org_scope: OrgScope | None = None,
) -> SemanticSearchOutput | None:
    """L3-W7：执行 Critic 定向 semantic_search（生成后回流；不重开已终态 run）。

    仅接受 reason_code=critic_directed_retrieve 的 tool Decision；失败/空命中返回 None。
    """
    if (
        decision.action != AgentActionKind.tool
        or decision.tool_name != "semantic_search"
        or decision.reason_code != "critic_directed_retrieve"
    ):
        return None
    query = str(decision.args.get("query", "")).strip()
    if not query:
        return None
    raw_kb_ids = decision.args.get("kb_ids")
    kb_ids = (
        [UUID(str(item)) for item in raw_kb_ids] if raw_kb_ids else None
    )
    try:
        result = await run_semantic_search(
            db,
            workspace,
            tool_scope,
            query=query,
            org_scope=org_scope,
            kb_ids=kb_ids,
            top_k=decision.args.get("top_k"),
        )
    except Exception:
        logger.warning("critic directed retrieval failed", exc_info=True)
        return None
    if not result.ok or result.data is None:
        return None
    if not isinstance(result.data, SemanticSearchOutput) or not result.data.hits:
        return None
    return result.data


async def guard_sub_query_drift(
    db: AsyncSession,
    *,
    sub_query: str,
    original_query: str,
    sub_args: dict[str, Any],
    sub_execution: StepExecution,
    steps_used: int,
    max_steps: int,
    workspace: WorkspaceScope,
    tool_scope: AgentToolScope,
    org_scope: OrgScope | None,
    current_user: CurrentUser | None,
    run_id: UUID,
    thread_id: UUID,
    user_id: UUID,
    chain_state: dict[str, Any] | None = None,
) -> tuple[list[AgentStepRecord], int]:
    """子查询漂移守卫（M1-W2 候选①）：只读判定（T1/T2/T3）→ S1 收敛改写 / S2 整题直检回退。

    调用时机：E2 complex_query 分解的子查询检索执行后（默认关，关闭时零激活）。
    仅对 semantic_search 子查询结果产生判定（search_documents 无 sim/top 信号）。

    S1（收敛改写）：每漂移子查询至多 rewrite 次（agent_decompose_drift_max_rewrites=1，
    防 LLM 非确定性放大）；改写重检收敛则替换原始漂移记录；仍漂移则该改写结果丢弃。
    S2（整题直检回退）：原 query 语义直检（RRF = 向量 + FTS 关键词混合，§10.4 修正②），
    每分解链至多 1 次 + 预算守卫（steps_used + 1 < max_steps）。

    返回 (恢复记录列表, 新 steps_used)：
    - 列表为空 → 无漂移 / 默认关 / 无可用恢复路径，调用方保持原子查询记录原样；
    - 列表非空 → 原子查询判定漂移，调用方以恢复记录替换原记录（§2.5「hits 不并入」）。

    步数账本（W2 实施澄清，回填 §2.5）：S1/S2 恢复搜索均为真实执行步，各 +1 步
    （与 §2.5 成本表「1 步」一致）；开启但预算不足（A0=3 常见）时零触发，走 S3 终点判据。
    """
    if not settings.agent_decompose_drift_recovery:
        return [], steps_used

    if not getattr(sub_execution, "ok", False) or sub_execution.data is None:
        return [], steps_used
    hits = getattr(sub_execution.data, "hits", None)
    if hits is None:
        return [], steps_used
    if _sub_query_drift_signal(original_query, hits) is None:
        return [], steps_used

    chain_state = chain_state or {}

    # ── S1 收敛改写（改写本身是 LLM 调用，不占 agent 步；重检是新执行步）──
    from app.services.rag.generation import rewrite_query

    rewrite_budget = max(0, int(settings.agent_decompose_drift_max_rewrites))
    attempted = 0
    while attempted < rewrite_budget and steps_used + 1 < max_steps:
        attempted += 1
        new_query = await rewrite_query(sub_query)
        if not new_query or new_query.strip() == sub_query.strip():
            break
        execution, record = await _run_recovery_search(
            db,
            workspace=workspace,
            tool_scope=tool_scope,
            org_scope=org_scope,
            current_user=current_user,
            run_id=run_id,
            thread_id=thread_id,
            user_id=user_id,
            query=new_query,
            args={**sub_args, "query": new_query},
            step_index=steps_used + 1,
        )
        if execution is None or record is None:
            break
        new_hits = getattr(execution.data, "hits", None) if execution.data else None
        if new_hits and _sub_query_drift_signal(original_query, new_hits) is None:
            await _safe_audit(audit_agent_reflection(
                db, actor_user_id=user_id, run_id=run_id,
                signal="drift_recovery", new_query=new_query,
            ))
            return [record], steps_used + 1
        # 改写后仍漂移 → 该改写结果丢弃（hits 不并入），转入 S2 整题直检

    # ── S2 整题直检回退（每分解链至多 1 次 + 预算守卫 steps_used + 1 < max_steps）──
    if chain_state.get("s2_used"):
        return [], steps_used
    if steps_used + 1 >= max_steps:
        return [], steps_used
    chain_state["s2_used"] = True
    execution, record = await _run_recovery_search(
        db,
        workspace=workspace,
        tool_scope=tool_scope,
        org_scope=org_scope,
        current_user=current_user,
        run_id=run_id,
        thread_id=thread_id,
        user_id=user_id,
        query=original_query,
        args={**sub_args, "query": original_query},
        step_index=steps_used + 1,
    )
    if execution is None or record is None:
        return [], steps_used
    await _safe_audit(audit_agent_reflection(
        db, actor_user_id=user_id, run_id=run_id,
        signal="drift_recovery", new_query=original_query,
    ))
    return [record], steps_used + 1


async def guard_evidence_insufficiency(
    db: AsyncSession,
    *,
    sub_query: str,
    original_query: str,
    sub_args: dict[str, Any],
    sub_execution: StepExecution,
    steps_used: int,
    max_steps: int,
    workspace: WorkspaceScope,
    tool_scope: AgentToolScope,
    org_scope: OrgScope | None,
    current_user: CurrentUser | None,
    run_id: UUID,
    thread_id: UUID,
    user_id: UUID,
    chain_state: dict[str, Any] | None = None,
) -> tuple[list[AgentStepRecord], int]:
    """M2 W2 · 证据不足自适应重检（S1 收敛改写 / S2 整题直检回退）。

    触发判据：check_evidence_sufficiency 判定该子查询证据不足（漂移守卫未命中时——
    漂移守卫优先，命中即由漂移路径恢复，本策略只补「有命中但数量/多样性不足」的空档）。

    复用 M1 drift guard 的 S1/S2 恢复执行器 _run_recovery_search 与 rewrite_query，
    不重造轮子；同样受 A0 预算守卫与每链 S2 至多 1 次约束。

    W4 方案 C（预算修正）：S1 以 steps_used < max_steps 守卫——恢复步计入总步、
    由调用方循环统一结算，故 steps_used = max_steps - 1 时 S1 单步可达且不越界
    （返回步数 = steps_used + 1 ≤ max_steps）；S2 仍须 steps_used + 1 < max_steps
    （每链至多 1 次，守住「直检不越过最后一步」）。

    返回 (恢复记录列表, 新 steps_used)：
    - 空列表 → 证据充分 / 策略默认关 / 无可用恢复路径，调用方保持原子查询记录原样；
    - 非空列表 → 证据不足触发重检，调用方以恢复记录替换原记录（hits 不并入）。
    """
    if not settings.agent_evidence_strategy_enabled:
        return [], steps_used

    if not getattr(sub_execution, "ok", False) or sub_execution.data is None:
        return [], steps_used
    hits = getattr(sub_execution.data, "hits", None)
    if hits is None:
        return [], steps_used

    from app.services.rag.evidence import check_evidence_sufficiency

    verdict = check_evidence_sufficiency(hits, sub_query)
    if verdict.sufficient:
        return [], steps_used

    chain_state = chain_state or {}
    await _safe_audit(audit_agent_reflection(
        db, actor_user_id=user_id, run_id=run_id,
        signal="evidence_recovery",
        new_query=f"verdict={verdict.reason} triggered=True",
    ))

    # ── S1 收敛改写（改写本身是 LLM 调用，不占 agent 步；重检是新执行步）──
    # W4 方案 C：守卫放宽为 steps_used < max_steps —— 恢复步计入总步、由调用方循环
    # 统一结算（steps_used 事后 >= max_steps 即 capped），steps_used = max_steps - 1
    # 时 S1 单步可达且返回 steps_used + 1 ≤ max_steps 不越界。
    from app.services.rag.generation import rewrite_query

    rewrite_budget = max(0, int(settings.agent_decompose_drift_max_rewrites))
    attempted = 0
    while attempted < rewrite_budget and steps_used < max_steps:
        attempted += 1
        new_query = await rewrite_query(sub_query)
        if not new_query or new_query.strip() == sub_query.strip():
            break
        execution, record = await _run_recovery_search(
            db,
            workspace=workspace,
            tool_scope=tool_scope,
            org_scope=org_scope,
            current_user=current_user,
            run_id=run_id,
            thread_id=thread_id,
            user_id=user_id,
            query=new_query,
            args={**sub_args, "query": new_query},
            step_index=steps_used + 1,
        )
        if execution is None or record is None:
            break
        new_hits = getattr(execution.data, "hits", None) if execution.data else None
        if new_hits:
            new_verdict = check_evidence_sufficiency(new_hits, sub_query)
            if new_verdict.sufficient:
                await _safe_audit(audit_agent_reflection(
                    db, actor_user_id=user_id, run_id=run_id,
                    signal="evidence_recovery",
                    new_query=f"rewrite={new_query} sufficient=True",
                ))
                return [record], steps_used + 1
        # 改写后证据仍不足 → 该改写结果丢弃（hits 不并入），转入 S2 整题直检

    # ── S2 整题直检回退（每分解链至多 1 次 + 预算守卫 steps_used + 1 < max_steps）──
    if chain_state.get("evidence_s2_used"):
        return [], steps_used
    if steps_used + 1 >= max_steps:
        return [], steps_used
    chain_state["evidence_s2_used"] = True
    execution, record = await _run_recovery_search(
        db,
        workspace=workspace,
        tool_scope=tool_scope,
        org_scope=org_scope,
        current_user=current_user,
        run_id=run_id,
        thread_id=thread_id,
        user_id=user_id,
        query=original_query,
        args={**sub_args, "query": original_query},
        step_index=steps_used + 1,
    )
    if execution is None or record is None:
        return [], steps_used
    await _safe_audit(audit_agent_reflection(
        db, actor_user_id=user_id, run_id=run_id,
        signal="evidence_recovery",
        new_query=f"direct={original_query}",
    ))
    return [record], steps_used + 1


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
    current_user: CurrentUser | None = None,
    hooks: ToolRuntimeHooks | None = None,
    max_steps: int = DEFAULT_MAX_STEPS,
    timeout_seconds: float = DEFAULT_RUN_TIMEOUT_SECONDS,
    mode: AgentRunMode = AgentRunMode.thorough,
) -> AgentRunOutcome:
    """ReAct 只读 tool 循环 · 每步 agent_budget · 终态 capped/completed 落库。

    G4-2.2：可传入 mode=AgentRunMode.edit 以正确记录编辑 run。
    generate_faq_draft 末步经 _dispatch_tool 执行（自身落 agent_approvals）。

    B1-2：循环主体包 try/except 兜底——异常/取消时未收尾 steps 置 error、
    run 收敛 failed/capped 并落库（P1-02）；正常路径终态由 finish_react_run
    条件更新幂等落库。
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

    try:
        outcome = await _run_react_loop_until_outcome(
            db,
            user_id=user_id,
            thread_id=thread_id,
            query=query,
            workspace=workspace,
            tool_scope=tool_scope,
            planner=planner,
            org_scope=org_scope,
            current_user=current_user,
            effective_hooks=effective_hooks,
            run=run,
            max_steps=max_steps,
            timeout_seconds=timeout_seconds,
        )
    except BaseException:
        # 异常/取消兜底：未收尾 steps 置 error + run 收敛 failed/capped + 落库
        try:
            await _converge_failed_run(
                db,
                run_id=run.id,
                user_id=user_id,
                max_steps=max_steps,
            )
        except Exception:
            logger.exception("run_react_loop 异常兜底落库失败: run=%s", run.id)
        raise

    await finish_react_run(
        db,
        run_id=run.id,
        user_id=user_id,
        outcome=outcome,
    )
    return outcome


async def _converge_failed_run(
    db: AsyncSession,
    *,
    run_id: UUID,
    user_id: UUID,
    max_steps: int,
) -> None:
    """B1-2 异常兜底：未收尾 steps 置 error + run 收敛终态并落库。

    幂等：finish_agent_run 条件更新保证仅 running 可写终态，重复收敛不覆盖
    （P1-02 / P0-01）；run 非 owner 或已终态则直接返回。
    """
    run = await db.get(AgentRun, run_id)
    if run is None or run.user_id != user_id or run.status != AgentRunStatus.running:
        return
    await db.execute(
        update(AgentStep)
        .where(
            AgentStep.run_id == run_id,
            AgentStep.status == AgentStepStatus.running,
        )
        .values(status=AgentStepStatus.error)
    )
    status = (
        AgentRunStatus.capped
        if run.steps_used >= max_steps
        else AgentRunStatus.failed
    )
    await finish_agent_run(db, run_id=run_id, user_id=user_id, status=status)
    await db.commit()


async def _run_l3_next_action_loop(
    db: AsyncSession,
    *,
    user_id: UUID,
    thread_id: UUID,
    query: str,
    workspace: WorkspaceScope,
    tool_scope: AgentToolScope,
    planner: NextActionPlanner,
    org_scope: OrgScope | None,
    current_user: CurrentUser | None,
    effective_hooks: ToolRuntimeHooks,
    run: AgentRun,
    max_steps: int,
    timeout_seconds: float,
) -> AgentRunOutcome:
    """L3-W3：Observation-driven 最小 loop（成功后也 re-decide）。

    显式 finish / clarify / refuse 收口；禁止用 None 猜语义。
    复用 `_execute_step` / step 落库 / audit / budget hooks；
    不做 E2 分解、不做 legacy fallback queue（失败进 Observation 后再 decide）。
    """
    memory_ctx = ""
    if settings.agent_memory_enabled:
        memories = await load_active_memories(db, user_id)
        memory_ctx = format_memory_context(memories)
        planner._memory_context = memory_ctx

    # L4：FactDecomposer → init（默认关 → 空 ledger，与接线前一致）
    from app.services.agent.decomposer import maybe_fact_goals_for_init

    fact_goals = await maybe_fact_goals_for_init(query)
    state = init_agent_state(
        original_query=query,
        max_steps=max_steps,
        memory_context=memory_ctx,
        fact_goals=fact_goals,
    )
    records: list[AgentStepRecord] = []
    capped = False
    timed_out = False
    deadline = time.monotonic() + timeout_seconds
    tool_run_counts: dict[str, int] = {}
    search_successes = 0
    terminal_decision: AgentDecision | None = None

    ensure_agent_tool_breakers()

    while state.steps_used < max_steps:
        if time.monotonic() >= deadline:
            timed_out = True
            break

        # L4-W6b：Recovery 薄钩子（默认关 → None，与接线前逐字一致）
        from app.services.agent.reflection_recovery import maybe_l3_recovery_decision

        recovery_decision = maybe_l3_recovery_decision(state)
        if recovery_decision is not None:
            decision = planner._maybe_inject_kb(recovery_decision)
            state = replace(state, reflection_count=state.reflection_count + 1)
        else:
            decision = await planner.decide_next(state)

        # L4-W5.5a：StopPolicy 薄钩子（默认关 → 原样 decision）
        from app.services.agent.stop_policy import apply_stop_policy_decision

        decision = apply_stop_policy_decision(state, decision)

        if settings.agent_l3_trajectory_trace_enabled:
            logger.info(
                "module=agent_l3 operation=trajectory_trace "
                "action=%s tool=%s reason_code=%s steps_used=%s",
                decision.action,
                decision.tool_name or "",
                decision.reason_code or "",
                state.steps_used,
            )

        if decision.action == AgentActionKind.finish:
            terminal_decision = decision
            break
        if decision.action == AgentActionKind.clarify:
            terminal_decision = decision
            break
        if decision.action == AgentActionKind.refuse:
            terminal_decision = decision
            break
        if decision.action != AgentActionKind.tool or not decision.tool_name:
            terminal_decision = AgentDecision(
                action=AgentActionKind.refuse,
                reason_code="invalid_tool_decision",
            )
            break

        step_index = state.steps_used + 1
        plan_args = _json_safe_args(decision.args)
        args_summary = build_args_summary(decision.tool_name, plan_args)
        await effective_hooks.on_tool_start(
            ToolStartEvent(
                step=step_index,
                tool=decision.tool_name,
                args_summary=args_summary,
            )
        )

        db_step = await create_agent_step(
            db,
            run_id=run.id,
            user_id=user_id,
            step_index=step_index,
            tool_name=decision.tool_name,
            args_json=plan_args,
        )

        _is_external = decision.tool_name in EXTERNAL_TOOL_NAMES
        run_limit = resolve_tool_run_limit(decision.tool_name)
        limited_summary: str | None = None
        limited_reason: str | None = None

        if (
            run_limit is not None
            and tool_run_counts.get(decision.tool_name, 0) >= run_limit
        ):
            limited_summary = "工具调用已达本轮上限"
            limited_reason = "tool_run_limit"
        elif _is_external and settings.external_tools_enabled:
            if not await allow_tool_window(decision.tool_name):
                limited_summary = "工具已达全局窗口限流上限"
                limited_reason = "tool_window_limit"

        if limited_summary is None:
            tool_run_counts[decision.tool_name] = (
                tool_run_counts.get(decision.tool_name, 0) + 1
            )
            execution = await _execute_step(
                db,
                workspace=workspace,
                tool_scope=tool_scope,
                org_scope=org_scope,
                current_user=current_user,
                tool_name=decision.tool_name,
                args=plan_args,
                run_id=run.id,
                thread_id=thread_id,
                user_id=user_id,
            )
        else:
            inc_agent_tool_call(
                decision.tool_name, "limited", external=_is_external
            )
            execution = StepExecution(
                ok=False,
                summary=limited_summary,
                latency_ms=0,
                data=None,
                failure=ToolFailure(
                    kind=ToolFailureKind.disabled,
                    tool_name=decision.tool_name,
                    summary=limited_summary,
                ),
            )
            db_step = None
            await audit_agent_tool_denied(
                db,
                actor_user_id=user_id,
                run_id=run.id,
                tool=decision.tool_name,
                reason=limited_reason,
            )

        if db_step is not None:
            await finish_agent_step(
                db,
                step_id=db_step.id,
                user_id=user_id,
                ok=execution.ok,
                result_summary=execution.summary,
                latency_ms=execution.latency_ms,
            )

        if limited_summary is None:
            await audit_agent_tool_executed(
                db,
                actor_user_id=user_id,
                run_id=run.id,
                step=step_index,
                tool=decision.tool_name,
                ok=execution.ok,
                latency_ms=execution.latency_ms,
            )
            if (
                not execution.ok
                and execution.summary == FORBIDDEN_KB_SUMMARY
            ):
                await audit_agent_tool_denied(
                    db,
                    actor_user_id=user_id,
                    run_id=run.id,
                    tool=decision.tool_name,
                )

        record = AgentStepRecord(
            step_index=step_index,
            tool_name=decision.tool_name,
            args=plan_args,
            ok=execution.ok,
            summary=execution.summary,
            latency_ms=execution.latency_ms,
            step_id=db_step.id if db_step is not None else None,
            data=execution.data,
        )
        records.append(record)
        state = reduce_observation(state, decision, execution, record)

        # L4：EvidenceMatcher → tool observation（默认关 → 原样 ledger）
        from app.services.agent.matcher_runtime import (
            maybe_apply_evidence_match_after_tool,
        )

        state = maybe_apply_evidence_match_after_tool(state, execution)

        await update_agent_run_steps_used(
            db,
            run_id=run.id,
            user_id=user_id,
            steps_used=state.steps_used,
        )

        if execution.ok and decision.tool_name in (
            "semantic_search",
            "search_documents",
        ):
            search_successes += 1

        await _safe_audit(
            extract_and_store_memory(
                db,
                user_id,
                query,
                kb_id=getattr(planner, "default_kb_id", None),
                tool_name=decision.tool_name,
                tool_data=execution.data,
                mode=run.mode,
                search_successes=search_successes,
            )
        )

        step_capped = state.steps_used >= max_steps
        if step_capped:
            capped = True

        await effective_hooks.on_tool_result(
            ToolResultEvent(
                step=step_index,
                tool=decision.tool_name,
                ok=execution.ok,
                summary=execution.summary,
                latency_ms=execution.latency_ms,
                capped=step_capped,
            )
        )
        await effective_hooks.on_agent_budget(
            AgentBudgetEvent(
                steps_used=state.steps_used,
                max_steps=max_steps,
                capped=step_capped,
            )
        )

        if step_capped:
            break
        # 成功 / 失败均回到 while 顶 → decide_next（re-decide）

    if (
        terminal_decision is None
        and not timed_out
        and state.steps_used >= max_steps
    ):
        capped = True

    # L4-W5.5a：预算耗尽无 terminal 时用 StopPolicy 收敛（默认关 → None）
    if terminal_decision is None and not timed_out:
        from app.services.agent.stop_policy import maybe_stop_terminal

        terminal_decision = maybe_stop_terminal(state)

    return AgentRunOutcome(
        run_id=run.id,
        steps_used=state.steps_used,
        max_steps=max_steps,
        capped=capped,
        timed_out=timed_out,
        steps=tuple(records),
        low_confidence=_detect_low_confidence(records),
        terminal_decision=terminal_decision,
    )


async def _run_react_loop_until_outcome(
    db: AsyncSession,
    *,
    user_id: UUID,
    thread_id: UUID,
    query: str,
    workspace: WorkspaceScope,
    tool_scope: AgentToolScope,
    planner: ToolPlanner,
    org_scope: OrgScope | None,
    current_user: CurrentUser | None,
    effective_hooks: ToolRuntimeHooks,
    run: AgentRun,
    max_steps: int,
    timeout_seconds: float,
) -> AgentRunOutcome:
    """ReAct 循环主体（返回 outcome；终态收敛由 run_react_loop 负责）。"""
    # L3-W3：NextActionPlanner → Observation-driven loop（flag 关时工厂不会产出）
    if isinstance(planner, NextActionPlanner):
        return await _run_l3_next_action_loop(
            db,
            user_id=user_id,
            thread_id=thread_id,
            query=query,
            workspace=workspace,
            tool_scope=tool_scope,
            planner=planner,
            org_scope=org_scope,
            current_user=current_user,
            effective_hooks=effective_hooks,
            run=run,
            max_steps=max_steps,
            timeout_seconds=timeout_seconds,
        )

    records: list[AgentStepRecord] = []
    steps_used = 0
    capped = False
    timed_out = False
    deadline = time.monotonic() + timeout_seconds
    reflection_count = 0
    memory_ctx = ""
    tool_run_counts: dict[str, int] = {}
    search_successes = 0
    fallback_queue: list[ToolFallbackPlan] = []
    replan_count = 0
    tool_fallback_count = 0
    # 工具失败提示重规划上限；0 表示关闭重规划。
    replan_limit = settings.agent_max_tool_replans

    # E3：加载记忆注入 planner（仅 LLMPlanner 路径，受 ablation 开关控制）
    if isinstance(planner, LLMPlanner) and settings.agent_memory_enabled:
        memories = await load_active_memories(db, user_id)
        memory_ctx = format_memory_context(memories)
        planner._memory_context = memory_ctx

    # W2：先预注册工具 breaker，确保 web_search 的 2/15 override 在惰性创建前生效。
    ensure_agent_tool_breakers()
    frozen_tools: set[str] = set()
    frozen_skips = 0

    while steps_used < max_steps:
        if time.monotonic() >= deadline:
            timed_out = True
            break

        step_index = steps_used + 1
        current_source: str | None = None
        if fallback_queue:
            fallback_plan = fallback_queue.pop(0)
            materialized = materialize_fallback_step(
                fallback_plan, tuple(records)
            )
            if materialized is None:
                continue
            current_source = fallback_plan.source
            plan = ToolCallPlan(
                tool_name=materialized.tool_name,
                args=_json_safe_args(materialized.args),
            )
        else:
            plan = await planner.next_tool_call(
                query=query,
                step_index=step_index,
                steps_used=steps_used,
                max_steps=max_steps,
                prior_steps=tuple(records),
            )
            if plan is None:
                break

        if plan.tool_name in frozen_tools:
            logger.warning("工具 %s 已熔断冻结，本轮跳过", plan.tool_name)
            if current_source is None:
                frozen_skips += 1
                if frozen_skips >= MAX_FROZEN_TOOL_SKIPS:
                    break
            continue

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

        # G2 W3：每轮 tool_run_counts 泛化 + web_search 窗口限流（拒绝 = disabled + 等价替换）
        _is_external = plan.tool_name in EXTERNAL_TOOL_NAMES
        run_limit = resolve_tool_run_limit(plan.tool_name)
        limited_summary: str | None = None
        limited_reason: str | None = None

        if run_limit is not None and tool_run_counts.get(plan.tool_name, 0) >= run_limit:
            limited_summary = "工具调用已达本轮上限"
            limited_reason = "tool_run_limit"
        elif _is_external and settings.external_tools_enabled:
            if not await allow_tool_window(plan.tool_name):
                limited_summary = "工具已达全局窗口限流上限"
                limited_reason = "tool_window_limit"

        if limited_summary is None:
            tool_run_counts[plan.tool_name] = (
                tool_run_counts.get(plan.tool_name, 0) + 1
            )
            execution = await _execute_step(
                db,
                workspace=workspace,
                tool_scope=tool_scope,
                org_scope=org_scope,
                current_user=current_user,
                tool_name=plan.tool_name,
                args=plan.args,
                run_id=run.id,
                thread_id=thread_id,
                user_id=user_id,
            )
            ok = execution.ok
            summary = execution.summary
            latency_ms = execution.latency_ms
            data = execution.data
            failure = execution.failure
        else:
            inc_agent_tool_call(plan.tool_name, "limited", external=_is_external)
            limited_failure = ToolFailure(
                kind=ToolFailureKind.disabled,
                tool_name=plan.tool_name,
                summary=limited_summary,
            )
            ok = False
            summary = limited_summary
            latency_ms = 0
            data = None
            failure = limited_failure
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
                reason=limited_reason,
            )
            await update_agent_run_steps_used(
                db, run_id=run.id, user_id=user_id, steps_used=steps_used,
            )
            record = AgentStepRecord(
                step_index=step_index,
                tool_name=plan.tool_name,
                args=plan.args,
                ok=False,
                summary=summary,
                latency_ms=0,
                data=None,
            )
            records.append(record)
            await effective_hooks.on_agent_budget(
                AgentBudgetEvent(
                    steps_used=steps_used,
                    max_steps=max_steps,
                    capped=step_capped,
                )
            )
            if step_capped:
                break
            equivalent = find_equivalent_tool(
                limited_failure,
                record,
                remaining_steps=max_steps - steps_used,
                default_kb_id=getattr(planner, "default_kb_id", None),
            )
            if equivalent:
                fallback_queue.extend(equivalent)
                tool_fallback_count += len(equivalent)
            continue

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

        if ok and plan.tool_name in ("semantic_search", "search_documents"):
            search_successes += 1

        # ── E2 迭代反思（仅 LLMPlanner 路径）──
        if (
            isinstance(planner, LLMPlanner)
            and failure is None
            and reflection_count < settings.agent_max_reflections
        ):
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
                    # M1-W2 候选①：分解链级状态（S2 整题直检每链至多 1 次）
                    chain_state: dict[str, Any] = {}
                    for sq in sub_queries[:3]:
                        if steps_used >= max_steps:
                            capped = True
                            break
                        sub = LLMPlannerFactory.create(
                            sq,
                            default_kb_id=getattr(planner, "default_kb_id", None),
                            memory_context=memory_ctx or "",
                        )
                        p = await sub.next_tool_call(
                            query=sq, step_index=1, steps_used=0,
                            max_steps=max_steps, prior_steps=(),
                        )
                        if p is None or p.tool_name not in (
                            "semantic_search", "search_documents",
                        ):
                            continue
                        sub_step_index = steps_used + 1
                        await effective_hooks.on_tool_start(
                            ToolStartEvent(
                                step=sub_step_index,
                                tool=p.tool_name,
                                args_summary=build_args_summary(p.tool_name, p.args),
                            )
                        )
                        db_sub = await create_agent_step(
                            db,
                            run_id=run.id,
                            user_id=user_id,
                            step_index=sub_step_index,
                            tool_name=p.tool_name,
                            args_json=p.args,
                        )
                        sub_execution = await _execute_step(
                            db, workspace=workspace, tool_scope=tool_scope,
                            org_scope=org_scope, current_user=current_user,
                            tool_name=p.tool_name, args=p.args,
                            run_id=run.id, thread_id=thread_id, user_id=user_id,
                        )
                        _ok2 = sub_execution.ok
                        _s2 = sub_execution.summary
                        _l2 = sub_execution.latency_ms
                        _d2 = sub_execution.data
                        steps_used = sub_step_index
                        sub_capped = steps_used >= max_steps
                        if sub_capped:
                            capped = True
                        if db_sub is not None:
                            await finish_agent_step(
                                db,
                                step_id=db_sub.id,
                                user_id=user_id,
                                ok=_ok2,
                                result_summary=_s2,
                                latency_ms=_l2,
                            )
                        await audit_agent_tool_executed(
                            db,
                            actor_user_id=user_id,
                            run_id=run.id,
                            step=sub_step_index,
                            tool=p.tool_name,
                            ok=_ok2,
                            latency_ms=_l2,
                        )
                        if not _ok2 and _s2 == FORBIDDEN_KB_SUMMARY:
                            await audit_agent_tool_denied(
                                db,
                                actor_user_id=user_id,
                                run_id=run.id,
                                tool=p.tool_name,
                            )
                        await update_agent_run_steps_used(
                            db,
                            run_id=run.id,
                            user_id=user_id,
                            steps_used=steps_used,
                        )
                        sub_record = AgentStepRecord(
                            step_index=sub_step_index,
                            tool_name=p.tool_name,
                            args=p.args,
                            ok=_ok2,
                            summary=_s2,
                            latency_ms=_l2,
                            step_id=db_sub.id if db_sub is not None else None,
                            data=_d2,
                        )
                        # M1-W2 候选① 漂移守卫：子查询检索结果照单全收前核对命中质量
                        # （默认关零激活；开启时漂移走 S1 收敛改写 / S2 整题直检回退）
                        recovery_records, steps_used = await guard_sub_query_drift(
                            db,
                            sub_query=sq,
                            original_query=query,
                            sub_args=p.args,
                            sub_execution=sub_execution,
                            steps_used=steps_used,
                            max_steps=max_steps,
                            workspace=workspace,
                            tool_scope=tool_scope,
                            org_scope=org_scope,
                            current_user=current_user,
                            run_id=run.id,
                            thread_id=thread_id,
                            user_id=user_id,
                            chain_state=chain_state,
                        )
                        # 子查询合并贡献：漂移守卫恢复时以恢复记录替换原始记录（hits 不并入）；
                        # 否则保留原子查询记录，并在证据不足时由 M2 W2 策略重检接管
                        if recovery_records:
                            merged_records = list(recovery_records)
                        else:
                            merged_records = [sub_record]
                            # ── M2 W2 证据不足自适应重检（S1 改写 / S2 整题直检回退）──
                            ev_recovery_records, steps_used = await guard_evidence_insufficiency(
                                db,
                                sub_query=sq,
                                original_query=query,
                                sub_args=p.args,
                                sub_execution=sub_execution,
                                steps_used=steps_used,
                                max_steps=max_steps,
                                workspace=workspace,
                                tool_scope=tool_scope,
                                org_scope=org_scope,
                                current_user=current_user,
                                run_id=run.id,
                                thread_id=thread_id,
                                user_id=user_id,
                                chain_state=chain_state,
                            )
                            if ev_recovery_records:
                                merged_records = ev_recovery_records
                        records.extend(merged_records)
                        await update_agent_run_steps_used(
                            db,
                            run_id=run.id,
                            user_id=user_id,
                            steps_used=steps_used,
                        )
                        for _recovery_record in merged_records:
                            if _recovery_record.ok and _recovery_record.data:
                                all_hits.append(_recovery_record.data)
                            if _recovery_record.ok and _recovery_record.tool_name in (
                                "semantic_search", "search_documents",
                            ):
                                search_successes += 1
                        sub_capped = steps_used >= max_steps
                        if sub_capped:
                            capped = True
                        # ── M2 证据充分性判定（W1 observation mode；只记录，不触发策略）──
                        if settings.agent_evidence_sufficiency_obs:
                            from app.services.rag.evidence import (
                                check_evidence_sufficiency,
                            )

                            _evidence_hits = (
                                _d2.hits
                                if _d2 and hasattr(_d2, "hits")
                                else ()
                            )
                            verdict = check_evidence_sufficiency(
                                _evidence_hits, sq,
                            )
                            await _safe_audit(audit_agent_reflection(
                                db,
                                actor_user_id=user_id,
                                run_id=run.id,
                                signal="evidence_check",
                                new_query=(
                                    f"sufficient={verdict.sufficient}"
                                    f" reason={verdict.reason}"
                                ),
                            ))
                            # observation mode：只记录判定结果；策略触发由 W2 guard_evidence_insufficiency 负责
                        await effective_hooks.on_tool_result(
                            ToolResultEvent(
                                step=sub_step_index,
                                tool=p.tool_name,
                                ok=_ok2,
                                summary=_s2,
                                latency_ms=_l2,
                                capped=sub_capped,
                            )
                        )
                        await effective_hooks.on_agent_budget(
                            AgentBudgetEvent(
                                steps_used=steps_used,
                                max_steps=max_steps,
                                capped=sub_capped,
                            )
                        )
                        if sub_capped:
                            break
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
            mode=run.mode, search_successes=search_successes,
        ))

        # 反思子步骤计入预算后，若已触顶则本轮同步按 capped 收尾
        step_capped = steps_used >= max_steps
        if step_capped:
            capped = True

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

        if failure is not None and failure.breaker_open:
            frozen_tools.add(plan.tool_name)

        if (
            failure is not None
            and current_source != "equivalent"
            and failure.kind
            in (ToolFailureKind.infra, ToolFailureKind.disabled)
        ):
            equivalent = find_equivalent_tool(
                failure,
                record,
                remaining_steps=max_steps - steps_used,
                default_kb_id=getattr(planner, "default_kb_id", None),
            )
            if equivalent:
                fallback_queue.extend(equivalent)
                tool_fallback_count += len(equivalent)
                continue

        if (
            failure is not None
            and should_replan(failure)
            and replan_count < replan_limit
            and hasattr(planner, "replan_after_failure")
        ):
            replan_count += 1
            replanned = await planner.replan_after_failure(
                query=query,
                step_index=step_index,
                steps_used=steps_used,
                max_steps=max_steps,
                prior_steps=tuple(records),
                failure=failure,
            )
            if replanned is not None:
                await _safe_audit(audit_agent_tool_replanned(
                    db,
                    actor_user_id=user_id,
                    run_id=run.id,
                    step=step_index,
                    tool=plan.tool_name,
                    kind=failure.kind.value,
                    fallback_tool=replanned.tool_name,
                    replan_count=replan_count,
                ))
                fallback_queue.append(
                    ToolFallbackPlan(
                        replanned.tool_name,
                        replanned.args,
                        "replan",
                    )
                )
                continue

    outcome = AgentRunOutcome(
        run_id=run.id,
        steps_used=steps_used,
        max_steps=max_steps,
        capped=capped,
        timed_out=timed_out,
        steps=tuple(records),
        # E2 信号 B：低置信度标记（循环外，outcome 构造时判定）
        low_confidence=_detect_low_confidence(records),
        tool_fallback_count=tool_fallback_count,
        tool_replanned=replan_count,
    )
    return outcome
