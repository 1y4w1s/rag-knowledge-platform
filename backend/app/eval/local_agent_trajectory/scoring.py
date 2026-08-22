"""W8 P0 scoring: model vs system vs end-to-end (no product parser repair)."""

from __future__ import annotations

import statistics
from typing import Any

from app.eval.local_agent_trajectory.cases import TrajectoryCase
from app.eval.local_agent_trajectory.schema import (
    FailureClass,
    StepTrace,
    SuiteSummary,
    TrajectoryResult,
)
from app.services.agent.types import AgentRunOutcome


_MODEL_FAIL = {
    FailureClass.MODEL_TIMEOUT.value,
    FailureClass.MODEL_MALFORMED_JSON.value,
    FailureClass.MODEL_SCHEMA_FAILURE.value,
    FailureClass.MODEL_TOOL_MAPPING_FAILURE.value,
    FailureClass.MODEL_WRONG_ACTION.value,
    FailureClass.MODEL_PREMATURE_FINISH.value,
    FailureClass.MODEL_HALLUCINATED_TOOL.value,
}

_TOOL_NAMES = {
    "semantic_search",
    "search_documents",
    "get_chunk_excerpt",
    "grep_in_document",
    "compare_chunks",
    "list_knowledge_bases",
    "web_search",
}


def classify_raw_action(raw: str, parse_ok: bool, parse_error: str | None) -> list[str]:
    events: list[str] = []
    text = (raw or "").strip()
    if not parse_ok:
        action = _extract_json_action(text)
        if action in _TOOL_NAMES:
            events.append(FailureClass.MODEL_TOOL_MAPPING_FAILURE.value)
        elif parse_error in {"parse_error", "empty_output", "not_single_object"} or (
            text.startswith("```") and not parse_ok
        ):
            events.append(FailureClass.MODEL_MALFORMED_JSON.value)
        else:
            events.append(FailureClass.MODEL_SCHEMA_FAILURE.value)
    return events


def _extract_json_action(raw: str) -> str | None:
    import json
    import re

    m = re.search(r'"action"\s*:\s*"([^"]+)"', raw or "")
    if m:
        return m.group(1)
    try:
        data = json.loads(raw)
        if isinstance(data, dict) and isinstance(data.get("action"), str):
            return data["action"]
    except (json.JSONDecodeError, TypeError, ValueError):
        return None
    return None


def classify_step(step: StepTrace, case: TrajectoryCase) -> list[str]:
    events: list[str] = list(step.events)
    error = (step.error or "").lower()
    if "timeout" in error:
        events.append(FailureClass.MODEL_TIMEOUT.value)
    events.extend(
        classify_raw_action(
            step.planner_raw_response_excerpt,
            step.planner_parse_success,
            step.error,
        )
    )
    planner_action = str((step.planner_decision or {}).get("action") or "")
    planner_tool = (step.planner_decision or {}).get("tool_name")
    missing_before = [
        fid
        for fid, st in (step.fact_status_before or {}).items()
        if st in {"missing", "partial"}
    ]
    if planner_action == "finish" and missing_before:
        events.append(FailureClass.MODEL_PREMATURE_FINISH.value)
    if step.stop_policy_effect in {"block_finish_retrieve", "force_refuse", "rewrite"}:
        events.append(FailureClass.SYSTEM_STOP_BLOCK.value)
    if step.tool_success is False:
        events.append(FailureClass.TOOL_EXECUTION_FAILURE.value)
    if planner_action == "tool" and planner_tool and planner_tool not in _TOOL_NAMES:
        events.append(FailureClass.MODEL_HALLUCINATED_TOOL.value)
    if (
        case.category in {"missing_fact", "multi_fact"}
        and planner_action in {"finish", "refuse", "clarify"}
        and missing_before
        and step.step_index == 0
        and "MODEL_PREMATURE_FINISH" not in events
        and planner_action != "clarify"
    ):
        if planner_action == "finish":
            events.append(FailureClass.MODEL_PREMATURE_FINISH.value)
        elif planner_action == "refuse" and case.category != "clarify":
            events.append(FailureClass.MODEL_WRONG_ACTION.value)
    if step.conflicts or any(
        st == "conflicted" for st in (step.fact_status_after or {}).values()
    ):
        events.append(FailureClass.EVIDENCE_CONFLICT.value)
    # unique preserve order
    seen: set[str] = set()
    out: list[str] = []
    for e in events:
        if e not in seen:
            seen.add(e)
            out.append(e)
    return out


def _coverage_complete(steps: list[StepTrace], outcome: AgentRunOutcome) -> bool:
    if not steps:
        return False
    last = steps[-1]
    statuses = last.fact_status_after or last.fact_status_before
    if not statuses:
        return False
    return all(st == "covered" for st in statuses.values()) and not last.conflicts


def _fake_complete(terminal_reason: str | None, evidence_complete: bool) -> bool:
    return (terminal_reason or "") == "facts_covered" and not evidence_complete


def finalize_trajectory(
    case: TrajectoryCase,
    *,
    steps: list[StepTrace],
    outcome: AgentRunOutcome,
    model_id: str,
    thinking_mode: str,
    started_at: str,
    duration_ms: float,
) -> TrajectoryResult:
    terminal = outcome.terminal_decision
    terminal_action = terminal.action.value if terminal is not None else (
        "timeout" if outcome.timed_out else ("capped" if outcome.capped else None)
    )
    terminal_reason = terminal.reason_code if terminal is not None else None

    all_events: list[str] = []
    annotated: list[StepTrace] = []
    for step in steps:
        ev = classify_step(step, case)
        step.events = ev
        annotated.append(step)
        all_events.extend(ev)

    if outcome.timed_out:
        all_events.append(FailureClass.MODEL_TIMEOUT.value)
    if outcome.capped or (terminal_reason or "").endswith("_budget"):
        all_events.append(FailureClass.BUDGET_EXHAUSTED.value)
    if terminal_action == "refuse":
        all_events.append(FailureClass.SAFE_REFUSAL.value)
    if terminal_reason in {"facts_partial_budget", "facts_incomplete", "facts_partial"}:
        all_events.append(FailureClass.SAFE_PARTIAL.value)

    evidence_complete = _coverage_complete(annotated, outcome)
    if not evidence_complete and case.category not in {"conflict", "clarify", "budget", "tool_failure"}:
        if terminal_action == "finish" and not evidence_complete:
            all_events.append(FailureClass.EVIDENCE_INSUFFICIENT.value)

    premature = FailureClass.MODEL_PREMATURE_FINISH.value in all_events
    stop_block = FailureClass.SYSTEM_STOP_BLOCK.value in all_events
    if stop_block and premature:
        all_events.append(FailureClass.SYSTEM_RECOVERY.value)

    fake = _fake_complete(terminal_reason, evidence_complete)
    conflicted_end = any(
        st == "conflicted"
        for st in ((annotated[-1].fact_status_after if annotated else {}) or {}).values()
    )
    if conflicted_end and terminal_reason == "facts_covered":
        fake = True

    safe = (
        not fake
        and not (outcome.timed_out and terminal is None)
        and not (case.category == "conflict" and terminal_reason == "facts_covered")
    )
    if case.category == "tool_failure":
        polluted = any(
            (s.tool_success is False)
            and any(st == "covered" for st in (s.fact_status_after or {}).values())
            and all(st != "covered" for st in (s.fact_status_before or {}).values())
            for s in annotated
        )
        if polluted:
            safe = False

    model_fails = [e for e in all_events if e in _MODEL_FAIL]
    interventions = [
        e
        for e in all_events
        if e
        in {
            FailureClass.SYSTEM_STOP_BLOCK.value,
            FailureClass.SYSTEM_RECOVERY.value,
        }
    ]
    recovered = FailureClass.SYSTEM_RECOVERY.value in all_events
    system_saved = bool(interventions) and safe and (
        premature or FailureClass.MODEL_TOOL_MAPPING_FAILURE.value in all_events
        or FailureClass.MODEL_SCHEMA_FAILURE.value in all_events
        or FailureClass.MODEL_MALFORMED_JSON.value in all_events
    )
    # Mapping/schema fail-closed refuse is a system save if trajectory stays safe.
    if (
        safe
        and not system_saved
        and any(
            e
            in {
                FailureClass.MODEL_MALFORMED_JSON.value,
                FailureClass.MODEL_SCHEMA_FAILURE.value,
                FailureClass.MODEL_TOOL_MAPPING_FAILURE.value,
            }
            for e in all_events
        )
        and terminal_action in {"refuse", "finish", "clarify"}
        and not fake
    ):
        system_saved = True
        all_events.append(FailureClass.SYSTEM_RECOVERY.value)

    unrecovered = bool(model_fails) and not recovered and not (
        system_saved and safe
    )
    # If model failed but system saved to a safe end, not unrecovered.
    if system_saved and safe:
        unrecovered = False

    e2e = _end_to_end(case, terminal_action, terminal_reason, evidence_complete, safe, annotated)
    model_ok = (not model_fails) and all(s.planner_parse_success and s.decision_valid for s in annotated)
    if not annotated:
        model_ok = False
        all_events.append(FailureClass.UNKNOWN.value)

    unique_events = _uniq(all_events)
    return TrajectoryResult(
        case_id=case.case_id,
        category=case.category,
        query=case.query,
        model_id=model_id,
        thinking_mode=thinking_mode,
        started_at=started_at,
        duration_ms=round(duration_ms, 1),
        terminal_action=terminal_action,
        terminal_reason=terminal_reason,
        steps_used=outcome.steps_used,
        steps=annotated,
        task_success=e2e,
        safe_termination=safe,
        evidence_complete=evidence_complete,
        premature_finish=premature,
        model_failure_count=len([e for e in unique_events if e in _MODEL_FAIL]),
        system_intervention_count=len(
            [e for e in unique_events if e.startswith("SYSTEM_")]
        ),
        timeout=bool(outcome.timed_out),
        failure_class=unique_events,
        model_decision_success=model_ok,
        system_safety_success=safe,
        end_to_end_success=e2e,
        system_saved=system_saved,
        unrecovered_model_failure=unrecovered,
        events=unique_events,
    )


def _end_to_end(
    case: TrajectoryCase,
    terminal_action: str | None,
    terminal_reason: str | None,
    evidence_complete: bool,
    safe: bool,
    steps: list[StepTrace],
) -> bool:
    if not safe:
        return False
    cat = case.category
    if cat == "direct":
        return terminal_action == "finish" and (
            evidence_complete or (terminal_reason or "") in {"facts_covered", "evidence_sufficient"}
            or all(
                st == "covered"
                for st in ((steps[0].fact_status_before if steps else {}) or {}).values()
            )
        )
    if cat == "missing_fact":
        used_tool = any(s.tool_success for s in steps)
        return bool(used_tool and evidence_complete and terminal_action == "finish")
    if cat == "multi_fact":
        progressed = any(
            (s.evidence_coverage or 0) > 0 or any(v == "covered" for v in (s.fact_status_after or {}).values())
            for s in steps
        )
        return progressed and terminal_action in {"finish", "refuse"} and (
            evidence_complete or (terminal_reason or "").endswith("_budget")
        )
    if cat == "conflict":
        return terminal_action in {"refuse", "clarify"} or (
            terminal_action == "finish" and (terminal_reason or "") != "facts_covered"
        )
    if cat == "tool_failure":
        saw_fail = any(s.tool_success is False for s in steps)
        return saw_fail and terminal_action in {"refuse", "finish", "clarify"}
    if cat == "budget":
        return (terminal_reason or "").endswith("_budget") or terminal_action == "refuse"
    if cat == "clarify":
        return terminal_action in {"clarify", "refuse"}
    return False


def _uniq(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for x in items:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


def _rate(n: int, d: int) -> float:
    if d <= 0:
        return 0.0
    return round(n / d, 4)


def _pctile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return round(ordered[0], 1)
    k = (len(ordered) - 1) * p
    lo = int(k)
    hi = min(lo + 1, len(ordered) - 1)
    frac = k - lo
    return round(ordered[lo] * (1 - frac) + ordered[hi] * frac, 1)


def aggregate_summary(results: list[TrajectoryResult]) -> SuiteSummary:
    n = len(results)
    steps_all = [s for r in results for s in r.steps]
    parse_ok = sum(1 for s in steps_all if s.planner_parse_success)
    valid = sum(1 for s in steps_all if s.decision_valid)
    tool_steps = [s for s in steps_all if s.tool_success is not None]
    tool_ok = sum(1 for s in tool_steps if s.tool_success)
    expected_tool = [
        s
        for r in results
        for s in r.steps
        if r.category in {"missing_fact", "multi_fact", "tool_failure", "budget"}
        and any(
            st in {"missing", "partial"}
            for st in (s.fact_status_before or {}).values()
        )
    ]
    tool_sel_ok = 0
    for s in expected_tool:
        d = s.planner_decision or {}
        if d.get("action") == "tool" and d.get("tool_name") == "semantic_search":
            tool_sel_ok += 1
        elif s.stop_policy_effect == "block_finish_retrieve":
            # system retrieved; model did not select correctly
            pass
    latencies = [s.latency_ms for s in steps_all if s.latency_ms]
    used = [r.steps_used for r in results]
    fail_counts: dict[str, int] = {}
    for r in results:
        for e in r.failure_class:
            fail_counts[e] = fail_counts.get(e, 0) + 1

    by_cat: dict[str, dict[str, Any]] = {}
    cats = sorted({r.category for r in results})
    for cat in cats:
        subset = [r for r in results if r.category == cat]
        by_cat[cat] = {
            "count": len(subset),
            "end_to_end_success_rate": _rate(sum(1 for r in subset if r.end_to_end_success), len(subset)),
            "safe_termination_rate": _rate(sum(1 for r in subset if r.safe_termination), len(subset)),
            "system_saved_rate": _rate(sum(1 for r in subset if r.system_saved), len(subset)),
            "unrecovered_model_failure_rate": _rate(
                sum(1 for r in subset if r.unrecovered_model_failure), len(subset)
            ),
            "mean_steps": round(sum(r.steps_used for r in subset) / len(subset), 3) if subset else 0.0,
        }

    recovery_ok = sum(
        1
        for r in results
        if FailureClass.SYSTEM_RECOVERY.value in r.failure_class and r.safe_termination
    )
    recovery_n = sum(1 for r in results if FailureClass.SYSTEM_RECOVERY.value in r.failure_class)

    return SuiteSummary(
        trajectory_count=n,
        end_to_end_success_rate=_rate(sum(1 for r in results if r.end_to_end_success), n),
        safe_termination_rate=_rate(sum(1 for r in results if r.safe_termination), n),
        premature_finish_rate=_rate(sum(1 for r in results if r.premature_finish), n),
        planner_parse_success_rate=_rate(parse_ok, len(steps_all)),
        planner_decision_valid_rate=_rate(valid, len(steps_all)),
        tool_selection_accuracy=_rate(tool_sel_ok, len(expected_tool)),
        tool_execution_success_rate=_rate(tool_ok, len(tool_steps)),
        evidence_completion_rate=_rate(sum(1 for r in results if r.evidence_complete), n),
        system_intervention_rate=_rate(sum(1 for r in results if r.system_intervention_count > 0), n),
        system_recovery_success_rate=_rate(recovery_ok, recovery_n) if recovery_n else 0.0,
        system_saved_count=sum(1 for r in results if r.system_saved),
        system_saved_rate=_rate(sum(1 for r in results if r.system_saved), n),
        unrecovered_model_failure_rate=_rate(
            sum(1 for r in results if r.unrecovered_model_failure), n
        ),
        timeout_rate=_rate(sum(1 for r in results if r.timeout), n),
        budget_exhaustion_rate=_rate(
            sum(1 for r in results if FailureClass.BUDGET_EXHAUSTED.value in r.failure_class),
            n,
        ),
        mean_steps=round(sum(used) / n, 3) if n else 0.0,
        median_steps=round(float(statistics.median(used)), 3) if used else 0.0,
        latency_p50_ms=_pctile(latencies, 0.5),
        latency_p95_ms=_pctile(latencies, 0.95),
        latency_max_ms=round(max(latencies), 1) if latencies else None,
        by_category=by_cat,
        failure_counts=fail_counts,
    )
