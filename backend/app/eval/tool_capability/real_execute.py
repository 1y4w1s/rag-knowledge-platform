"""Run one TOOL P2 case through product run_react_loop + real L3 tools."""

from __future__ import annotations

import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any
from uuid import UUID

from app.core.database import SessionLocal
from app.eval.local_agent_trajectory.injection import (
    RecordingAdapter,
    RoundCapture,
    TracingPlanner,
    apply_research_flags,
    patch_planner_llm,
    restore_flags,
    restore_planner_llm,
    wrap_stop_policy,
)
from app.eval.tool_capability.fixtures import ADAPT_FIXTURE_TRAJECTORIES
from app.eval.tool_capability.schema import ToolStepInput, ToolTrajectoryInput
from app.eval.tool_capability.seed import SeededWorkspace, seed_case_workspace, workspace_for
from app.models.enums import AccountType
from app.models.user import User
from app.services.agent.fact_contracts import fact_coverage_ratio
from app.services.agent.runtime import run_react_loop
from app.services.agent.tools.list_knowledge_bases import ListKnowledgeBasesOutput
from app.services.agent.tools.scope import AgentToolScope
from app.services.agent.tools.search_documents import SearchDocumentsOutput
from app.services.agent.types import AgentActionKind, AgentRunOutcome, AgentStepRecord
from app.services.auth.password import hash_password
from app.services.rag.thread_persistence import create_workspace_thread
from app.services.workspace.scope import WorkspaceKind


@dataclass(slots=True)
class RealTrialRecord:
    case_id: str
    trial_index: int
    panel: str
    query: str
    model_id: str
    thinking_mode: str
    started_at: str
    duration_ms: float
    outcome: dict[str, Any]
    captures: list[dict[str, Any]]
    trajectory: dict[str, Any]
    trajectory_input: ToolTrajectoryInput
    seeded: dict[str, Any] = field(default_factory=dict)


def _utc_now_iso() -> str:
    from app.eval.local_agent_trajectory.schema import utc_now_iso

    return utc_now_iso()


def _serialize_observation(step: AgentStepRecord) -> Any:
    data = step.data
    if isinstance(data, SearchDocumentsOutput):
        return {
            "total": data.total,
            "summary": step.summary,
            "items": [
                {
                    "document_id": str(item.document_id),
                    "kb_id": str(item.kb_id),
                    "kb_name": item.kb_name,
                    "filename": item.filename,
                    "snippet": item.snippet,
                }
                for item in data.items
            ],
        }
    if isinstance(data, ListKnowledgeBasesOutput):
        return {
            "total": data.total,
            "scope_label": data.scope_label,
            "summary": step.summary,
            "items": [
                {
                    "kb_id": str(item.kb_id),
                    "name": item.name,
                    "document_count": item.document_count,
                }
                for item in data.items
            ],
        }
    if data is None:
        return None
    if hasattr(data, "__dataclass_fields__"):
        return asdict(data)
    return data


def _outcome_dict(outcome: AgentRunOutcome) -> dict[str, Any]:
    terminal = outcome.terminal_decision
    return {
        "run_id": str(outcome.run_id),
        "steps_used": outcome.steps_used,
        "max_steps": outcome.max_steps,
        "capped": outcome.capped,
        "timed_out": outcome.timed_out,
        "low_confidence": outcome.low_confidence,
        "terminal_action": terminal.action.value if terminal else None,
        "terminal_reason": terminal.reason_code if terminal else None,
        "steps": [
            {
                "step_index": s.step_index,
                "tool_name": s.tool_name,
                "args": dict(s.args or {}),
                "ok": s.ok,
                "summary": s.summary,
                "latency_ms": s.latency_ms,
                "observation": _serialize_observation(s),
            }
            for s in outcome.steps
        ],
    }


def _capture_dict(cap: RoundCapture) -> dict[str, Any]:
    d = cap.planner_decision
    return {
        "step_index": cap.step_index,
        "raw_excerpt": (cap.raw or "")[:2000],
        "parse_ok": cap.parse_ok,
        "parse_error": cap.parse_error,
        "parsed_action": cap.parsed_action,
        "parsed_tool": cap.parsed_tool,
        "parsed_args": dict(cap.parsed_args or {}),
        "planner_decision": {
            "action": d.action.value,
            "tool_name": d.tool_name,
            "args": dict(d.args or {}),
            "reason_code": d.reason_code,
        },
        "stop_effect": cap.stop_effect,
        "tool_name": cap.tool_name,
        "tool_args": dict(cap.tool_args or {}),
        "tool_success": cap.tool_success,
        "observation_summary": cap.observation_summary,
        "timed_out": cap.timed_out,
        "provider_error": cap.provider_error,
        "latency_ms": cap.latency_ms,
    }


def build_trajectory_input(
    *,
    case_id: str,
    outcome: AgentRunOutcome,
    captures: list[RoundCapture],
) -> ToolTrajectoryInput:
    template = ADAPT_FIXTURE_TRAJECTORIES[case_id]
    case = template.case

    tool_records = [s for s in outcome.steps if s.tool_name]
    first_tool_record = tool_records[0] if tool_records else None

    first_tool_cap: RoundCapture | None = None
    post_cap: RoundCapture | None = None
    for cap in captures:
        if cap.planner_decision.action == AgentActionKind.tool and first_tool_cap is None:
            first_tool_cap = cap
        elif first_tool_cap is not None and cap is not first_tool_cap and post_cap is None:
            post_cap = cap
            break

    selected_tool = None
    tool_args: dict[str, Any] = {}
    if first_tool_cap is not None:
        dec = first_tool_cap.stop_after or first_tool_cap.planner_decision
        if dec.action == AgentActionKind.tool:
            selected_tool = dec.tool_name
            tool_args = dict(dec.args or {})
    elif first_tool_record is not None:
        selected_tool = first_tool_record.tool_name
        tool_args = dict(first_tool_record.args or {})

    resolver_accepted: bool | None = None
    if first_tool_cap is None:
        resolver_accepted = None
    elif first_tool_record is not None and selected_tool == first_tool_record.tool_name:
        resolver_accepted = True
    elif first_tool_cap.planner_decision.action == AgentActionKind.tool and first_tool_record is None:
        resolver_accepted = False
    else:
        resolver_accepted = first_tool_record is not None

    execution_succeeded = first_tool_record.ok if first_tool_record else None
    execution_error = None if (first_tool_record is None or first_tool_record.ok) else first_tool_record.summary
    observation = _serialize_observation(first_tool_record) if first_tool_record else None

    post_action = None
    post_valid: bool | None = None
    if post_cap is not None:
        post_dec = post_cap.planner_decision
        post_action = post_dec.action.value
        post_valid = post_cap.parse_ok and post_cap.decision_valid
    elif outcome.terminal_decision is not None and first_tool_record is not None:
        post_action = outcome.terminal_decision.action.value
        post_valid = True

    terminal = outcome.terminal_decision
    terminal_action = terminal.action.value if terminal else None
    budget_exhausted = outcome.capped or (
        terminal is not None and terminal.reason_code == "budget_exhausted"
    )
    safe = terminal_action in {"finish", "refuse", "clarify"} and not outcome.timed_out

    step = ToolStepInput(
        planner_action="tool" if selected_tool else "other",
        selected_tool=selected_tool,
        tool_args=tool_args,
        resolver_accepted=resolver_accepted,
        execution_succeeded=execution_succeeded,
        execution_error=execution_error,
        observation=observation,
        post_observation_action=post_action,
        post_observation_decision_valid=post_valid,
    )
    return ToolTrajectoryInput(
        case=case,
        steps=[step] if selected_tool or first_tool_record else [],
        terminal_action=terminal_action,
        terminal_reason=terminal.reason_code if terminal else None,
        budget_exhausted=budget_exhausted,
        safe=safe,
    )


async def _ensure_thread(user_id: UUID) -> UUID:
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


async def run_real_trial(
    *,
    case_id: str,
    trial_index: int,
    panel: str,
    adapter: RecordingAdapter,
    model_id: str,
    thinking_mode: str,
    run_timeout_seconds: float = 600.0,
    seeded: SeededWorkspace | None = None,
) -> RealTrialRecord:
    from app.services.agent import decomposer as decomposer_mod
    from app.services.agent import matcher_runtime, stop_policy
    from app.services.agent.decomposer import maybe_fact_goals_for_init as real_goals

    template = ADAPT_FIXTURE_TRAJECTORIES[case_id]
    ws_seed = seeded or await seed_case_workspace(case_id)
    user_id = ws_seed.user_id

    saved = apply_research_flags()
    captures: list[RoundCapture] = []

    async def _goals(_query: str):
        return []

    stop_wrapped = wrap_stop_policy(captures)
    real_matcher = matcher_runtime.maybe_apply_evidence_match_after_tool

    def _matcher(state, execution):  # noqa: ANN001
        updated = real_matcher(state, execution)
        if captures:
            cap = captures[-1]
            cap.tool_name = (
                cap.stop_after.tool_name
                if cap.stop_after and cap.stop_after.action == AgentActionKind.tool
                else cap.planner_decision.tool_name
            )
            cap.tool_args = dict(
                (cap.stop_after.args if cap.stop_after else cap.planner_decision.args) or {}
            )
            cap.tool_success = bool(execution.ok)
            cap.observation_summary = execution.summary or ""
            cap.facts_after = {g.id: g.status.value for g in updated.evidence.facts}
            cap.coverage_after = fact_coverage_ratio(updated.evidence)
        return updated

    orig_stop = stop_policy.apply_stop_policy_decision
    orig_match = matcher_runtime.maybe_apply_evidence_match_after_tool
    decomposer_mod.maybe_fact_goals_for_init = _goals  # type: ignore[method-assign]
    stop_policy.apply_stop_policy_decision = stop_wrapped  # type: ignore[method-assign]
    matcher_runtime.maybe_apply_evidence_match_after_tool = _matcher  # type: ignore[method-assign]
    patch_planner_llm(adapter)

    planner = TracingPlanner(template.case.query, adapter=adapter, captures=captures)
    started = time.perf_counter()
    started_at = _utc_now_iso()
    thread_id = await _ensure_thread(user_id)
    try:
        async with SessionLocal() as db:
            outcome = await run_react_loop(
                db,
                user_id=user_id,
                thread_id=thread_id,
                query=template.case.query,
                workspace=workspace_for(user_id),
                tool_scope=AgentToolScope(),
                planner=planner,
                max_steps=5,
                timeout_seconds=run_timeout_seconds,
            )
            await db.commit()
    finally:
        decomposer_mod.maybe_fact_goals_for_init = real_goals  # type: ignore[method-assign]
        stop_policy.apply_stop_policy_decision = orig_stop  # type: ignore[method-assign]
        matcher_runtime.maybe_apply_evidence_match_after_tool = orig_match  # type: ignore[method-assign]
        restore_flags(saved)
        restore_planner_llm()

    duration_ms = (time.perf_counter() - started) * 1000.0
    trajectory = build_trajectory_input(case_id=case_id, outcome=outcome, captures=captures)
    return RealTrialRecord(
        case_id=case_id,
        trial_index=trial_index,
        panel=panel,
        query=template.case.query,
        model_id=model_id,
        thinking_mode=thinking_mode,
        started_at=started_at,
        duration_ms=round(duration_ms, 1),
        outcome=_outcome_dict(outcome),
        captures=[_capture_dict(c) for c in captures],
        trajectory={
            "case_id": case_id,
            "terminal_action": trajectory.terminal_action,
            "terminal_reason": trajectory.terminal_reason,
            "budget_exhausted": trajectory.budget_exhausted,
            "safe": trajectory.safe,
            "steps": [
                {
                    "selected_tool": s.selected_tool,
                    "tool_args": dict(s.tool_args or {}),
                    "resolver_accepted": s.resolver_accepted,
                    "execution_succeeded": s.execution_succeeded,
                    "observation": s.observation,
                    "post_observation_action": s.post_observation_action,
                }
                for s in trajectory.steps
            ],
        },
        trajectory_input=trajectory,
        seeded={
            "user_id": str(ws_seed.user_id),
            "kb_ids": [str(k) for k in ws_seed.kb_ids],
            "markers": dict(ws_seed.markers),
        },
    )

