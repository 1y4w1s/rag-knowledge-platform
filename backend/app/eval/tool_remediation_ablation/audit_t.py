"""Family T audit — classify T-A..T-F from frozen traces."""

from __future__ import annotations

from typing import Any

from app.eval.tool_capability.observation import observation_satisfies_contract
from app.eval.tool_remediation_ablation.corpus import first_satisfying_step, reconstruct_trials
from app.eval.tool_remediation_ablation.models import (
    FAMILY_T_CASES,
    FailureFamily,
    FailureTrial,
    TSubtype,
)


def _args_equal(a: dict[str, Any], b: dict[str, Any]) -> bool:
    return dict(a or {}) == dict(b or {})


def classify_trial_t(trial: FailureTrial) -> list[TSubtype]:
    """Classify one Family T trial into one or more T subtypes."""
    assert trial.family == FailureFamily.T_POST_OBS_TERMINATION
    labels: list[TSubtype] = []

    first_ok = first_satisfying_step(trial)
    if first_ok is None:
        # Usable obs never appeared — would be evidence-gate territory; not seen in P2.
        labels.append(TSubtype.T_B_EVIDENCE_GATE_CORRECT)
        return labels

    # After a satisfying observation, did the agent ever finish/refuse/clarify?
    terminal_seen = any(
        (s.parsed_action or "").lower() in {"finish", "refuse", "clarify"}
        for s in trial.steps
    )
    if not terminal_seen and trial.terminal_action is None:
        labels.append(TSubtype.T_A_TERMINATION_REASONING)

    # Identical success repeats after first satisfying step
    identical = 0
    mutated = 0
    for step in trial.steps:
        if step.step_index <= first_ok.step_index:
            continue
        if step.tool_name != first_ok.tool_name or not step.ok:
            continue
        if _args_equal(step.args, first_ok.args):
            identical += 1
        else:
            mutated += 1
    if identical > 0:
        labels.append(TSubtype.T_C_IDENTICAL_SUCCESS_REPEAT)
    if mutated > 0:
        labels.append(TSubtype.T_D_MUTATED_ARGS_AFTER_SUCCESS)

    if trial.budget_exhausted and trial.terminal_action is None:
        labels.append(TSubtype.T_E_BUDGET_LOOP)

    wrong_terminal = (trial.terminal_action or "").lower() in {"clarify", "refuse"}
    if wrong_terminal:
        labels.append(TSubtype.T_F_WRONG_TERMINAL)

    # Evidence-gate correctly blocking? Only if obs contract fails OR explicit gate.
    # P2 traces: first satisfying obs exists and stop_effect stays passthrough → NOT T-B.
    obs_ok, _ = observation_satisfies_contract(first_ok.tool_name or "", first_ok.observation)
    if not obs_ok:
        labels.append(TSubtype.T_B_EVIDENCE_GATE_CORRECT)

    return labels


def critical_distinction(trial: FailureTrial) -> dict[str, Any]:
    first_ok = first_satisfying_step(trial)
    if first_ok is None:
        return {
            "kind": "EVIDENCE_GATE_OR_NO_USABLE_OBS",
            "termination_reasoning_failure": False,
            "evidence_gate_blocking": True,
        }
    obs_ok, reason = observation_satisfies_contract(
        first_ok.tool_name or "", first_ok.observation
    )
    return {
        "kind": "TERMINATION_REASONING_FAILURE",
        "termination_reasoning_failure": True,
        "evidence_gate_blocking": False,
        "first_satisfying_step": first_ok.step_index,
        "obs_contract_ok": obs_ok,
        "obs_contract_reason": reason,
        "tool_name": first_ok.tool_name,
        "note": (
            "Tool-native observation contract already satisfied; model kept choosing "
            "tool (reason_code often initial_retrieval) until budget exhaustion."
        ),
    }


def audit_family_t(trials: tuple[FailureTrial, ...] | None = None) -> dict[str, Any]:
    trials = trials or reconstruct_trials()
    t_trials = [t for t in trials if t.family == FailureFamily.T_POST_OBS_TERMINATION]
    assert len(t_trials) == 10
    assert {t.case_id for t in t_trials} == set(FAMILY_T_CASES)

    subtype_counts: dict[str, int] = {s.value: 0 for s in TSubtype}
    per_trial: list[dict[str, Any]] = []
    for trial in t_trials:
        labels = classify_trial_t(trial)
        for label in labels:
            subtype_counts[label.value] += 1
        per_trial.append(
            {
                "case_id": trial.case_id,
                "trial_index": trial.trial_index,
                "subtypes": [s.value for s in labels],
                "distinction": critical_distinction(trial),
            }
        )

    root = (
        "POST_OBSERVATION_TERMINATION_FAILURE / BUDGET_EXHAUSTION: correct tool+args and "
        "usable tool-native observation appear early, but NextAction keeps re-selecting "
        "tool (identical or lightly mutated) with no finish — termination reasoning "
        "failure, not evidence gate correctly blocking finish."
    )
    return {
        "family": FailureFamily.T_POST_OBS_TERMINATION.value,
        "trials": 10,
        "cases": sorted(FAMILY_T_CASES),
        "root_cause": root,
        "subtype_counts": subtype_counts,
        "per_trial": per_trial,
        "critical_distinction": (
            "termination_reasoning_failure vs evidence_gate_correctly_blocking — "
            "P2 Family T is the former (obs contract satisfied; no safe terminal)."
        ),
    }
