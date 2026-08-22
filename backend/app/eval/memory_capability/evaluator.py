"""Deterministic five-level MEMORY utilization evaluator."""

from __future__ import annotations

from app.eval.memory_capability.contract import MEMORY_MEASUREMENT_LEVELS
from app.eval.memory_capability.proposition import (
    analyze_utilization,
    memory_exposed_in_context,
    seeds_equivalent,
)
from app.eval.memory_capability.schema import (
    CaseEvaluation,
    CounterfactualPair,
    LevelResult,
    MeasurementLevel,
    MemoryTrajectoryInput,
    UtilizationAnalysis,
)


def _level(
    level: MeasurementLevel,
    *,
    eligible: bool,
    attempted: bool,
    passed: bool,
    reason: str = "",
) -> LevelResult:
    return LevelResult(
        level=level,
        eligible=eligible,
        attempted=attempted,
        passed=passed,
        reason=reason,
    )


def evaluate_trajectory(trajectory: MemoryTrajectoryInput) -> CaseEvaluation:
    """Evaluate L1-L4 for a single trajectory (L5 requires counterfactual pair)."""
    empty_case = trajectory.empty_memory_case
    l4_applicable = not empty_case and bool(trajectory.seeded_memories)
    levels: list[LevelResult] = []

    # L1 — seeded
    if empty_case:
        l1 = _level(
            MeasurementLevel.L1_SEEDED,
            eligible=True,
            attempted=True,
            passed=trajectory.seed_succeeded and not trajectory.seeded_memories,
            reason="" if not trajectory.seeded_memories else "empty case should not seed",
        )
    else:
        expected_count = len(trajectory.seeded_memories)
        l1_pass = trajectory.seed_succeeded and expected_count > 0
        l1 = _level(
            MeasurementLevel.L1_SEEDED,
            eligible=True,
            attempted=True,
            passed=l1_pass,
            reason="" if l1_pass else "seed failed or missing memories",
        )
    levels.append(l1)

    # L2 — loaded (independent of L1 pass)
    if empty_case:
        l2_pass = len(trajectory.loaded_memories) == 0
        l2 = _level(
            MeasurementLevel.L2_LOADED,
            eligible=True,
            attempted=True,
            passed=l2_pass,
            reason="" if l2_pass else "empty case loaded unexpected memories",
        )
    else:
        l2_attempted = l1.attempted
        l2_pass = seeds_equivalent(trajectory.seeded_memories, trajectory.loaded_memories)
        l2 = _level(
            MeasurementLevel.L2_LOADED,
            eligible=True,
            attempted=l2_attempted,
            passed=bool(l2_attempted and l2_pass),
            reason="" if l2_pass else "loaded set does not match seeded set",
        )
    levels.append(l2)

    # L3 — exposed
    if empty_case:
        l3_pass = trajectory.exposed_context.strip() == ""
        l3 = _level(
            MeasurementLevel.L3_EXPOSED,
            eligible=True,
            attempted=True,
            passed=l3_pass,
            reason="" if l3_pass else "empty memory should not expose context",
        )
    else:
        l3_attempted = l2.attempted
        if not trajectory.loaded_memories and trajectory.seeded_memories:
            exposed = False
            l3_reason = "memories loaded empty but seed expected rows"
        else:
            exposed = memory_exposed_in_context(
                trajectory.exposed_context,
                trajectory.loaded_memories,
            )
            l3_reason = "" if exposed else "memory not present in exposed context"
        l3 = _level(
            MeasurementLevel.L3_EXPOSED,
            eligible=True,
            attempted=l3_attempted,
            passed=bool(l3_attempted and exposed),
            reason=l3_reason,
        )
    levels.append(l3)

    # L4 — semantic utilization
    utilization: UtilizationAnalysis | None = None
    false_utilization = False
    if l4_applicable:
        l4_attempted = l3.attempted and l3.passed
        utilization = analyze_utilization(
            trajectory.seeded_memories,
            trajectory.output_text,
            tool_query=trajectory.tool_query,
        )
        l4_pass = utilization.semantic_utilized and not utilization.contradicted
        false_utilization = utilization.keyword_overlap_only and not l4_pass
        l4 = _level(
            MeasurementLevel.L4_UTILIZED,
            eligible=True,
            attempted=l4_attempted,
            passed=bool(l4_attempted and l4_pass),
            reason=utilization.reason if not l4_pass else "",
        )
    else:
        l4 = _level(
            MeasurementLevel.L4_UTILIZED,
            eligible=False,
            attempted=False,
            passed=False,
            reason="N/A for empty memory case",
        )
    levels.append(l4)

    # L5 placeholder — filled by evaluate_counterfactual
    l5 = _level(
        MeasurementLevel.L5_TASK_BENEFIT,
        eligible=l4_applicable,
        attempted=False,
        passed=False,
        reason="requires counterfactual pair",
    )
    levels.append(l5)

    return CaseEvaluation(
        case_id=trajectory.case_id,
        levels=tuple(levels),
        utilization=utilization,
        false_utilization=false_utilization,
        l4_applicable=l4_applicable,
        l5_applicable=l4_applicable,
    )


def evaluate_counterfactual(pair: CounterfactualPair) -> CaseEvaluation:
    """Evaluate L5 task benefit via WITH vs WITHOUT memory counterfactual."""
    with_eval = evaluate_trajectory(pair.with_memory)

    with_pass = pair.with_memory.task_contract_passed
    without_pass = pair.without_memory.task_contract_passed
    l5_pass = with_pass and not without_pass
    l5_reason = ""
    if not with_pass:
        l5_reason = "with_memory did not satisfy task contract"
    elif without_pass:
        l5_reason = "without_memory also succeeded — no incremental benefit"
    else:
        l5_reason = ""

    l5 = _level(
        MeasurementLevel.L5_TASK_BENEFIT,
        eligible=True,
        attempted=True,
        passed=l5_pass,
        reason=l5_reason,
    )

    levels = list(with_eval.levels[:-1]) + [l5]
    return CaseEvaluation(
        case_id=pair.case_id,
        levels=tuple(levels),
        utilization=with_eval.utilization,
        false_utilization=with_eval.false_utilization,
        l4_applicable=with_eval.l4_applicable,
        l5_applicable=True,
    )


def evaluate_empty_memory_behavior(trajectory: MemoryTrajectoryInput) -> LevelResult:
    """Dedicated empty-memory behavior check (no fabrication + safe termination)."""
    passed = (
        trajectory.empty_memory_case
        and trajectory.no_fabricated_memory
        and trajectory.safe_termination
        and trajectory.exposed_context.strip() == ""
    )
    reason = ""
    if not trajectory.no_fabricated_memory:
        reason = "fabricated memory detected"
    elif not trajectory.safe_termination:
        reason = "unsafe termination"
    elif trajectory.exposed_context.strip():
        reason = "unexpected memory exposure"
    return _level(
        MeasurementLevel.L1_SEEDED,
        eligible=True,
        attempted=True,
        passed=passed,
        reason=reason,
    )


def all_measurement_levels() -> tuple[str, ...]:
    return tuple(level.value for level in MEMORY_MEASUREMENT_LEVELS)
