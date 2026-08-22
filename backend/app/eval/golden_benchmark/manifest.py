"""Fixed W8 P4 timing-validation case selection (frozen before run)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from tests.golden_agent_qa_loader import AgentGoldenCase

# Frozen selection: first N per category from W8 P3 manifest order (20260822 subset).
W8_P4_TIMING_VALIDATION_CASE_IDS: tuple[str, ...] = (
    "GQ-8",
    "GQ-16",  # RAG ×2
    "GQ-41",
    "GQ-44",  # RETRIEVAL ×2
    "GA-1",  # MULTI_STEP ×1
    "GA-13",  # AUTH ×1
    "GA-9",  # MEMORY ×1
    "GQ-92",  # ADVERSARIAL ×1
    "GQ-135",  # TOOL ×1 (first TOOL in W8 P3 manifest order)
)

W8_P4_CATEGORY_QUOTAS: dict[str, int] = {
    "RAG": 2,
    "RETRIEVAL": 2,
    "MULTI_STEP": 1,
    "AUTH": 1,
    "MEMORY": 1,
    "ADVERSARIAL": 1,
    "TOOL": 1,
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def build_timing_validation_manifest(
    cases_by_id: dict[str, AgentGoldenCase],
    *,
    source_manifest_path: str | None = None,
) -> dict[str, Any]:
    """Build frozen 9-case timing validation manifest."""
    selected: list[AgentGoldenCase] = []
    for case_id in W8_P4_TIMING_VALIDATION_CASE_IDS:
        if case_id not in cases_by_id:
            raise KeyError(f"timing validation case missing from golden loader: {case_id}")
        selected.append(cases_by_id[case_id])

    cat_counts: dict[str, int] = {}
    for case in selected:
        cat_counts[case.category] = cat_counts.get(case.category, 0) + 1

    return {
        "schema_version": "w8-p4-timing-validation-v1",
        "generated_at": _utc_now(),
        "selection_method": "w8_p3_manifest_first_n_per_category",
        "source_w8_p3_manifest": source_manifest_path,
        "category_quotas": W8_P4_CATEGORY_QUOTAS,
        "case_count": len(selected),
        "case_ids": list(W8_P4_TIMING_VALIDATION_CASE_IDS),
        "category_counts": dict(sorted(cat_counts.items())),
        "cases": [
            {
                "case_id": c.case_id,
                "category": c.category,
                "query": c.query,
                "expected_doc": c.expected_doc,
                "expected_chunk": c.expected_chunk,
                "scope": c.scope,
                "expected_steps": c.expected_steps,
            }
            for c in selected
        ],
    }
