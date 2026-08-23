"""Loader for T2 Broader Validation Phase A Contract (eval freeze; no real run)."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

CONTRACT_RELATIVE_PATH = Path(
    "tests/fixtures/l4_tool_capability/t2-broader-validation-contract.json"
)

CONTRACT_NAME = "T2 Broader Validation Phase A Contract"
STAGE = "T2_BROADER_VALIDATION_PHASE_A_CONTRACT"
SCHEMA_VERSION = "t2-broader-validation-phase-a-contract-v1"
POSITIVE_CASE_IDS = frozenset({"GQ-132", "GQ-149"})
FORBIDDEN_LABELS = frozenset(
    {
        "Broader Validation Completed",
        "Expanded Capability Validated",
    }
)

REQUIRED_TOP_LEVEL_KEYS = frozenset(
    {
        "schema_version",
        "stage",
        "contract_name",
        "forbidden_labels",
        "design_only",
        "real_run_executed",
        "product_change",
        "enable_by_default",
        "enable_by_default_forbidden_even_if_broader_pass",
        "convergence_round_start_master_sha",
        "candidate_cases",
        "excluded_cases",
        "positive_strata",
        "hard_negatives",
        "hard_negative_contract",
        "denominators",
        "core_metrics",
        "baseline_matrix",
        "sample_size",
        "success_criteria",
        "no_results_semantics",
        "default_on_rule",
        "phase_plan",
        "phase_a_freeze",
        "design_verdict",
        "current_runtime_inventory",
    }
)

POSITIVE_GATE_KEYS = frozenset(
    {
        "runtime_executable",
        "tool_exposed",
        "observation_machine_verifiable",
        "completion_predicate_clear",
        "safe_terminal_verifiable",
        "current_contract_valid",
    }
)


def contract_path(repo_backend_root: Path | None = None) -> Path:
    root = repo_backend_root or Path(__file__).resolve().parents[3]
    return root / CONTRACT_RELATIVE_PATH


@lru_cache(maxsize=1)
def load_t2_broader_validation_contract() -> dict[str, Any]:
    path = contract_path()
    payload = json.loads(path.read_text(encoding="utf-8"))
    missing = REQUIRED_TOP_LEVEL_KEYS - set(payload)
    if missing:
        raise ValueError(f"T2 broader contract missing keys: {sorted(missing)}")
    return payload


def assert_design_invariants(contract: dict[str, Any] | None = None) -> None:
    """Phase A freeze invariants — no default-on, no expanded positive denom claims."""
    data = contract or load_t2_broader_validation_contract()
    assert data["schema_version"] == SCHEMA_VERSION
    assert data["stage"] == STAGE
    assert data["contract_name"] == CONTRACT_NAME
    assert data["contract_name"] not in FORBIDDEN_LABELS
    for label in FORBIDDEN_LABELS:
        assert label in data["forbidden_labels"]

    assert data["design_only"] is True
    assert data["real_run_executed"] is False
    assert data["product_change"] is False
    assert data["enable_by_default"] is False
    assert data["enable_by_default_forbidden_even_if_broader_pass"] is True
    assert data["runtime_rollout"] is False
    assert data["default_on_rule"]["this_design_rollout_decision"] == "NO"

    freeze = data["phase_a_freeze"]
    assert freeze["PHASE_A_CONTRACT"] == "VALID"
    assert freeze["POSITIVE_DENOMINATOR_EXPANDED"] == "NO"
    assert freeze["positive_denominator"] == 2
    assert freeze["positive_cases"] == ["GQ-132", "GQ-149"]
    assert freeze["gq131_role"] == "ELIGIBILITY_CONTROL"
    assert freeze["gq131_in_positive_denominator"] is False
    assert freeze["ready_for_phase_b"] == "YES"
    assert freeze["runtime_rollout"] == "NO"
    assert freeze["broader_real_validated"] == "WAITS_FOR_PHASE_B"

    verdict = data["design_verdict"]
    assert verdict["state"] == "PASS"
    assert verdict["phase_a_status"] == "PASS_FROZEN"
    assert verdict["PHASE_A_CONTRACT"] == "VALID"
    assert verdict["POSITIVE_DENOMINATOR_EXPANDED"] == "NO"
    assert verdict["ready_for_phase_b"] == "YES"
    assert verdict["runtime_rollout"] == "NO"
    assert verdict["product_change"] == 0
    assert verdict["gq131_role"] == "ELIGIBILITY_CONTROL"
    assert verdict["ready_for_real_local_broader_run"] == "YES"

    positives = [
        c
        for c in data["candidate_cases"]
        if c.get("include_in_broader_positive_denominator") is True
    ]
    assert {c["case_id"] for c in positives} == POSITIVE_CASE_IDS
    assert data["denominators"]["t2_bound_positive_denominator"] == 2
    assert data["denominators"]["broader_positive_denominator_phase_a"] == 2
    assert data["denominators"]["POSITIVE_DENOMINATOR_EXPANDED"] == "NO"
    assert data["denominators"]["hard_negative_denominator"] == 8
    assert len(data["hard_negatives"]) == 8

    for case in positives:
        gate = case["phase_a_positive_gate"]
        assert set(gate) == POSITIVE_GATE_KEYS
        assert all(gate[k] is True for k in POSITIVE_GATE_KEYS)

    broader = data["success_criteria"]["BROADER_REAL_VALIDATED"]
    assert "ENABLE_BY_DEFAULT" in broader["does_not_authorize"]
    assert broader["waits_for"] == "PHASE_B"
    assert broader["phase_a_may_award"] is False
    assert broader["status_under_phase_a"] == "NOT_CLAIMED_WAITS_FOR_PHASE_B"
    assert data["success_criteria"]["PHASE_A_CONTRACT"]["status"] == "VALID"
    assert data["success_criteria"]["FUTURE_BROADER_RUN_GATES"]["phase_a_does_not_satisfy"] is True

    hn = data["hard_negative_contract"]
    assert hn["denominator"] == 8
    assert hn["phase_a_status"] == "CONTRACT_FROZEN_NOT_EXECUTED"
    assert hn["gates"]["t2_false_positive_rate"] == "must_be_0"
    assert hn["gates"]["premature_finish_rate"] == "must_be_0"
    assert hn["gates"]["unsafe_finish_rate"] == "must_be_0"
    assert hn["gates"]["eligibility_precision"] == "must_be_1.0"

    phase_b = data["phase_plan"]["phase_b_eligibility_extension_separate_window"]
    assert phase_b["authorized_by_this_design"] is False
    assert phase_b["requires_product_change"] is True
