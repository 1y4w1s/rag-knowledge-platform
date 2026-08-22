"""L4 TOOL capability evaluator — deterministic contract tests (P0)."""

from __future__ import annotations

import copy

import pytest

from app.eval.tool_capability.contract import CURRENT_L3_TOOL_CAPABILITY_STAGES
from app.eval.tool_capability.evaluator import evaluate_trajectory
from app.eval.tool_capability.fixtures import (
    ADAPT_FIXTURE_TRAJECTORIES,
    gq131_success_trajectory,
    gq132_success_trajectory,
    gq149_success_trajectory,
)
from app.eval.tool_capability.metrics import aggregate_metrics
from app.eval.tool_capability.migration_map import (
    ADAPT_CASE_IDS,
    GATE_G_PRIMARY_COUNTS,
    TOOL20_MIGRATION_BY_ID,
    TOOL20_MIGRATION_MAP,
    MigrationAction,
)


def test_seven_stage_contract_defined() -> None:
    assert len(CURRENT_L3_TOOL_CAPABILITY_STAGES) == 7
    names = [s.value for s in CURRENT_L3_TOOL_CAPABILITY_STAGES]
    assert names == [
        "planner_tool_selected",
        "tool_args_valid",
        "tool_resolver_accepted",
        "tool_execution_succeeded",
        "expected_observation_present",
        "post_observation_decision_valid",
        "safe_terminal",
    ]


def test_gate_g_primary_counts_preserved_in_migration_map() -> None:
    assert GATE_G_PRIMARY_COUNTS == {
        "CURRENT_L3_NATIVE": 3,
        "INTEGRATION_ONLY": 5,
        "STALE_GOLDEN_CONTRACT": 5,
        "UNSATISFIABLE_CURRENT_CONTRACT": 7,
    }
    assert len(TOOL20_MIGRATION_MAP) == 20
    assert ADAPT_CASE_IDS == frozenset({"GQ-131", "GQ-132", "GQ-149"})


@pytest.mark.parametrize("case_id", ["GQ-131", "GQ-132", "GQ-149"])
def test_adapt_fixtures_all_seven_stages_pass(case_id: str) -> None:
    trajectory = ADAPT_FIXTURE_TRAJECTORIES[case_id]
    result = evaluate_trajectory(trajectory)
    assert all(stage.passed for stage in result.stages)
    assert result.task_completion is True
    assert result.false_task_success_from_terminal is False


def test_migration_map_actions_cover_all_twenty() -> None:
    actions = {entry.action for entry in TOOL20_MIGRATION_MAP}
    assert actions == {
        MigrationAction.ADAPT,
        MigrationAction.UNIT_ONLY,
        MigrationAction.REPLACE,
        MigrationAction.UNSATISFIABLE,
    }
    assert sum(1 for e in TOOL20_MIGRATION_MAP if e.action == MigrationAction.ADAPT) == 3
    assert sum(1 for e in TOOL20_MIGRATION_MAP if e.action == MigrationAction.UNIT_ONLY) == 5
    assert sum(1 for e in TOOL20_MIGRATION_MAP if e.action == MigrationAction.REPLACE) == 5
    assert sum(1 for e in TOOL20_MIGRATION_MAP if e.action == MigrationAction.UNSATISFIABLE) == 7


def test_hard_negative_wrong_tool_selection_fails() -> None:
    trajectory = gq131_success_trajectory()
    trajectory.steps[0].selected_tool = "semantic_search"
    result = evaluate_trajectory(trajectory)
    assert result.stage_map()["planner_tool_selected"].passed is False
    assert result.task_completion is False


def test_hard_negative_invalid_args_fails() -> None:
    trajectory = gq131_success_trajectory()
    trajectory.steps[0].tool_args = {}
    result = evaluate_trajectory(trajectory)
    assert result.stage_map()["planner_tool_selected"].passed is True
    assert result.stage_map()["tool_args_valid"].passed is False
    assert result.stage_map()["tool_args_valid"].attempted is True
    assert result.task_completion is False


def test_hard_negative_resolver_rejection_fails() -> None:
    trajectory = gq132_success_trajectory()
    trajectory.steps[0].resolver_accepted = False
    result = evaluate_trajectory(trajectory)
    assert result.stage_map()["tool_resolver_accepted"].passed is False
    assert result.stage_map()["tool_execution_succeeded"].attempted is False
    assert result.task_completion is False


def test_hard_negative_execution_exception_fails() -> None:
    trajectory = gq149_success_trajectory()
    trajectory.steps[0].execution_succeeded = False
    trajectory.steps[0].execution_error = "TimeoutError"
    result = evaluate_trajectory(trajectory)
    assert result.stage_map()["tool_execution_succeeded"].passed is False
    assert result.stage_map()["expected_observation_present"].attempted is False
    assert result.task_completion is False


def test_hard_negative_missing_observation_task_incomplete() -> None:
    trajectory = gq131_success_trajectory()
    trajectory.steps[0].observation = None
    result = evaluate_trajectory(trajectory)
    assert result.stage_map()["tool_execution_succeeded"].passed is True
    assert result.stage_map()["expected_observation_present"].passed is False
    assert result.task_completion is False
    assert result.terminal_only_would_succeed is True
    assert result.false_task_success_from_terminal is True


def test_hard_negative_invalid_post_decision_task_incomplete() -> None:
    trajectory = gq132_success_trajectory()
    trajectory.steps[0].post_observation_decision_valid = False
    trajectory.steps[0].post_observation_action = "tool"
    result = evaluate_trajectory(trajectory)
    assert result.stage_map()["expected_observation_present"].passed is True
    assert result.stage_map()["post_observation_decision_valid"].passed is False
    assert result.task_completion is False


def test_hard_negative_budget_exhausted_blocks_task_completion() -> None:
    trajectory = gq149_success_trajectory()
    trajectory.budget_exhausted = True
    result = evaluate_trajectory(trajectory)
    assert result.task_completion is False
    assert result.budget_exhausted is True


def test_hard_negative_unsafe_terminal_fails_safe_stage() -> None:
    trajectory = gq131_success_trajectory()
    trajectory.safe = False
    result = evaluate_trajectory(trajectory)
    assert result.stage_map()["safe_terminal"].passed is False
    assert result.task_completion is False
    assert result.safe_termination is False


def test_success_path_does_not_use_terminal_only() -> None:
    for case_id in ADAPT_CASE_IDS:
        result = evaluate_trajectory(ADAPT_FIXTURE_TRAJECTORIES[case_id])
        assert result.task_completion is True
        assert result.false_task_success_from_terminal is False


def test_denominator_integrity_unexecuted_tools_excluded() -> None:
    resolver_blocked = gq131_success_trajectory()
    resolver_blocked.steps[0].resolver_accepted = False

    execution_failed = gq132_success_trajectory()
    execution_failed.steps[0].execution_succeeded = False
    execution_failed.steps[0].execution_error = "ToolError"

    wrong_tool = gq131_success_trajectory()
    wrong_tool.steps[0].selected_tool = "semantic_search"

    evaluations = [
        evaluate_trajectory(resolver_blocked),
        evaluate_trajectory(execution_failed),
        evaluate_trajectory(wrong_tool),
    ]
    metrics = aggregate_metrics(evaluations).metric_map()

    exec_metric = metrics["tool_execution_success_rate"]
    assert exec_metric.eligible == 3
    assert exec_metric.attempted == 1
    assert exec_metric.passed == 0

    resolver_metric = metrics["tool_resolver_accept_rate"]
    assert resolver_metric.attempted == 2
    assert resolver_metric.passed == 1

    selection_metric = metrics["tool_selection_accuracy"]
    assert selection_metric.attempted == 3
    assert selection_metric.passed == 2


def test_metrics_three_layer_counts_for_adapt_suite() -> None:
    evaluations = [
        evaluate_trajectory(copy.deepcopy(t))
        for t in ADAPT_FIXTURE_TRAJECTORIES.values()
    ]
    suite = aggregate_metrics(evaluations)
    assert suite.case_count == 3
    assert suite.task_completion_count == 3
    assert suite.false_task_success_count == 0

    for metric_name in (
        "tool_selection_accuracy",
        "tool_args_valid_rate",
        "tool_resolver_accept_rate",
        "tool_execution_success_rate",
        "expected_observation_rate",
        "post_observation_decision_valid_rate",
        "task_completion_rate",
        "safe_termination_rate",
        "budget_exhaustion_rate",
        "tool_failure_recovery_rate",
    ):
        assert metric_name in suite.metric_map()

    completion = suite.metric_map()["task_completion_rate"]
    assert completion.eligible == 3
    assert completion.attempted == 3
    assert completion.passed == 3
    assert completion.rate == 1.0


def test_gq149_requires_content_mode_in_args() -> None:
    trajectory = gq149_success_trajectory()
    trajectory.steps[0].tool_args = {"query": "content search query", "mode": "filename"}
    result = evaluate_trajectory(trajectory)
    assert result.stage_map()["tool_args_valid"].passed is False


def test_migration_map_native_cases_are_adapt() -> None:
    for case_id in ("GQ-131", "GQ-132", "GQ-149"):
        entry = TOOL20_MIGRATION_BY_ID[case_id]
        assert entry.action == MigrationAction.ADAPT
        assert entry.expected_tool in {"search_documents", "list_knowledge_bases"}


def test_observation_contract_search_documents() -> None:
    from app.eval.tool_capability.observation import observation_satisfies_contract

    ok, _ = observation_satisfies_contract(
        "search_documents",
        {"total": 1, "items": [{"document_id": "d1", "filename": "a.md"}]},
    )
    assert ok is True
    bad, reason = observation_satisfies_contract("search_documents", {"total": 0, "items": []})
    assert bad is False
    assert "document_id" in reason or "requires" in reason


def test_observation_contract_list_knowledge_bases() -> None:
    from app.eval.tool_capability.observation import observation_satisfies_contract

    ok, _ = observation_satisfies_contract(
        "list_knowledge_bases",
        {"total": 1, "items": [{"kb_id": "k1", "name": "KB"}]},
    )
    assert ok is True


def test_observation_contract_semantic_search() -> None:
    from app.eval.tool_capability.observation import observation_satisfies_contract

    ok, _ = observation_satisfies_contract(
        "semantic_search",
        {"items": [{"chunk_id": "c1", "score": 0.9, "excerpt": "evidence"}]},
    )
    assert ok is True
