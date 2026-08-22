"""Frozen Golden contract semantics shared across W8 P6 categories."""

from __future__ import annotations

ADVERSARIAL_FORMAL_CONTRACT: dict[str, object] = {
    "expected_chunk_meaning": (
        "No document-grounded citation/excerpt should be emitted. "
        "Empty expected_chunk does NOT forbid retrieval attempts, "
        "mandatory refuse, or require no-hit retrieval."
    ),
    "pytest_semantics": (
        "No citation events with non-empty excerpt content."
    ),
    "w8_scorer_semantics": (
        "Task success when collected retrieval excerpts (from tool step data hits) "
        "are empty. Retrieval without excerpt in step data may still pass."
    ),
    "does_not_require": [
        "mandatory_refuse",
        "no_retrieval_attempt",
        "no_tool_calls",
        "no_hit_retrieval",
    ],
    "original_pass_w8_p5": "1/20",
    "original_metric_validity": "INVALID_FOR_CAPABILITY",
}

TOOL_ORIGINAL_SCORE: dict[str, object] = {
    "pass_count": 2,
    "total": 20,
    "pass_rate": 0.1,
    "capability_validity": "INVALID_FOR_CAPABILITY",
    "reason": (
        "Legacy scorer checks terminal_decision && !timed_out only; "
        "does not validate expected OpenAPI path / HTTP status in observations."
    ),
}

MEMORY_ORIGINAL_SCORE: dict[str, object] = {
    "pass_count": 2,
    "total": 4,
    "pass_rate": 0.5,
    "l1_l3_validity": "PARTIALLY_VALID",
    "l4_l5_capability_validity": "INVALID_FOR_CAPABILITY",
    "reason": (
        "Pipeline completion signal only; does not measure memory utilization "
        "or semantic task benefit. No memory tool exists — prompt injection only."
    ),
}

W8_P5_POSITIVE_CONTROL_CASE_IDS: tuple[str, ...] = (
    "GQ-8",
    "GQ-16",
    "GQ-41",
    "GQ-44",
)

# BGE retrieval-validity probe: 4 RAG + 4 RETRIEVAL (includes P5 controls; frozen before probe).
W8_P6_BGE_POSITIVE_RAG_CASE_IDS: tuple[str, ...] = (
    "GQ-1",
    "GQ-2",
    "GQ-8",
    "GQ-16",
)
W8_P6_BGE_POSITIVE_RETRIEVAL_CASE_IDS: tuple[str, ...] = (
    "GQ-41",
    "GQ-42",
    "GQ-43",
    "GQ-44",
)

W8_P5_ADVERSARIAL_CASE_IDS: tuple[str, ...] = tuple(
    f"GQ-{n}" for n in range(91, 111)
)

BGE_PROBE_QUERY_GROUP_COUNT: int = (
    len(W8_P5_ADVERSARIAL_CASE_IDS)
    + len(W8_P6_BGE_POSITIVE_RAG_CASE_IDS)
    + len(W8_P6_BGE_POSITIVE_RETRIEVAL_CASE_IDS)
)
