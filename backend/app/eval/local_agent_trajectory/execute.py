"""Run one research case through product ``run_react_loop``."""

from __future__ import annotations

import time
import uuid
from typing import Any
from uuid import UUID

from app.core.database import SessionLocal
from app.eval.local_agent_trajectory.cases import TrajectoryCase, tool_result_for
from app.eval.local_agent_trajectory.injection import (
    RecordingAdapter,
    TracingPlanner,
    apply_research_flags,
    patch_planner_llm,
    restore_flags,
    restore_planner_llm,
    wrap_stop_policy,
)
from app.eval.local_agent_trajectory.schema import StepTrace, excerpt_raw
from app.eval.local_agent_trajectory.scoring import finalize_trajectory
from app.models.enums import AccountType
from app.models.user import User
from app.services.agent.fact_contracts import fact_coverage_ratio
from app.services.agent.runtime import run_react_loop
from app.services.agent.tools.scope import AgentToolScope
from app.services.agent.types import FactStatus
from app.services.auth.password import hash_password
from app.services.rag.thread_persistence import create_workspace_thread
from app.services.workspace.scope import WorkspaceKind, WorkspaceScope


async def _ensure_research_user() -> UUID:
    async with SessionLocal() as db:
        email = f"w8p0-{uuid.uuid4().hex[:10]}@research.local"
        username = f"w8p0{uuid.uuid4().hex[:8]}"[:32]
        user = User(
            email=email,
            username=username,
            password_hash=hash_password("W8p0Research!a"),
            account_type=AccountType.personal,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user.id


async def _create_thread(user_id: UUID) -> UUID:
    async with SessionLocal() as db:
        thread = await create_workspace_thread(
            db,
            user_id=user_id,
            workspace_kind=WorkspaceKind.personal,
            workspace_org_id=None,
            department_id=None,
        )
        await db.commit()
        return thread.id


def _workspace(user_id: UUID) -> WorkspaceScope:
    return WorkspaceScope(kind=WorkspaceKind.personal, user_id=user_id, org_id=None)


async def run_one_case(
    case: TrajectoryCase,
    adapter: RecordingAdapter,
    *,
    model_id: str,
    thinking_mode: str,
    user_id: UUID | None = None,
    run_timeout_seconds: float = 600.0,
) -> Any:
    """Query → product run_react_loop → traced TrajectoryResult."""
    from app.services.agent import matcher_runtime, stop_policy
    from app.services.agent.decomposer import maybe_fact_goals_for_init as real_goals
    from app.services.agent import decomposer as decomposer_mod
    from app.services.agent import runtime as runtime_mod

    saved = apply_research_flags()
    captures: list = []
    tool_calls = {"n": 0}

    async def _goals(_query: str):
        return case.fact_goals

    async def _search(*_a, query: str = "", **_k):
        idx = tool_calls["n"]
        tool_calls["n"] = idx + 1
        return tool_result_for(case, query, idx)

    async def _search_docs(*_a, **_k):
        from app.services.agent.tools.search_documents import SearchDocumentsToolResult

        return SearchDocumentsToolResult(
            ok=False, data=None, summary="w8_deterministic_semantic_search_only"
        )

    stop_wrapped = wrap_stop_policy(captures)
    real_matcher = matcher_runtime.maybe_apply_evidence_match_after_tool

    def _matcher(state, execution):  # noqa: ANN001
        updated = real_matcher(state, execution)
        if captures:
            cap = captures[-1]
            cap.tool_name = cap.stop_after.tool_name if cap.stop_after else cap.planner_decision.tool_name
            cap.tool_args = dict(
                (cap.stop_after.args if cap.stop_after else cap.planner_decision.args) or {}
            )
            cap.tool_success = bool(execution.ok)
            cap.observation_summary = execution.summary or ""
            cap.facts_after = {g.id: g.status.value for g in updated.evidence.facts}
            cap.coverage_after = fact_coverage_ratio(updated.evidence)
            cap.conflicts_after = [
                g.id
                for g in updated.evidence.facts
                if g.status == FactStatus.conflicted
            ]
        return updated

    decomposer_mod.maybe_fact_goals_for_init = _goals  # type: ignore[method-assign]
    runtime_mod.run_semantic_search = _search  # type: ignore[method-assign]
    runtime_mod.run_search_documents = _search_docs  # type: ignore[method-assign]
    stop_policy.apply_stop_policy_decision = stop_wrapped  # type: ignore[method-assign]
    matcher_runtime.maybe_apply_evidence_match_after_tool = _matcher  # type: ignore[method-assign]
    patch_planner_llm(adapter)

    planner = TracingPlanner(case.query, adapter=adapter, captures=captures)
    started = time.perf_counter()
    started_at = __import__(
        "app.eval.local_agent_trajectory.schema", fromlist=["utc_now_iso"]
    ).utc_now_iso()
    uid = user_id or await _ensure_research_user()
    thread_id = await _create_thread(uid)
    try:
        async with SessionLocal() as db:
            outcome = await run_react_loop(
                db,
                user_id=uid,
                thread_id=thread_id,
                query=case.query,
                workspace=_workspace(uid),
                tool_scope=AgentToolScope(),
                planner=planner,
                max_steps=case.max_steps,
                timeout_seconds=run_timeout_seconds,
            )
        duration_ms = (time.perf_counter() - started) * 1000.0
        # Terminal-only rounds never hit matcher; copy before→after.
        for cap in captures:
            if not cap.facts_after:
                cap.facts_after = dict(cap.facts_before)
                cap.coverage_after = cap.coverage_before
                cap.conflicts_after = list(cap.conflicts_before)
        steps = [_step_from_capture(c) for c in captures]
        return finalize_trajectory(
            case,
            steps=steps,
            outcome=outcome,
            model_id=model_id,
            thinking_mode=thinking_mode,
            started_at=started_at,
            duration_ms=duration_ms,
        )
    finally:
        decomposer_mod.maybe_fact_goals_for_init = real_goals  # type: ignore[method-assign]
        restore_flags(saved)
        restore_planner_llm()
        _restore_originals(runtime_mod, stop_policy, matcher_runtime)


_ORIG: dict[str, Any] = {}


def _restore_originals(runtime_mod, stop_policy, matcher_runtime) -> None:  # noqa: ANN001
    from app.services.agent.tools.semantic_search import run_semantic_search as real_search

    orig_stop = _ORIG.get("stop")
    orig_match = _ORIG.get("match")
    orig_search = _ORIG.get("search")
    orig_docs = _ORIG.get("search_docs")
    if orig_stop is not None:
        stop_policy.apply_stop_policy_decision = orig_stop
    if orig_match is not None:
        matcher_runtime.maybe_apply_evidence_match_after_tool = orig_match
    if orig_search is not None:
        runtime_mod.run_semantic_search = orig_search
    else:
        runtime_mod.run_semantic_search = real_search
    if orig_docs is not None:
        runtime_mod.run_search_documents = orig_docs


def _capture_originals() -> None:
    from app.services.agent import matcher_runtime, stop_policy, runtime as runtime_mod

    _ORIG.setdefault("stop", stop_policy.apply_stop_policy_decision)
    _ORIG.setdefault("match", matcher_runtime.maybe_apply_evidence_match_after_tool)
    _ORIG.setdefault("search", runtime_mod.run_semantic_search)
    _ORIG.setdefault("search_docs", runtime_mod.run_search_documents)


_capture_originals()


def _step_from_capture(cap) -> StepTrace:  # noqa: ANN001
    decision = cap.stop_after or cap.planner_decision
    planner_d = cap.planner_decision
    return StepTrace(
        step_index=cap.step_index,
        planner_raw_response_excerpt=excerpt_raw(cap.raw),
        planner_parse_success=cap.parse_ok,
        planner_decision={
            "action": planner_d.action.value,
            "tool_name": planner_d.tool_name,
            "args": dict(planner_d.args or {}),
            "reason_code": planner_d.reason_code,
        },
        decision_valid=cap.decision_valid,
        stop_policy_effect=cap.stop_effect,
        tool_name=decision.tool_name if decision.action.value == "tool" else cap.tool_name,
        tool_args=dict(decision.args or {}) if decision.action.value == "tool" else cap.tool_args,
        tool_success=cap.tool_success,
        observation_summary=cap.observation_summary,
        fact_status_before=dict(cap.facts_before),
        fact_status_after=dict(cap.facts_after),
        evidence_coverage=float(cap.coverage_after),
        conflicts=list(cap.conflicts_after or cap.conflicts_before),
        latency_ms=round(cap.latency_ms, 1),
        error=cap.provider_error or cap.parse_error,
        events=[],
        recoverable_if_repaired=_fence_only(cap.raw, cap.parse_ok),
    )


def _fence_only(raw: str, parse_ok: bool) -> bool:
    text = (raw or "").strip()
    return (not parse_ok) and text.startswith("```")
