"""Three-layer metric aggregation for TOOL capability evaluator."""

from __future__ import annotations

from app.eval.tool_capability.schema import (
    CaseEvaluation,
    ContractStage,
    MetricCount,
    SuiteMetrics,
)

_METRIC_STAGE_MAP: dict[str, ContractStage] = {
    "tool_selection_accuracy": ContractStage.planner_tool_selected,
    "tool_args_valid_rate": ContractStage.tool_args_valid,
    "tool_resolver_accept_rate": ContractStage.tool_resolver_accepted,
    "tool_execution_success_rate": ContractStage.tool_execution_succeeded,
    "expected_observation_rate": ContractStage.expected_observation_present,
    "post_observation_decision_valid_rate": ContractStage.post_observation_decision_valid,
}


def _stage_counts(
    evaluations: list[CaseEvaluation],
    stage: ContractStage,
) -> MetricCount:
    eligible = len(evaluations)
    attempted = sum(1 for ev in evaluations if ev.stage_map()[stage.value].attempted)
    passed = sum(1 for ev in evaluations if ev.stage_map()[stage.value].passed)
    return MetricCount(
        metric=stage.value,
        eligible=eligible,
        attempted=attempted,
        passed=passed,
    )


def aggregate_metrics(evaluations: list[CaseEvaluation]) -> SuiteMetrics:
    n = len(evaluations)
    metrics: list[MetricCount] = []

    for metric_name, stage in _METRIC_STAGE_MAP.items():
        counts = _stage_counts(evaluations, stage)
        metrics.append(
            MetricCount(
                metric=metric_name,
                eligible=counts.eligible,
                attempted=counts.attempted,
                passed=counts.passed,
            )
        )

    task_completion_count = sum(1 for ev in evaluations if ev.task_completion)
    metrics.append(
        MetricCount(
            metric="task_completion_rate",
            eligible=n,
            attempted=n,
            passed=task_completion_count,
        )
    )

    safe_passed = sum(1 for ev in evaluations if ev.safe_termination)
    metrics.append(
        MetricCount(
            metric="safe_termination_rate",
            eligible=n,
            attempted=n,
            passed=safe_passed,
        )
    )

    budget_passed = sum(1 for ev in evaluations if ev.budget_exhausted)
    metrics.append(
        MetricCount(
            metric="budget_exhaustion_rate",
            eligible=n,
            attempted=n,
            passed=budget_passed,
        )
    )

    recovery_attempted = sum(
        1
        for ev in evaluations
        if any(
            s.stage == ContractStage.tool_execution_succeeded
            and s.attempted
            and not s.passed
            for s in ev.stages
        )
    )
    recovery_passed = sum(
        1
        for ev in evaluations
        if ev.task_completion
        and any(
            s.stage == ContractStage.tool_execution_succeeded
            and s.attempted
            and not s.passed
            for s in ev.stages
        )
    )
    metrics.append(
        MetricCount(
            metric="tool_failure_recovery_rate",
            eligible=n,
            attempted=recovery_attempted,
            passed=recovery_passed,
        )
    )

    false_task_success = sum(1 for ev in evaluations if ev.false_task_success_from_terminal)

    return SuiteMetrics(
        case_count=n,
        metrics=tuple(metrics),
        task_completion_count=task_completion_count,
        false_task_success_count=false_task_success,
    )
