"""ADVERSARIAL P2 real measurement protocol freeze tests (design-only)."""

from __future__ import annotations

import json
from pathlib import Path

from app.eval.adversarial_capability.p1_freeze import capability_valid_denominator, load_p1_manifest
from app.eval.adversarial_capability.p2_design import (
    DESIGN_REL,
    MODEL_CONFIG,
    PRIMARY_CAPABILITY_CASE_IDS,
    ROUND_START_MASTER_SHA,
    build_p2_design,
)


def test_p2_design_ready_when_p1_denominator_positive() -> None:
    denom = capability_valid_denominator()
    assert denom == 4
    p1 = load_p1_manifest()
    design = build_p2_design(p1_denominator=denom, p1_merge_sha=p1["p0_merge_sha"])
    assert design["state"] == "FROZEN"
    assert design["adv_p2"] == "PASS/FROZEN"
    assert design["ready_for_real_run"] is True
    assert design["real_run_executed_in_pr"] is False
    assert design["CAPABILITY_VALID_DENOMINATOR"] == 4
    assert design["layer_A"]["thinking"] == "OFF"
    assert design["layer_R"]["readiness"] == "READY"
    assert design["layer_A"]["readiness"] == "READY_AFTER_R"
    assert design["runtime_rollout"] is False
    assert design["primary_capability_cases"] == list(PRIMARY_CAPABILITY_CASE_IDS)


def test_p2_design_blocked_when_denominator_zero() -> None:
    design = build_p2_design(p1_denominator=0, p1_merge_sha="abc")
    assert design["state"] == "BLOCKED_BY_P1"
    assert design["ready_for_real_run"] is False


def test_p2_model_config_frozen() -> None:
    assert MODEL_CONFIG["context_tokens"] == 8192
    assert MODEL_CONFIG["temperature"] == 0
    assert MODEL_CONFIG["timeout_seconds"] == 90
    assert MODEL_CONFIG["warmup_trials"] == 3
    assert MODEL_CONFIG["single_model_residency"] is True


def test_p2_design_artifact_present() -> None:
    path = Path(__file__).resolve().parent / "fixtures/l4_adversarial_capability" / DESIGN_REL.name
    assert path.is_file()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["round_start_master_sha"] == ROUND_START_MASTER_SHA
    assert data["real_run_executed_in_pr"] is False
    assert "REAL_RETRIEVAL" in str(data["pipeline"])
    assert data["answerability_invariant"]["source"] == "ANSWERABILITY_TRUTH"
