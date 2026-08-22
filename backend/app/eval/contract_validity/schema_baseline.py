"""W8 P5 Planner schema baseline freeze (TOOL_NAME_AS_ACTION)."""

from __future__ import annotations

from app.eval.contract_validity.models import (
    SchemaCharacterizationBaseline,
    SchemaFailureSubtype,
)

VALIDATED_MERGED_MASTER_SHA = "5dde0f119483beed74bae649e778a42298848f00"
BENCHMARK_SEMANTICS_SHA = "1b4f28dd988ebdda015018a228859f05bc3c9905"

# Frozen from W8 P5 schema analysis (benchmark checkout 1b4f28d, validated on merged master).
_TOOL_NAME_AS_ACTION_AFFECTED: tuple[str, ...] = (
    "GQ-98",
    "GQ-99",
    "GQ-100",
    "GQ-102",
    "GQ-103",
    "GQ-106",
    "GQ-132",
    "GA-9",
    "GA-10",
)


def schema_characterization_baseline() -> SchemaCharacterizationBaseline:
    total = 226
    failures = 9
    return SchemaCharacterizationBaseline(
        total_decisions=total,
        failure_count=failures,
        failure_rate=failures / total,
        failure_subtypes=(
            SchemaFailureSubtype(
                subtype="TOOL_NAME_AS_ACTION",
                count=9,
                affected_case_ids=_TOOL_NAME_AS_ACTION_AFFECTED,
                step_positions=(),
                raw_output_hashes=(),
            ),
        ),
        source_benchmark="W8_P5",
        benchmark_semantics_sha=BENCHMARK_SEMANTICS_SHA,
        validated_merged_master=VALIDATED_MERGED_MASTER_SHA,
        notes=(
            "Pattern: action='semantic_search' instead of action='tool' + "
            "tool_name='semantic_search'. P5 ran at benchmark_semantics_sha; "
            "product validation SHA is validated_merged_master."
        ),
    )
