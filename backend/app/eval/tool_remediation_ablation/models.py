"""TOOL P3 offline remediation ablation — dataclasses (eval-only)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


P2_LINEAGE_SHA = "ba5837bed3a1828363871c2f3c2dd92fd761bbec"
P2_FREEZE_HEAD = "8e6e133"
STAGE = "TOOL_P3_OFFLINE_REMEDIATION_ABLATION"
CORPUS_SCHEMA = "tool-p3-failure-corpus-v1"

FAMILY_S_CASE = "GQ-131"
FAMILY_T_CASES = frozenset({"GQ-132", "GQ-149"})
TARGET_TRIAL_COUNT = 15


class FailureFamily(str, Enum):
    S_TOOL_SELECTION = "TOOL_SELECTION_FAILURE"
    T_POST_OBS_TERMINATION = "POST_OBSERVATION_TERMINATION_FAILURE"


class Verdict(str, Enum):
    ACCEPT = "ACCEPT"
    REJECT = "REJECT"
    DIAGNOSTIC_ONLY = "DIAGNOSTIC_ONLY"


class TSubtype(str, Enum):
    """Family T audit classes (trace-derived)."""

    T_A_TERMINATION_REASONING = "T-A_TERMINATION_REASONING_FAILURE"
    T_B_EVIDENCE_GATE_CORRECT = "T-B_EVIDENCE_GATE_CORRECTLY_BLOCKING"
    T_C_IDENTICAL_SUCCESS_REPEAT = "T-C_IDENTICAL_SUCCESS_REPEAT"
    T_D_MUTATED_ARGS_AFTER_SUCCESS = "T-D_MUTATED_ARGS_AFTER_SUCCESS"
    T_E_BUDGET_LOOP = "T-E_BUDGET_AWARE_LOOP_TO_EXHAUSTION"
    T_F_WRONG_TERMINAL = "T-F_WRONG_TERMINAL_PREFERENCE"


@dataclass(frozen=True, slots=True)
class TraceStep:
    step_index: int
    tool_name: str | None
    args: dict[str, Any]
    ok: bool
    observation: dict[str, Any] | None
    observation_summary: str | None
    parsed_action: str | None
    reason_code: str | None
    raw_excerpt: str | None
    stop_effect: str | None


@dataclass(frozen=True, slots=True)
class FailureTrial:
    case_id: str
    trial_index: int
    panel: str
    family: FailureFamily
    failure_taxonomy: str
    first_failed_stage: str
    expected_tool: str
    query: str
    steps: tuple[TraceStep, ...]
    budget_exhausted: bool
    terminal_action: str | None
    safe: bool


@dataclass(frozen=True, slots=True)
class SelectionSample:
    """One offline selection decision (target or hard-negative)."""

    sample_id: str
    source: str  # TARGET | HARD_NEGATIVE
    case_id: str | None
    trial_index: int | None
    query: str
    exposed_tools: tuple[str, ...]
    selected_tool: str
    expected_tool: str | None
    must_not_force_tool: str | None
    intent_class: str  # catalog_search | semantic_qa | ambiguous | oos | multi_step
    notes: str = ""


@dataclass(frozen=True, slots=True)
class TerminationSample:
    """One offline post-observation decision point."""

    sample_id: str
    source: str  # TARGET | HARD_NEGATIVE
    case_id: str | None
    trial_index: int | None
    step_index: int
    tool_name: str
    args: dict[str, Any]
    observation: dict[str, Any] | None
    obs_contract_ok: bool
    expected_action: str  # finish | tool | refuse | clarify
    intent_class: str
    prior_success_count: int
    steps_used: int
    max_steps: int
    notes: str = ""


@dataclass(slots=True)
class CandidateScore:
    candidate_id: str
    family: str
    target_count: int = 0
    target_recovered: int = 0
    hard_negative_count: int = 0
    hard_negative_regressions: int = 0
    new_false_behavior: int = 0
    safety_risk: str = "none"
    scope_expansion: bool = False
    deterministic: bool = True
    complexity: str = "low"
    verdict: Verdict = Verdict.REJECT
    rationale: str = ""
    details: list[dict[str, Any]] = field(default_factory=list)

    @property
    def target_recovery_rate(self) -> float:
        if self.target_count == 0:
            return 0.0
        return self.target_recovered / self.target_count

    @property
    def hard_negative_regression_rate(self) -> float:
        if self.hard_negative_count == 0:
            return 0.0
        return self.hard_negative_regressions / self.hard_negative_count

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "family": self.family,
            "target_count": self.target_count,
            "target_recovered": self.target_recovered,
            "target_recovery_rate": round(self.target_recovery_rate, 4),
            "hard_negative_count": self.hard_negative_count,
            "hard_negative_regressions": self.hard_negative_regressions,
            "hard_negative_regression_rate": round(self.hard_negative_regression_rate, 4),
            "new_false_behavior": self.new_false_behavior,
            "safety_risk": self.safety_risk,
            "scope_expansion": self.scope_expansion,
            "deterministic": self.deterministic,
            "complexity": self.complexity,
            "verdict": self.verdict.value,
            "rationale": self.rationale,
            "details": self.details,
        }


@dataclass(slots=True)
class AblationReport:
    stage: str
    corpus_trials: int
    family_s_root: str
    family_t_root: str
    family_t_subtypes: dict[str, int]
    s_scores: list[CandidateScore]
    t_scores: list[CandidateScore]
    best_s: str | None
    best_t: str | None
    ready_for_product_selection_fix: bool
    ready_for_product_termination_fix: bool
    recommended_next_product_experiments: list[str]
    product_diff: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "corpus_trials": self.corpus_trials,
            "family_s_root": self.family_s_root,
            "family_t_root": self.family_t_root,
            "family_t_subtypes": self.family_t_subtypes,
            "s_candidates": [s.to_dict() for s in self.s_scores],
            "t_candidates": [s.to_dict() for s in self.t_scores],
            "best_s": self.best_s,
            "best_t": self.best_t,
            "ready_for_product_selection_fix": self.ready_for_product_selection_fix,
            "ready_for_product_termination_fix": self.ready_for_product_termination_fix,
            "recommended_next_product_experiments": self.recommended_next_product_experiments,
            "product_diff": self.product_diff,
            "ready_for_product_ablation": (
                self.ready_for_product_selection_fix
                or self.ready_for_product_termination_fix
            ),
        }
