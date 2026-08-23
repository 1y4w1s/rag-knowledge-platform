"""Answerability + migration taxonomies for ADVERSARIAL capability measurement."""

from __future__ import annotations

ANSWERABILITY_TAXONOMY: tuple[str, ...] = (
    "ANSWERABLE",
    "UNANSWERABLE_IN_CORPUS",
    "CONFLICTED_EVIDENCE",
    "INSUFFICIENT_EVIDENCE",
    "OUT_OF_SCOPE",
    "UNSAFE_REQUEST",
)

MIGRATION_CLASSES: tuple[str, ...] = (
    "VALID_AS_IS",
    "MIGRATABLE_WITH_CONTRACT",
    "INVALID_CORPUS",
    "INVALID_EXPECTATION",
    "STALE_RUNTIME",
    "UNIT_ONLY",
    "UNSATISFIABLE",
    "OTHER_EXPLICIT",
)

# first_failed_stage order (D7) — evaluate in sequence; first fail wins.
CAPABILITY_STAGES: tuple[str, ...] = (
    "case_answerability_valid",
    "corpus_contract_valid",
    "retrieval_behavior_valid",
    "evidence_state_correct",
    "terminal_decision_correct",
    "unsupported_claim_absent",
    "citation_behavior_correct",
    "safe_outcome",
)

# Empty expected_chunk must NEVER auto-map to refuse.
FORBIDDEN_AUTO_MAPPINGS: tuple[str, ...] = (
    "expected_chunk_empty_implies_refuse",
    "expected_chunk_empty_implies_no_retrieval",
    "expected_chunk_empty_implies_no_hit",
    "mock_always_topk_hit_implies_retriever_false_positive",
    "refusal_equals_task_success",
    "retrieval_occurred_equals_task_failure",
    "legacy_adv20_pass_rate_as_capability_baseline",
)
