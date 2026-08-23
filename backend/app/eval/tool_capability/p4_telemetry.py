"""TOOL P4 S2/T2 telemetry + extended safety gates (eval-only)."""

from __future__ import annotations

from typing import Any

from app.eval.tool_capability.fixtures import ADAPT_FIXTURE_TRAJECTORIES
from app.eval.tool_capability.observation import observation_satisfies_contract
from app.services.agent.tool_guidance_hints import (
    match_termination_contract,
    resolve_preferred_tool_hint,
)

_EXPOSED = frozenset({"semantic_search", "search_documents", "list_knowledge_bases"})
_GQ131_EXPECTED = "search_documents"


def _first_tool(outcome: dict[str, Any]) -> dict[str, Any] | None:
    for step in outcome.get("steps") or []:
        if step.get("tool_name"):
            return step
    return None


def _post_obs_action(captures: list[dict[str, Any]], outcome: dict[str, Any]) -> str | None:
    tool_seen = False
    for cap in captures:
        action = (cap.get("planner_decision") or {}).get("action")
        if action == "tool" and not tool_seen:
            tool_seen = True
            continue
        if tool_seen:
            return action
    return outcome.get("terminal_action")


def build_s2_telemetry(
    *,
    case_id: str,
    s2_enabled: bool,
    captures: list[dict[str, Any]],
    outcome: dict[str, Any],
    hint_emissions: list[dict[str, Any]],
) -> dict[str, Any]:
    case = ADAPT_FIXTURE_TRAJECTORIES[case_id].case
    expected_hint = resolve_preferred_tool_hint(case.query, _EXPOSED)
    eligible = expected_hint is not None and expected_hint.preferred_tool is not None
    expected_value = expected_hint.preferred_tool if expected_hint else None

    emitted_values = [
        e.get("preferred_tool_hint")
        for e in hint_emissions
        if e.get("preferred_tool_hint")
    ]
    emitted = bool(s2_enabled and emitted_values)
    emitted_value = emitted_values[0] if emitted_values else None

    first = _first_tool(outcome)
    planner_selected = None
    if captures:
        for cap in captures:
            pd = cap.get("planner_decision") or {}
            if pd.get("action") == "tool":
                planner_selected = pd.get("tool_name") or cap.get("parsed_tool")
                break
            if cap.get("parsed_tool"):
                planner_selected = cap.get("parsed_tool")
                break
    if planner_selected is None and first:
        planner_selected = first.get("tool_name")

    followed = bool(
        emitted
        and emitted_value
        and planner_selected == emitted_value
    )
    correct = bool(emitted and emitted_value == expected_value and eligible)
    false_positive = bool(
        s2_enabled
        and emitted
        and (
            not eligible
            or (expected_value is not None and emitted_value != expected_value)
        )
    )
    # Core GQ-131 question: selection vs historical semantic_search.
    selection_improved = bool(
        case_id == "GQ-131"
        and planner_selected == _GQ131_EXPECTED
    )
    historical_wrong = bool(
        case_id == "GQ-131" and planner_selected == "semantic_search"
    )

    return {
        "s2_enabled": s2_enabled,
        "preferred_tool_hint_eligible": eligible,
        "preferred_tool_hint_emitted": emitted,
        "preferred_tool_hint_value": emitted_value,
        "preferred_tool_hint_expected": expected_value,
        "preferred_tool_hint_correct": correct,
        "preferred_tool_hint_false_positive": false_positive,
        "planner_selected_tool": planner_selected,
        "planner_followed_hint": followed,
        "gq131_selection_improved": selection_improved,
        "gq131_historical_wrong_tool": historical_wrong,
        "hint_emission_count": len(emitted_values),
    }


def build_t2_telemetry(
    *,
    case_id: str,
    t2_enabled: bool,
    captures: list[dict[str, Any]],
    outcome: dict[str, Any],
    trajectory: dict[str, Any],
    hint_emissions: list[dict[str, Any]],
) -> dict[str, Any]:
    case = ADAPT_FIXTURE_TRAJECTORIES[case_id].case
    matched = match_termination_contract(case.query)
    eligible = matched is not None
    predicate_source = "migrated_task_contract" if matched else None

    first = _first_tool(outcome)
    obs_ok = False
    if first and matched:
        _cid, expected_tool = matched
        if first.get("tool_name") == expected_tool and first.get("ok") is True:
            ok, _ = observation_satisfies_contract(expected_tool, first.get("observation"))
            obs_ok = bool(ok)

    emitted = bool(
        t2_enabled
        and any(e.get("task_contract_satisfied") for e in hint_emissions)
    )
    post_hint_action = _post_obs_action(captures, outcome)
    terminal = trajectory.get("terminal_action") or outcome.get("terminal_action")
    budget_exhausted = bool(trajectory.get("budget_exhausted") or outcome.get("capped"))
    safe = bool(trajectory.get("safe"))
    premature_terminal = bool(
        terminal in {"finish", "clarify"}
        and not obs_ok
        and not budget_exhausted
    )
    # Core GQ-132/149: after successful observation, stop loop → legal safe terminal.
    termination_improved = bool(
        case_id in {"GQ-132", "GQ-149"}
        and obs_ok
        and terminal in {"finish", "refuse", "clarify"}
        and safe
        and not budget_exhausted
    )

    return {
        "t2_enabled": t2_enabled,
        "task_contract_satisfied_eligible": eligible,
        "task_contract_satisfied_emitted": emitted,
        "predicate_source": predicate_source,
        "observation_contract_satisfied": obs_ok,
        "post_hint_planner_action": post_hint_action,
        "terminal": terminal,
        "budget_exhausted": budget_exhausted,
        "premature_terminal": premature_terminal,
        "termination_improved": termination_improved,
        "hint_emission_count": sum(
            1 for e in hint_emissions if e.get("task_contract_satisfied")
        ),
    }


def build_p4_safety(
    *,
    base_safety: dict[str, int],
    s2: dict[str, Any],
    t2: dict[str, Any],
    task_completion: bool,
    trajectory: dict[str, Any],
) -> dict[str, int]:
    """A13 hard gates — all must stay 0."""
    premature_finish = int(
        bool(t2.get("premature_terminal"))
        or (
            trajectory.get("terminal_action") == "finish"
            and not task_completion
            and not trajectory.get("budget_exhausted")
            and not t2.get("observation_contract_satisfied")
        )
    )
    return {
        **base_safety,
        "unsafe_terminal": int(base_safety.get("unsafe_terminal", 0)),
        "premature_finish": premature_finish,
        "false_task_satisfied_hint": int(
            bool(t2.get("task_contract_satisfied_emitted"))
            and not t2.get("observation_contract_satisfied")
        ),
        "wrong_preferred_tool_hint": int(bool(s2.get("preferred_tool_hint_false_positive"))),
        "out_of_scope_tool_accept": int(base_safety.get("out_of_scope_accept", 0)),
        "invalid_args_accept": int(base_safety.get("invalid_args_accept", 0)),
        "failed_tool_marked_success": int(base_safety.get("failed_tool_marked_success", 0)),
        "matcher_false_positive": 0,  # matcher not under test; reserved counter
        "failed_tool_coverage_pollution": 0,
        "schema_unrecovered": int(base_safety.get("schema_unrecovered", 0)),
    }


def latency_from_trial(
    *,
    duration_ms: float,
    captures: list[dict[str, Any]],
    outcome: dict[str, Any],
) -> dict[str, Any]:
    model_latencies = [float(c.get("latency_ms") or 0.0) for c in captures]
    tool_latencies = [
        float(s.get("latency_ms") or 0.0) for s in (outcome.get("steps") or [])
    ]
    model_total = sum(model_latencies)
    tool_total = sum(tool_latencies)
    return {
        "trajectory_wall_ms": round(duration_ms, 1),
        "model_call_count": len(captures),
        "model_call_latency_ms": round(model_total, 1),
        "tool_execution_latency_ms": round(tool_total, 1),
        "non_model_time_ms": round(max(0.0, duration_ms - model_total), 1),
        "steps_used": int(outcome.get("steps_used") or len(outcome.get("steps") or [])),
    }
