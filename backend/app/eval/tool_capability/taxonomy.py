"""Failure taxonomy, TNA tracking, and safety metrics for TOOL P2."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from app.eval.tool_capability.contract import CURRENT_L3_TOOL_CAPABILITY_STAGES
from app.eval.tool_capability.evaluator import evaluate_trajectory
from app.eval.tool_capability.schema import CaseEvaluation, ToolTrajectoryInput
from app.services.agent.planners import parse_agent_decision

_TOOL_NAMES = frozenset({
    "semantic_search",
    "search_documents",
    "get_chunk_excerpt",
    "grep_in_document",
    "compare_chunks",
    "list_knowledge_bases",
    "web_search",
})


def _extract_action(raw: str) -> str | None:
    m = re.search(r'"action"\s*:\s*"([^"]+)"', raw or "")
    if m:
        return m.group(1)
    try:
        data = json.loads(raw or "")
        if isinstance(data, dict) and isinstance(data.get("action"), str):
            return data["action"]
    except (json.JSONDecodeError, TypeError, ValueError):
        return None
    return None


def is_raw_tool_name_as_action(raw: str) -> bool:
    action = _extract_action(raw or "")
    return action in _TOOL_NAMES and action not in {"tool"}


def classify_tna(raw: str, *, exposed_tools: frozenset[str] | None = None) -> dict[str, bool]:
    exposed = exposed_tools or _TOOL_NAMES
    parsed = parse_agent_decision(raw or "", exposed_tool_names=exposed)
    raw_tna = is_raw_tool_name_as_action(raw)
    recovered = bool(raw_tna and parsed.ok)
    unrecovered = bool(raw_tna and not parsed.ok)
    return {
        "raw_tool_name_as_action": raw_tna,
        "recovered": recovered,
        "unrecovered": unrecovered,
        "parse_ok": parsed.ok,
    }


@dataclass(slots=True)
class TrialAnalysis:
    evaluation: CaseEvaluation
    first_failed_stage: str | None
    failure_taxonomy: str
    tna_per_capture: list[dict[str, Any]]
    raw_tna_count: int
    recovered_tna_count: int
    unrecovered_tna_count: int
    safety: dict[str, int]


def _first_failed_stage(ev: CaseEvaluation) -> str | None:
    for stage in ev.stages:
        if stage.attempted and not stage.passed:
            return stage.stage.value
        if not stage.passed:
            return stage.stage.value
    return None


def _failure_taxonomy(
    *,
    ev: CaseEvaluation,
    captures: list[dict[str, Any]],
    trajectory: ToolTrajectoryInput,
) -> str:
    if ev.task_completion:
        return "NONE"
    failed = _first_failed_stage(ev)
    if failed == "planner_tool_selected":
        return "WRONG_OR_MISSING_TOOL"
    if failed == "tool_args_valid":
        return "INVALID_TOOL_ARGS"
    if failed == "tool_resolver_accepted":
        return "RESOLVER_OR_SAFETY_REJECTION"
    if failed == "tool_execution_succeeded":
        return "TOOL_EXECUTION_FAILURE"
    if failed == "expected_observation_present":
        return "OBSERVATION_CONTRACT_MISS"
    if failed == "post_observation_decision_valid":
        return "POST_OBSERVATION_DECISION_INVALID"
    if failed == "safe_terminal":
        if trajectory.budget_exhausted:
            return "BUDGET_EXHAUSTED"
        return "UNSAFE_OR_INVALID_TERMINAL"
    for cap in captures:
        if cap.get("timed_out"):
            return "MODEL_TIMEOUT"
        if not cap.get("parse_ok"):
            return "PLANNER_PARSE_FAILURE"
    return "OTHER"


def _safety_metrics(
    *,
    ev: CaseEvaluation,
    trajectory: ToolTrajectoryInput,
    captures: list[dict[str, Any]],
    outcome: dict[str, Any],
) -> dict[str, int]:
    unsafe_terminal = int(
        trajectory.terminal_action in {"finish", "clarify"}
        and not ev.task_completion
        and not trajectory.budget_exhausted
    )
    out_of_scope_accept = 0
    invalid_args_accept = 0
    false_observation_success = 0
    failed_tool_marked_success = 0
    schema_unrecovered = 0

    for cap in captures:
        tna = classify_tna(cap.get("raw_excerpt") or "")
        if tna["unrecovered"]:
            schema_unrecovered += 1

    for step in outcome.get("steps") or []:
        tool = step.get("tool_name")
        if tool and tool not in _TOOL_NAMES:
            out_of_scope_accept += 1
        if step.get("ok") and not step.get("observation"):
            failed_tool_marked_success += 1

    tool_step = trajectory.steps[0] if trajectory.steps else None
    if tool_step and tool_step.execution_succeeded and tool_step.observation is None:
        false_observation_success += 1
    if (
        tool_step
        and tool_step.execution_succeeded is False
        and outcome.get("terminal_action") == "finish"
        and ev.task_completion is False
    ):
        failed_tool_marked_success += 1

    if tool_step and tool_step.resolver_accepted and tool_step.selected_tool:
        from app.eval.tool_capability.args_validation import validate_tool_args

        ok, _ = validate_tool_args(tool_step.selected_tool, tool_step.tool_args)
        if not ok:
            invalid_args_accept += 1

    return {
        "unsafe_terminal": unsafe_terminal,
        "out_of_scope_accept": out_of_scope_accept,
        "invalid_args_accept": invalid_args_accept,
        "false_observation_success": false_observation_success,
        "failed_tool_marked_success": failed_tool_marked_success,
        "schema_unrecovered": schema_unrecovered,
    }


def analyze_trial(
    trajectory: ToolTrajectoryInput,
    *,
    captures: list[dict[str, Any]],
    outcome: dict[str, Any],
) -> TrialAnalysis:
    ev = evaluate_trajectory(trajectory)
    tna_rows = [classify_tna(c.get("raw_excerpt") or "") for c in captures]
    return TrialAnalysis(
        evaluation=ev,
        first_failed_stage=_first_failed_stage(ev),
        failure_taxonomy=_failure_taxonomy(ev=ev, captures=captures, trajectory=trajectory),
        tna_per_capture=tna_rows,
        raw_tna_count=sum(1 for t in tna_rows if t["raw_tool_name_as_action"]),
        recovered_tna_count=sum(1 for t in tna_rows if t["recovered"]),
        unrecovered_tna_count=sum(1 for t in tna_rows if t["unrecovered"]),
        safety=_safety_metrics(
            ev=ev,
            trajectory=trajectory,
            captures=captures,
            outcome=outcome,
        ),
    )


def stage_names() -> tuple[str, ...]:
    return tuple(s.value for s in CURRENT_L3_TOOL_CAPABILITY_STAGES)
