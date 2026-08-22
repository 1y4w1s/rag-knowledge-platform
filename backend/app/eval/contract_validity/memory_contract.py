"""MEMORY Golden contract measurability — seeded vs empty case semantics."""

from __future__ import annotations

from app.eval.contract_validity.models import (
    FORBIDDEN_MEMORY_TAXONOMY,
    MeasurementLayer,
    MemoryCaseKind,
    MemoryContractRecord,
    MemoryTaxonomy,
    Validity,
)

_SEEDED_TAXONOMY: tuple[str, ...] = tuple(
    t.value
    for t in MemoryTaxonomy
    if t.value not in FORBIDDEN_MEMORY_TAXONOMY
)

_EMPTY_TAXONOMY: tuple[str, ...] = (
    MemoryTaxonomy.EMPTY_MEMORY_SAFE_BEHAVIOR.value,
    MemoryTaxonomy.EMPTY_MEMORY_UNPRODUCTIVE_LOOP.value,
    MemoryTaxonomy.MEMORY_NOT_EXPOSED.value,
    MemoryTaxonomy.UNKNOWN.value,
)

_SEEDED_LAYERS: dict[str, Validity] = {
    MeasurementLayer.L1_SEEDING.value: Validity.PARTIALLY_VALID,
    MeasurementLayer.L2_LOADING.value: Validity.PARTIALLY_VALID,
    MeasurementLayer.L3_EXPOSURE.value: Validity.PARTIALLY_VALID,
    MeasurementLayer.L4_UTILIZATION.value: Validity.INVALID_FOR_CAPABILITY,
    MeasurementLayer.L5_TASK_SUCCESS.value: Validity.INVALID_FOR_CAPABILITY,
}

_EMPTY_LAYERS: dict[str, Validity] = {
    MeasurementLayer.L1_SEEDING.value: Validity.VALID_MEASUREMENT,
    MeasurementLayer.L2_LOADING.value: Validity.VALID_MEASUREMENT,
    MeasurementLayer.L3_EXPOSURE.value: Validity.VALID_MEASUREMENT,
    MeasurementLayer.L4_UTILIZATION.value: Validity.UNIT_ONLY,
    MeasurementLayer.L5_TASK_SUCCESS.value: Validity.INVALID_FOR_CAPABILITY,
    MeasurementLayer.EMPTY_MEMORY_BEHAVIOR.value: Validity.PARTIALLY_VALID,
}

_MEMORY_CASES: tuple[MemoryContractRecord, ...] = (
    MemoryContractRecord(
        case_id="GA-9",
        case_kind=MemoryCaseKind.SEEDED_MEMORY_CASE,
        pre_seed_count=1,
        expected_chunk_marker="memory_loaded",
        layer_validity=dict(_SEEDED_LAYERS),
        l4_utilization_applicable=True,
        measurement_targets=(
            "planner_or_final_uses_target_memory_semantic_content",
            "not_prompt_text_presence_only",
        ),
        allowed_taxonomy=_SEEDED_TAXONOMY,
        capability_measurable=False,
        reason=(
            "Seeded preference memory exposed via prompt injection; "
            "L4 utilization requires semantic use not mere visibility."
        ),
    ),
    MemoryContractRecord(
        case_id="GA-10",
        case_kind=MemoryCaseKind.SEEDED_MEMORY_CASE,
        pre_seed_count=2,
        expected_chunk_marker="memory_loaded",
        layer_validity=dict(_SEEDED_LAYERS),
        l4_utilization_applicable=True,
        measurement_targets=(
            "planner_or_final_uses_target_memory_semantic_content",
            "topic_preference_influences_retrieval_or_answer",
        ),
        allowed_taxonomy=_SEEDED_TAXONOMY,
        capability_measurable=False,
        reason="Dual seeded preferences; utilization not measured by legacy scorer.",
    ),
    MemoryContractRecord(
        case_id="GA-11",
        case_kind=MemoryCaseKind.EMPTY_MEMORY_CASE,
        pre_seed_count=0,
        expected_chunk_marker="memory_empty",
        layer_validity=dict(_EMPTY_LAYERS),
        l4_utilization_applicable=False,
        measurement_targets=(
            "no_fabricated_memory",
            "reasonable_retrieval_or_clarify",
            "no_unproductive_loop",
            "safe_termination",
        ),
        allowed_taxonomy=_EMPTY_TAXONOMY,
        capability_measurable=False,
        reason="Empty by design; evaluate EMPTY_MEMORY_BEHAVIOR not utilization failure.",
    ),
    MemoryContractRecord(
        case_id="GA-12",
        case_kind=MemoryCaseKind.EMPTY_MEMORY_CASE,
        pre_seed_count=0,
        expected_chunk_marker="memory_empty",
        layer_validity=dict(_EMPTY_LAYERS),
        l4_utilization_applicable=False,
        measurement_targets=(
            "no_fabricated_memory",
            "reasonable_retrieval_or_clarify",
            "no_unproductive_loop",
            "safe_termination",
        ),
        allowed_taxonomy=_EMPTY_TAXONOMY,
        capability_measurable=False,
        reason="Empty memory context case; L4 utilization is N/A.",
    ),
)

MEMORY_CASE_BY_ID: dict[str, MemoryContractRecord] = {c.case_id: c for c in _MEMORY_CASES}


def memory_contract_records() -> tuple[MemoryContractRecord, ...]:
    return _MEMORY_CASES
