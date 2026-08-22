"""L4 TOOL Contract Migration P1 — sidecar manifest + satisfiability tests."""

from __future__ import annotations

import copy
import json

import pytest

from app.eval.tool_capability.evaluator import evaluate_trajectory
from app.eval.tool_capability.fixtures import (
    ADAPT_FIXTURE_TRAJECTORIES,
    gq131_success_trajectory,
    gq132_success_trajectory,
    gq149_success_trajectory,
)
from app.eval.tool_capability.migration_contract import (
    MIGRATED_CASE_BY_ID,
    MIGRATED_CASE_CONTRACTS,
    MIGRATION_STATUS_MIGRATED,
    all_migrations_proven,
    legacy_case_hash,
)
from app.eval.tool_capability.migration_map import (
    MIGRATED_CURRENT_L3_IDS,
    TOOL20_MIGRATION_BY_ID,
    MigrationStatus,
)
from app.eval.tool_capability.observation import observation_satisfies_contract
from app.eval.tool_capability.p1_freeze import (
    CAPABILITY_VALID_CASE_COUNT,
    CURRENT_L3_TOOL_CAPABILITY_DENOMINATOR,
    MEASURED_MODEL_SCORE,
    P0_MERGE_SHA,
    build_p1_manifest,
    load_p1_manifest,
    manifest_path,
)


def test_p1_denominator_frozen_at_three() -> None:
    assert all_migrations_proven()
    assert CURRENT_L3_TOOL_CAPABILITY_DENOMINATOR == 3
    assert CAPABILITY_VALID_CASE_COUNT == 3
    assert MEASURED_MODEL_SCORE == "NOT_YET_MEASURED"


def test_p1_migrated_cases_have_satisfiability_proven() -> None:
    assert len(MIGRATED_CASE_CONTRACTS) == 3
    for contract in MIGRATED_CASE_CONTRACTS:
        assert contract.migration_status == MIGRATION_STATUS_MIGRATED
        assert contract.satisfiability.proven
        assert len(contract.stages) == 7
        assert contract.legacy_case_hash
        assert contract.migration_contract_hash


def test_p1_legacy_mapping_migrated_current_l3_only_adapt_triplet() -> None:
    assert MIGRATED_CURRENT_L3_IDS == frozenset({"GQ-131", "GQ-132", "GQ-149"})
    for case_id in MIGRATED_CURRENT_L3_IDS:
        entry = TOOL20_MIGRATION_BY_ID[case_id]
        assert entry.migration_status == MigrationStatus.MIGRATED_CURRENT_L3
    unmigrated = [
        e for e in TOOL20_MIGRATION_BY_ID.values() if e.case_id not in MIGRATED_CURRENT_L3_IDS
    ]
    assert len(unmigrated) == 17
    assert all(e.migration_status == MigrationStatus.UNMIGRATED for e in unmigrated)


def test_p1_sidecar_manifest_matches_code() -> None:
    manifest = load_p1_manifest()
    expected = build_p1_manifest(base_sha=P0_MERGE_SHA)
    assert manifest["schema_version"] == expected["schema_version"]
    assert manifest["CURRENT_L3_TOOL_CAPABILITY_DENOMINATOR"] == 3
    assert manifest["measured_model_score"] == "NOT_YET_MEASURED"
    assert manifest["legacy_tool20_score"] == "INVALID"
    assert manifest["golden_rewrite"] is False
    assert manifest["product_remediation"] is False
    assert len(manifest["cases"]) == 3
    for case in manifest["cases"]:
        code = MIGRATED_CASE_BY_ID[case["case_id"]]
        assert case["migration_contract_hash"] == code.migration_contract_hash
        assert case["legacy_case_hash"] == code.legacy_case_hash


def test_p1_legacy_case_hashes_stable() -> None:
    manifest = load_p1_manifest()
    for case in manifest["cases"]:
        assert legacy_case_hash(case["case_id"]) == case["legacy_case_hash"]


@pytest.mark.parametrize("case_id", ["GQ-131", "GQ-132", "GQ-149"])
def test_p1_ideal_trajectory_seven_of_seven(case_id: str) -> None:
    result = evaluate_trajectory(ADAPT_FIXTURE_TRAJECTORIES[case_id])
    assert all(stage.passed for stage in result.stages)
    assert result.task_completion is True


def test_p1_hard_negative_wrong_observation_fails_stage_five() -> None:
    trajectory = gq132_success_trajectory()
    trajectory.steps[0].observation = {"total": 0, "items": []}
    result = evaluate_trajectory(trajectory)
    assert result.stage_map()["expected_observation_present"].passed is False


def test_p1_hard_negative_wrong_observation_search_documents() -> None:
    trajectory = gq131_success_trajectory()
    trajectory.steps[0].observation = {"total": 1, "items": [{"kb_id": "k1", "name": "KB"}]}
    ok, _ = observation_satisfies_contract("search_documents", trajectory.steps[0].observation)
    assert ok is False
    result = evaluate_trajectory(trajectory)
    assert result.stage_map()["expected_observation_present"].passed is False


def test_p1_manifest_file_exists() -> None:
    path = manifest_path()
    assert path.is_file()
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["stage"] == "TOOL_CONTRACT_MIGRATION_P1"


def test_p1_contract_preserves_user_intent_not_legacy_chunk() -> None:
    for contract in MIGRATED_CASE_CONTRACTS:
        golden_hash = legacy_case_hash(contract.case_id)
        assert contract.legacy_case_hash == golden_hash
        assert "GET /" not in contract.observation_contract
        assert contract.expected_tool in {"search_documents", "list_knowledge_bases"}


def test_p1_replay_hard_negatives_map_to_expected_stages() -> None:
    wrong_tool = gq131_success_trajectory()
    wrong_tool.steps[0].selected_tool = "semantic_search"
    assert evaluate_trajectory(wrong_tool).stage_map()["planner_tool_selected"].passed is False

    invalid_args = copy.deepcopy(gq149_success_trajectory())
    invalid_args.steps[0].tool_args = {"query": "x", "mode": "filename"}
    assert evaluate_trajectory(invalid_args).stage_map()["tool_args_valid"].passed is False

    resolver_reject = gq132_success_trajectory()
    resolver_reject.steps[0].resolver_accepted = False
    assert evaluate_trajectory(resolver_reject).stage_map()["tool_resolver_accepted"].passed is False

    exec_fail = gq149_success_trajectory()
    exec_fail.steps[0].execution_succeeded = False
    assert evaluate_trajectory(exec_fail).stage_map()["tool_execution_succeeded"].passed is False

    missing_obs = gq131_success_trajectory()
    missing_obs.steps[0].observation = None
    assert evaluate_trajectory(missing_obs).stage_map()["expected_observation_present"].passed is False

    bad_post = gq132_success_trajectory()
    bad_post.steps[0].post_observation_decision_valid = False
    assert evaluate_trajectory(bad_post).stage_map()["post_observation_decision_valid"].passed is False

    unsafe = gq131_success_trajectory()
    unsafe.safe = False
    assert evaluate_trajectory(unsafe).stage_map()["safe_terminal"].passed is False

    budget = gq149_success_trajectory()
    budget.budget_exhausted = True
    assert evaluate_trajectory(budget).task_completion is False
