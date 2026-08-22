"""L4 MEMORY Contract Migration P1 — sidecar manifest + denominator freeze tests."""

from __future__ import annotations

import copy
import json

import pytest

from app.eval.memory_capability.evaluator import evaluate_trajectory
from app.eval.memory_capability.migration_audit import (
    MEMORY4_MIGRATION_AUDITS,
    MEMORY4_MIGRATION_AUDIT_BY_ID,
)
from app.eval.memory_capability.migration_contract import (
    SIDECAR_MEMORY_CONTRACTS,
    SIDECAR_MEMORY_CONTRACT_BY_ID,
    ideal_trajectory_for,
    l3_blocked_hard_negative,
    legacy_case_hash,
)
from app.eval.memory_capability.migration_map import (
    BLOCKED_BY_L3_OBSERVABILITY_IDS,
    EMPTY_MEMORY_CONTROL_IDS,
    MigrationPrimaryCategory,
)
from app.eval.memory_capability.p1_freeze import (
    BLOCKED_BY_L3_OBSERVABILITY_COUNT,
    CAPABILITY_SCORE,
    EMPTY_MEMORY_BEHAVIOR_DENOMINATOR,
    L1_DENOMINATOR,
    L2_DENOMINATOR,
    L3_DENOMINATOR,
    L4_UTILIZATION_DENOMINATOR,
    L5_TASK_BENEFIT_DENOMINATOR,
    P0_MERGE_SHA,
    READY_FOR_MEMORY_P2,
    build_p1_manifest,
    load_p1_manifest,
    manifest_path,
)
from app.eval.memory_capability.l3_observability_recommendation import (
    NEED_L3_PRODUCT_INSTRUMENTATION,
)


def test_p1_denominators_frozen_independently() -> None:
    assert L1_DENOMINATOR == 4
    assert L2_DENOMINATOR == 4
    assert L3_DENOMINATOR == 2
    assert L4_UTILIZATION_DENOMINATOR == 0
    assert L5_TASK_BENEFIT_DENOMINATOR == 0
    assert EMPTY_MEMORY_BEHAVIOR_DENOMINATOR == 2
    assert BLOCKED_BY_L3_OBSERVABILITY_COUNT == 2
    assert CAPABILITY_SCORE == "NOT_YET_MEASURED"
    assert READY_FOR_MEMORY_P2 == "OBSERVABILITY"
    assert NEED_L3_PRODUCT_INSTRUMENTATION is True


def test_memory4_migration_map_four_cases_classified() -> None:
    assert len(MEMORY4_MIGRATION_AUDITS) == 4
    assert BLOCKED_BY_L3_OBSERVABILITY_IDS == frozenset({"GA-9", "GA-10"})
    assert EMPTY_MEMORY_CONTROL_IDS == frozenset({"GA-11", "GA-12"})
    for case_id in ("GA-9", "GA-10"):
        audit = MEMORY4_MIGRATION_AUDIT_BY_ID[case_id]
        assert audit.primary_migration_category == MigrationPrimaryCategory.BLOCKED_BY_L3_OBSERVABILITY
        assert audit.blocker.startswith("L3_OBSERVABILITY_GAP")
        assert audit.measurement_currently_possible["L3"] is False
    for case_id in ("GA-11", "GA-12"):
        audit = MEMORY4_MIGRATION_AUDIT_BY_ID[case_id]
        assert audit.primary_migration_category == MigrationPrimaryCategory.EMPTY_MEMORY_CONTROL
        assert audit.measurement_currently_possible["EMPTY_MEMORY_BEHAVIOR"] is True


def test_p1_sidecar_manifest_matches_code() -> None:
    manifest = load_p1_manifest()
    expected = build_p1_manifest(base_sha=P0_MERGE_SHA)
    assert manifest["schema_version"] == expected["schema_version"]
    assert manifest["denominators"] == expected["denominators"]
    assert manifest["legacy_memory4_mutated"] is False
    assert manifest["golden_rewrite"] is False
    assert manifest["capability_score"] == "NOT_YET_MEASURED"
    assert len(manifest["cases"]) == 4
    for case in manifest["cases"]:
        code = SIDECAR_MEMORY_CONTRACT_BY_ID[case["case_id"]]
        assert case["migration_contract_hash"] == code.migration_contract_hash
        assert case["legacy_case_hash"] == code.legacy_case_hash


def test_p1_legacy_case_hashes_stable() -> None:
    for contract in SIDECAR_MEMORY_CONTRACTS:
        assert legacy_case_hash(contract.case_id) == contract.legacy_case_hash


@pytest.mark.parametrize("case_id", ["GA-9", "GA-10"])
def test_p1_fixture_ideal_trajectory_passes_l1_l4(case_id: str) -> None:
    result = evaluate_trajectory(copy.deepcopy(ideal_trajectory_for(case_id)))
    for level in ("L1_SEEDED", "L2_LOADED", "L3_EXPOSED", "L4_UTILIZED"):
        assert result.level_map()[level].passed is True


@pytest.mark.parametrize("case_id", ["GA-11", "GA-12"])
def test_p1_empty_memory_ideal_passes_l1_l3(case_id: str) -> None:
    result = evaluate_trajectory(copy.deepcopy(ideal_trajectory_for(case_id)))
    for level in ("L1_SEEDED", "L2_LOADED", "L3_EXPOSED"):
        assert result.level_map()[level].passed is True
    assert result.level_map()["L4_UTILIZED"].eligible is False


@pytest.mark.parametrize("case_id", ["GA-9", "GA-10"])
def test_p1_hard_negative_missing_l3_blocks_l4(case_id: str) -> None:
    traj = l3_blocked_hard_negative(case_id)
    result = evaluate_trajectory(traj)
    assert result.level_map()["L3_EXPOSED"].passed is False
    assert result.level_map()["L4_UTILIZED"].passed is False
    assert result.level_map()["L4_UTILIZED"].attempted is False


def test_p1_manifest_file_exists() -> None:
    path = manifest_path()
    assert path.is_file()
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["stage"] == "MEMORY_CONTRACT_MIGRATION_P1"


def test_p1_gate_g_memory_counts_unchanged_in_manifest() -> None:
    manifest = load_p1_manifest()
    assert manifest["legacy_memory4_pass_count"] == 2
    assert manifest["legacy_memory4_total"] == 4
    assert manifest["legacy_memory4_score"] == "INVALID_FOR_UTILIZATION_CAPABILITY"
