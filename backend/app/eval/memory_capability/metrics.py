"""Metric aggregation with explicit denominators for MEMORY evaluator."""

from __future__ import annotations

from app.eval.memory_capability.schema import (
    CaseEvaluation,
    LevelResult,
    MeasurementLevel,
    MetricCount,
    SuiteMetrics,
)


def _level_counts(
    evaluations: list[CaseEvaluation],
    level: MeasurementLevel,
) -> MetricCount:
    eligible = sum(
        1
        for ev in evaluations
        if ev.level_map()[level.value].eligible
    )
    attempted = sum(
        1
        for ev in evaluations
        if ev.level_map()[level.value].attempted
    )
    passed = sum(
        1
        for ev in evaluations
        if ev.level_map()[level.value].passed
    )
    return MetricCount(
        metric=level.value,
        eligible=eligible,
        attempted=attempted,
        passed=passed,
    )


def _custom_counts(
    evaluations: list[CaseEvaluation],
    metric: str,
    predicate_eligible,
    predicate_passed,
) -> MetricCount:
    eligible = sum(1 for ev in evaluations if predicate_eligible(ev))
    attempted = eligible
    passed = sum(1 for ev in evaluations if predicate_eligible(ev) and predicate_passed(ev))
    return MetricCount(metric=metric, eligible=eligible, attempted=attempted, passed=passed)


def aggregate_metrics(
    evaluations: list[CaseEvaluation],
    *,
    empty_behavior_results: tuple[LevelResult, ...] = (),
) -> SuiteMetrics:
    n = len(evaluations)
    metrics: list[MetricCount] = [
        MetricCount(
            metric="seed_success_rate",
            eligible=n,
            attempted=n,
            passed=sum(
                1
                for ev in evaluations
                if ev.level_map()[MeasurementLevel.L1_SEEDED.value].passed
            ),
        ),
        MetricCount(
            metric="load_success_rate",
            eligible=sum(
                1
                for ev in evaluations
                if ev.level_map()[MeasurementLevel.L2_LOADED.value].eligible
            ),
            attempted=sum(
                1
                for ev in evaluations
                if ev.level_map()[MeasurementLevel.L2_LOADED.value].attempted
            ),
            passed=sum(
                1
                for ev in evaluations
                if ev.level_map()[MeasurementLevel.L2_LOADED.value].passed
            ),
        ),
        MetricCount(
            metric="exposure_success_rate",
            eligible=sum(
                1
                for ev in evaluations
                if ev.level_map()[MeasurementLevel.L3_EXPOSED.value].eligible
            ),
            attempted=sum(
                1
                for ev in evaluations
                if ev.level_map()[MeasurementLevel.L3_EXPOSED.value].attempted
            ),
            passed=sum(
                1
                for ev in evaluations
                if ev.level_map()[MeasurementLevel.L3_EXPOSED.value].passed
            ),
        ),
        MetricCount(
            metric="semantic_utilization_rate",
            eligible=sum(1 for ev in evaluations if ev.l4_applicable),
            attempted=sum(
                1
                for ev in evaluations
                if ev.level_map()[MeasurementLevel.L4_UTILIZED.value].attempted
            ),
            passed=sum(
                1
                for ev in evaluations
                if ev.level_map()[MeasurementLevel.L4_UTILIZED.value].passed
            ),
        ),
        _custom_counts(
            evaluations,
            "task_benefit_rate",
            lambda ev: ev.l5_applicable
            and ev.level_map()[MeasurementLevel.L5_TASK_BENEFIT.value].attempted,
            lambda ev: ev.level_map()[MeasurementLevel.L5_TASK_BENEFIT.value].passed,
        ),
        _custom_counts(
            evaluations,
            "contradiction_rate",
            lambda ev: ev.utilization is not None,
            lambda ev: bool(ev.utilization and ev.utilization.contradicted),
        ),
        MetricCount(
            metric="empty_memory_behavior_rate",
            eligible=len(empty_behavior_results),
            attempted=len(empty_behavior_results),
            passed=sum(1 for r in empty_behavior_results if r.passed),
        ),
        MetricCount(
            metric="false_utilization_rate",
            eligible=sum(1 for ev in evaluations if ev.l4_applicable),
            attempted=sum(
                1
                for ev in evaluations
                if ev.level_map()[MeasurementLevel.L4_UTILIZED.value].attempted
            ),
            passed=sum(1 for ev in evaluations if ev.false_utilization),
        ),
    ]

    false_utilization_count = sum(1 for ev in evaluations if ev.false_utilization)

    return SuiteMetrics(
        case_count=n,
        metrics=tuple(metrics),
        false_utilization_count=false_utilization_count,
    )
