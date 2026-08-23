"""Family T offline termination candidates (T0–T6) — eval-only."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.eval.tool_capability.observation import observation_satisfies_contract
from app.eval.tool_remediation_ablation.models import TerminationSample, Verdict


def _obs_complete(sample: TerminationSample) -> bool:
    if not sample.obs_contract_ok:
        return False
    ok, _ = observation_satisfies_contract(sample.tool_name, sample.observation)
    return ok


def apply_t0(sample: TerminationSample) -> str:
    """Baseline: keep re-tooling (frozen behavior)."""
    return "tool"


def apply_t1(sample: TerminationSample) -> str:
    """Obs-complete signal → finish when tool-native contract satisfied."""
    if _obs_complete(sample):
        return "finish"
    return "tool"


_CONTRACT_NATIVE_TOOLS = frozenset({"list_knowledge_bases", "search_documents"})


def t2_task_contract_satisfied_hint(sample: TerminationSample) -> str | None:
    """Advisory task_contract_satisfied signal (freeze T2).

    Returns 'finish' hint only when tool-native evaluator/contract predicate proves
    satisfaction for a task_contract_target. This is NOT force_finish: planner still
    chooses the legal terminal. Offline apply uses the hint as a recovery proxy.
    """
    if sample.intent_class == "task_contract_target" and _obs_complete(sample):
        return "finish"
    return None


def apply_t2(sample: TerminationSample) -> str:
    """Offline proxy: follow advisory task_contract_satisfied hint when present."""
    hint = t2_task_contract_satisfied_hint(sample)
    if hint == "finish":
        return "finish"
    return "tool"


def apply_t3(sample: TerminationSample) -> str:
    """Repeat-success detector: prior success with same tool + obs ok → finish."""
    if (
        sample.prior_success_count >= 1
        and _obs_complete(sample)
        and sample.tool_name in _CONTRACT_NATIVE_TOOLS
        and sample.intent_class == "task_contract_target"
    ):
        return "finish"
    return "tool"


def apply_t4(sample: TerminationSample) -> str:
    """Budget-aware nudge: low remaining steps + obs ok → finish."""
    remaining = sample.max_steps - sample.steps_used
    if (
        remaining <= 2
        and _obs_complete(sample)
        and sample.intent_class == "task_contract_target"
    ):
        return "finish"
    return "tool"


def apply_t5(sample: TerminationSample) -> str:
    """Deterministic terminal guard IF tool-native contract proves complete."""
    if sample.tool_name not in _CONTRACT_NATIVE_TOOLS:
        return "tool"
    if not _obs_complete(sample):
        return "tool"
    # Require explicit task-contract eligibility — not any OK observation.
    if sample.intent_class == "task_contract_target":
        return "finish"
    return "tool"


def apply_t6(sample: TerminationSample) -> str:
    """StopPolicy diagnostic only — does not rewrite action offline."""
    return "tool"


T_CANDIDATES: dict[str, Callable[[TerminationSample], str]] = {
    "T0": apply_t0,
    "T1": apply_t1,
    "T2": apply_t2,
    "T3": apply_t3,
    "T4": apply_t4,
    "T5": apply_t5,
    "T6": apply_t6,
}

T_META: dict[str, dict[str, Any]] = {
    "T0": {
        "label": "baseline",
        "complexity": "none",
        "scope_expansion": False,
        "deterministic": True,
        "safety_risk": "none",
        "rationale": "Frozen loop continues until budget exhaustion.",
    },
    "T1": {
        "label": "obs_complete_signal",
        "complexity": "low",
        "scope_expansion": False,
        "deterministic": True,
        "safety_risk": "medium_premature_finish",
        "rationale": "Surfaces obs-complete signal; offline proxy finishes when contract ok.",
    },
    "T2": {
        "label": "task_contract_satisfied_hint",
        "complexity": "low",
        "scope_expansion": False,
        "deterministic": False,  # advisory hint; not force_finish
        "force_finish": False,
        "product_mode": "advisory_task_contract_satisfied_hint",
        "safety_risk": "low",
        "rationale": (
            "Advisory task_contract_satisfied when tool-native contract proves satisfaction; "
            "NOT force_finish — planner still chooses legal terminal."
        ),
    },
    "T3": {
        "label": "repeat_success_detector",
        "complexity": "low",
        "scope_expansion": False,
        "deterministic": True,
        "safety_risk": "low",
        "rationale": "After a prior successful satisfying call, stop re-tooling.",
    },
    "T4": {
        "label": "budget_aware_nudge",
        "complexity": "low",
        "scope_expansion": False,
        "deterministic": True,
        "safety_risk": "medium_late_only",
        "rationale": "When budget nearly exhausted and obs ok, nudge finish.",
    },
    "T5": {
        "label": "deterministic_terminal_guard",
        "complexity": "medium",
        "scope_expansion": False,
        "deterministic": True,
        "safety_risk": "medium_if_matcher_loose",
        "rationale": (
            "Force finish only when tool-native observation contract proves complete "
            "for the target task — still must respect hard negatives."
        ),
    },
    "T6": {
        "label": "stop_policy_diagnostic",
        "complexity": "high",
        "scope_expansion": True,
        "deterministic": True,
        "safety_risk": "high_fact_coverage_coupling",
        "rationale": (
            "StopPolicy/fact-coverage path is orthogonal and product-coupled; "
            "diagnostic only — does not recover Family T offline."
        ),
    },
}


def _is_regression(sample: TerminationSample, chosen: str) -> bool:
    """Hard-negative regression: finish when must not, or non-finish when must finish."""
    if sample.expected_action == "finish":
        return chosen != "finish"
    # For non-finish expectations, finishing is the false behavior.
    if chosen == "finish" and sample.expected_action != "finish":
        return True
    return False


def score_termination_candidate(
    candidate_id: str,
    targets: list[TerminationSample],
    hard_negatives: list[TerminationSample],
) -> dict[str, Any]:
    fn = T_CANDIDATES[candidate_id]
    meta = T_META[candidate_id]
    details: list[dict[str, Any]] = []
    recovered = 0
    for sample in targets:
        chosen = fn(sample)
        ok = chosen == "finish"
        if ok:
            recovered += 1
        details.append(
            {
                "sample_id": sample.sample_id,
                "source": sample.source,
                "chosen": chosen,
                "expected": sample.expected_action,
                "recovered": ok,
            }
        )

    regressions = 0
    false_behavior = 0
    for sample in hard_negatives:
        chosen = fn(sample)
        bad = _is_regression(sample, chosen)
        if bad:
            regressions += 1
            if chosen == "finish" and sample.expected_action != "finish":
                false_behavior += 1
        details.append(
            {
                "sample_id": sample.sample_id,
                "source": sample.source,
                "intent_class": sample.intent_class,
                "chosen": chosen,
                "expected": sample.expected_action,
                "regression": bad,
            }
        )

    if candidate_id == "T0":
        verdict = Verdict.REJECT
    elif candidate_id == "T6":
        verdict = Verdict.DIAGNOSTIC_ONLY
    elif recovered == 0:
        verdict = Verdict.REJECT
    elif regressions > 0:
        verdict = Verdict.REJECT
    elif meta["scope_expansion"]:
        verdict = Verdict.DIAGNOSTIC_ONLY
    else:
        verdict = Verdict.ACCEPT

    return {
        "candidate_id": candidate_id,
        "family": "T",
        "target_count": len(targets),
        "target_recovered": recovered,
        "hard_negative_count": len(hard_negatives),
        "hard_negative_regressions": regressions,
        "new_false_behavior": false_behavior,
        "safety_risk": meta["safety_risk"],
        "scope_expansion": meta["scope_expansion"],
        "deterministic": meta["deterministic"],
        "complexity": meta["complexity"],
        "verdict": verdict,
        "rationale": meta["rationale"],
        "details": details,
        "label": meta["label"],
    }
