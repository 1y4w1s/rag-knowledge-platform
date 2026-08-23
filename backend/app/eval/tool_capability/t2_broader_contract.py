"""Loader for T2 broader validation design contract (design-only; no real run)."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

CONTRACT_RELATIVE_PATH = Path(
    "tests/fixtures/l4_tool_capability/t2-broader-validation-contract.json"
)

REQUIRED_TOP_LEVEL_KEYS = frozenset(
    {
        "schema_version",
        "stage",
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
        "denominators",
        "core_metrics",
        "baseline_matrix",
        "sample_size",
        "success_criteria",
        "no_results_semantics",
        "default_on_rule",
        "phase_plan",
        "design_verdict",
        "current_runtime_inventory",
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
    """Hard design invariants — no default-on, no invented expanded positive denom."""
    data = contract or load_t2_broader_validation_contract()
    assert data["design_only"] is True
    assert data["real_run_executed"] is False
    assert data["product_change"] is False
    assert data["enable_by_default"] is False
    assert data["enable_by_default_forbidden_even_if_broader_pass"] is True
    assert data["runtime_rollout"] is False
    assert data["default_on_rule"]["this_design_rollout_decision"] == "NO"
    assert data["design_verdict"]["runtime_rollout"] == "NO"
    assert data["design_verdict"]["product_change"] == 0
    assert data["design_verdict"]["state"] == "PASS"
    assert data["design_verdict"]["ready_for_real_local_broader_run"] == "YES"

    positives = [
        c
        for c in data["candidate_cases"]
        if c.get("include_in_broader_positive_denominator") is True
    ]
    assert {c["case_id"] for c in positives} == {"GQ-132", "GQ-149"}
    assert data["denominators"]["t2_bound_positive_denominator"] == 2
    assert data["denominators"]["broader_positive_denominator_phase_a"] == 2
    assert data["denominators"]["hard_negative_denominator"] == 8
    assert len(data["hard_negatives"]) == 8

    broader = data["success_criteria"]["BROADER_REAL_VALIDATED"]
    assert "ENABLE_BY_DEFAULT" in broader["does_not_authorize"]

    phase_b = data["phase_plan"]["phase_b_eligibility_extension_separate_window"]
    assert phase_b["authorized_by_this_design"] is False
    assert phase_b["requires_product_change"] is True
