"""W8 P1 / Gate C — Evidence integrity characterization schema (eval-only)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any

SCHEMA_VERSION = "1.0.0"

# Product EvidenceRelation / FactStatus are the runtime truth.
# Eval labels below are characterization ground-truth only.


class EvalRelation(str, Enum):
    """Ground-truth support relation (eval-only; not a product enum)."""

    support = "support"
    partial = "partial"
    contradict = "contradict"
    irrelevant = "irrelevant"


class FailureTaxonomy(str, Enum):
    LEXICAL_OVERLAP_FALSE_POSITIVE = "LEXICAL_OVERLAP_FALSE_POSITIVE"
    VALUE_MISMATCH_FALSE_POSITIVE = "VALUE_MISMATCH_FALSE_POSITIVE"
    NEGATION_FALSE_POSITIVE = "NEGATION_FALSE_POSITIVE"
    ENTITY_MISMATCH_FALSE_POSITIVE = "ENTITY_MISMATCH_FALSE_POSITIVE"
    TEMPORAL_MISMATCH_FALSE_POSITIVE = "TEMPORAL_MISMATCH_FALSE_POSITIVE"
    SCOPE_MISMATCH_FALSE_POSITIVE = "SCOPE_MISMATCH_FALSE_POSITIVE"
    PARTIAL_AS_FULL_FALSE_POSITIVE = "PARTIAL_AS_FULL_FALSE_POSITIVE"
    DISTRACTOR_FALSE_POSITIVE = "DISTRACTOR_FALSE_POSITIVE"
    SEMANTIC_PARAPHRASE_FALSE_NEGATIVE = "SEMANTIC_PARAPHRASE_FALSE_NEGATIVE"
    CONTRADICTION_MISCLASSIFIED = "CONTRADICTION_MISCLASSIFIED"
    NONE = "NONE"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class IntegrityCase:
    case_id: str
    category: str  # A..L + f2_repro
    fact_goal: str
    evidence_texts: tuple[str, ...]
    expected_relation: EvalRelation
    acceptable_relations: tuple[EvalRelation, ...] = ()
    reason: str = ""
    # Optional second fact for multi-goal / conflict scenarios
    secondary_fact_goal: str | None = None
    secondary_expected: EvalRelation | None = None
    # If True, case is the W8 F2 historical reproduction
    is_f2_repro: bool = False
    # Expect StopPolicy facts_covered after matcher (unsafe if expected != support)
    check_stop_propagation: bool = False
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "category": self.category,
            "fact_goal": self.fact_goal,
            "evidence_texts": list(self.evidence_texts),
            "expected_relation": self.expected_relation.value,
            "acceptable_relations": [r.value for r in self.acceptable_relations],
            "reason": self.reason,
            "secondary_fact_goal": self.secondary_fact_goal,
            "secondary_expected": (
                self.secondary_expected.value if self.secondary_expected else None
            ),
            "is_f2_repro": self.is_f2_repro,
            "check_stop_propagation": self.check_stop_propagation,
            "notes": self.notes,
        }


@dataclass(slots=True)
class CaseResult:
    case_id: str
    category: str
    expected_relation: str
    actual_relation: str  # mapped eval label from product matcher
    product_relation: str | None  # EvidenceRelation value or None
    fact_status_before: str
    fact_status_after: str
    overlap_score: float | None
    support_threshold: float
    partial_threshold: float
    threshold_band: str  # above_support | near_support | partial_band | below | no_score
    matched: bool  # actual in {expected} ∪ acceptable
    coverage_false_positive: bool
    false_positive: bool
    false_negative: bool
    true_positive: bool
    true_negative: bool
    contradiction_correct: bool
    partial_correct: bool
    unsafe_finish_enabling: bool
    stop_kind: str | None
    stop_reason: str | None
    failure_taxonomy: str
    root_cause_layer: str  # MATCHER / LEDGER / STOP / NONE / UNKNOWN
    evidence_excerpt: str
    notes: str = ""
    extras: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        return payload


@dataclass(slots=True)
class SuiteMetrics:
    case_count: int
    true_positive: int
    true_negative: int
    false_positive: int
    false_negative: int
    contradiction_correct: int
    partial_correct: int
    precision: float
    recall: float
    false_positive_rate: float
    false_negative_rate: float
    coverage_false_positive_rate: float
    unsafe_finish_enabling_fp_rate: float
    coverage_false_positive_count: int
    unsafe_finish_enabling_count: int
    by_category: dict[str, dict[str, Any]] = field(default_factory=dict)
    failure_taxonomy_counts: dict[str, int] = field(default_factory=dict)
    f2_reproduced: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
