"""Reconstruct machine-readable failure corpus from frozen P2 trials."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.eval.tool_capability.observation import observation_satisfies_contract
from app.eval.tool_remediation_ablation.models import (
    CORPUS_SCHEMA,
    FAMILY_S_CASE,
    FAMILY_T_CASES,
    TARGET_TRIAL_COUNT,
    FailureFamily,
    FailureTrial,
    TraceStep,
)

CORPUS_REL = Path("tests/fixtures/l4_tool_capability/l4-tool-p3-p2-failure-corpus.json")

_EXPECTED_TOOL = {
    "GQ-131": "search_documents",
    "GQ-132": "list_knowledge_bases",
    "GQ-149": "search_documents",
}

_QUERIES = {
    "GQ-131": "How to search documents across knowledge bases?",
    "GQ-132": "List all knowledge bases endpoint",
    "GQ-149": "Search documents by content mode",
}


def corpus_path(repo_root: Path | None = None) -> Path:
    root = repo_root or Path(__file__).resolve().parents[3]
    return root / CORPUS_REL


def load_corpus_payload(repo_root: Path | None = None) -> dict[str, Any]:
    path = corpus_path(repo_root)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != CORPUS_SCHEMA:
        raise ValueError(f"unexpected corpus schema: {payload.get('schema_version')}")
    return payload


def _family_for(case_id: str) -> FailureFamily:
    if case_id == FAMILY_S_CASE:
        return FailureFamily.S_TOOL_SELECTION
    if case_id in FAMILY_T_CASES:
        return FailureFamily.T_POST_OBS_TERMINATION
    raise ValueError(f"unknown case_id for P3 corpus: {case_id}")


def _reason_code(capture: dict[str, Any]) -> str | None:
    decision = capture.get("planner_decision")
    if isinstance(decision, dict):
        rc = decision.get("reason_code")
        return str(rc) if rc is not None else None
    return None


def _build_steps(
    outcome_steps: list[dict[str, Any]],
    captures: list[dict[str, Any]],
) -> tuple[TraceStep, ...]:
    by_index: dict[int, dict[str, Any]] = {}
    for cap in captures:
        idx = int(cap.get("step_index", -1))
        by_index[idx] = cap

    steps: list[TraceStep] = []
    for raw in outcome_steps:
        step_index = int(raw["step_index"])
        # Captures in P2 report use 0-based step_index; outcome steps are 1-based.
        cap = by_index.get(step_index - 1) or by_index.get(step_index) or {}
        obs = raw.get("observation")
        obs_dict = obs if isinstance(obs, dict) else None
        args = raw.get("args") if isinstance(raw.get("args"), dict) else {}
        steps.append(
            TraceStep(
                step_index=step_index,
                tool_name=raw.get("tool_name"),
                args=dict(args),
                ok=bool(raw.get("ok")),
                observation=obs_dict,
                observation_summary=cap.get("observation_summary") or raw.get("summary"),
                parsed_action=cap.get("parsed_action"),
                reason_code=_reason_code(cap),
                raw_excerpt=cap.get("raw_excerpt"),
                stop_effect=cap.get("stop_effect"),
            )
        )
    return tuple(steps)


def reconstruct_trials(repo_root: Path | None = None) -> tuple[FailureTrial, ...]:
    payload = load_corpus_payload(repo_root)
    trials_raw = payload.get("trials") or []
    if len(trials_raw) != TARGET_TRIAL_COUNT:
        raise ValueError(f"expected {TARGET_TRIAL_COUNT} trials, got {len(trials_raw)}")

    out: list[FailureTrial] = []
    for row in trials_raw:
        case_id = str(row["case_id"])
        traj = row.get("trajectory") or {}
        steps = _build_steps(list(row.get("outcome_steps") or []), list(row.get("captures") or []))
        out.append(
            FailureTrial(
                case_id=case_id,
                trial_index=int(row["trial_index"]),
                panel=str(row.get("panel") or ""),
                family=_family_for(case_id),
                failure_taxonomy=str(row.get("failure_taxonomy") or ""),
                first_failed_stage=str(row.get("first_failed_stage") or ""),
                expected_tool=_EXPECTED_TOOL[case_id],
                query=_QUERIES[case_id],
                steps=steps,
                budget_exhausted=bool(traj.get("budget_exhausted")),
                terminal_action=traj.get("terminal_action"),
                safe=bool(traj.get("safe")),
            )
        )
    return tuple(out)


def first_tool_name(trial: FailureTrial) -> str | None:
    if not trial.steps:
        return None
    return trial.steps[0].tool_name


def first_satisfying_step(trial: FailureTrial) -> TraceStep | None:
    for step in trial.steps:
        if not step.ok or not step.tool_name:
            continue
        ok, _ = observation_satisfies_contract(step.tool_name, step.observation)
        if ok:
            return step
    return None


def assert_corpus_integrity(trials: tuple[FailureTrial, ...] | None = None) -> None:
    trials = trials or reconstruct_trials()
    assert len(trials) == TARGET_TRIAL_COUNT
    by_case: dict[str, int] = {}
    for trial in trials:
        by_case[trial.case_id] = by_case.get(trial.case_id, 0) + 1
        assert trial.budget_exhausted is True
        assert trial.terminal_action is None
        assert trial.safe is False
        if trial.family == FailureFamily.S_TOOL_SELECTION:
            assert first_tool_name(trial) == "semantic_search"
            assert trial.expected_tool == "search_documents"
            assert trial.failure_taxonomy == "WRONG_OR_MISSING_TOOL"
        else:
            assert first_tool_name(trial) == trial.expected_tool
            assert trial.failure_taxonomy == "BUDGET_EXHAUSTED"
            assert first_satisfying_step(trial) is not None
    assert by_case == {"GQ-131": 5, "GQ-132": 5, "GQ-149": 5}
