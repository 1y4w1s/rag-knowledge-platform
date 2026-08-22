"""CURRENT_L4_MEMORY_UTILIZATION_CONTRACT — five independent measurement levels."""

from __future__ import annotations

from app.eval.memory_capability.schema import MeasurementLevel

# Each level is independently scored; passing L1 does NOT imply L2, etc.
MEMORY_MEASUREMENT_LEVELS: tuple[MeasurementLevel, ...] = (
    MeasurementLevel.L1_SEEDED,
    MeasurementLevel.L2_LOADED,
    MeasurementLevel.L3_EXPOSED,
    MeasurementLevel.L4_UTILIZED,
    MeasurementLevel.L5_TASK_BENEFIT,
)

LEVEL_DEFINITIONS: dict[str, str] = {
    MeasurementLevel.L1_SEEDED.value: (
        "Pre-run upsert of expected memory rows succeeded (seed count matches intent)."
    ),
    MeasurementLevel.L2_LOADED.value: (
        "load_active_memories returned the expected active rows for the user. "
        "memory_loaded != memory_used."
    ),
    MeasurementLevel.L3_EXPOSED.value: (
        "format_memory_context output was injected into planner prompt / agent state. "
        "Exposure is visibility, not utilization."
    ),
    MeasurementLevel.L4_UTILIZED.value: (
        "Output satisfies structured proposition contracts derived from seeded memory. "
        "Keyword overlap alone is NOT semantic utilization."
    ),
    MeasurementLevel.L5_TASK_BENEFIT.value: (
        "Counterfactual: WITH_MEMORY passes task contract AND WITHOUT_MEMORY fails "
        "the same contract. No benefit if both succeed."
    ),
}

L4_SEMANTIC_UTILIZATION_CONTRACT: dict[str, object] = {
    "method": "structured_proposition_matching",
    "not_accepted": [
        "substring_presence_only",
        "keyword_overlap_without_semantic_binding",
        "prompt_text_echo_without_task_effect",
    ],
    "example": {
        "proposition": {"kind": "language_preference", "expected": "zh-TW"},
        "pass_output": "User prefers Traditional Chinese (繁體中文) for retrieval.",
        "fail_output": "The query mentions zh-TW but answer is in English only.",
        "false_positive": "Output contains 'zh-TW' token but responds in English.",
    },
}

L5_COUNTERFACTUAL_CONTRACT: dict[str, object] = {
    "requires": ["with_memory_trajectory", "without_memory_trajectory"],
    "task_benefit_true_when": (
        "with_memory.task_contract_passed is True "
        "AND without_memory.task_contract_passed is False"
    ),
    "task_benefit_false_when": [
        "both_with_and_without_succeed",
        "with_memory_fails",
        "without_memory_not_evaluated",
    ],
}

# Legacy W8 P5 MEMORY4 score — frozen, not rewritten by this evaluator.
LEGACY_MEMORY4_SCORE: dict[str, object] = {
    "pass_count": 2,
    "total": 4,
    "pass_rate": 0.5,
    "capability_validity": "INVALID_FOR_UTILIZATION_CAPABILITY",
    "capability_score": "NOT_YET_VALID",
    "reason": (
        "Legacy scorer checks pipeline completion (memory_loaded / memory_empty marker) "
        "only; does not measure semantic utilization or counterfactual task benefit."
    ),
}
