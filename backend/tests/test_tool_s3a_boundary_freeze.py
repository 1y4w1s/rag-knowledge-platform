"""Freeze tests for TOOL S3A real-result + V1.0 selection boundary (no LM Studio)."""

from __future__ import annotations

from app.core.config import Settings, settings
from app.eval.tool_capability.s3a_freeze import (
    ALLOWED_CLAIM,
    BOUNDARY_LABEL,
    CAPABILITY_LABEL,
    FORBIDDEN_CLAIMS,
    S3B_HISTORICAL_ROLE,
    S3B_V1_0_STATUS,
    SCHEMA_VERSION,
    STAGE,
    V1_0_REMEDIATION_DECISION,
    assert_freeze_matches_real_artifact,
    assert_s2_chronology_from_p4,
    assert_s3a_boundary_freeze_invariants,
    assert_s3b_historical_artifact_preserved,
    load_s3a_boundary_freeze,
    load_s3a_real_artifact,
)
from app.eval.tool_capability.s3a_flags import assert_production_s3a_default


def test_s3a_boundary_freeze_loads_and_passes_invariants() -> None:
    freeze = load_s3a_boundary_freeze()
    assert_s3a_boundary_freeze_invariants(freeze)
    assert freeze["schema_version"] == SCHEMA_VERSION
    assert freeze["stage"] == STAGE
    assert freeze["freeze_verdict"]["TOOL_S3A"] == "PASS/FROZEN"
    assert freeze["freeze_verdict"]["Result"] == CAPABILITY_LABEL
    assert freeze["v1_0_remediation"]["decision"] == V1_0_REMEDIATION_DECISION


def test_s3a_measured_results_locked() -> None:
    freeze = load_s3a_boundary_freeze()
    m = freeze["measured_results"]
    assert m["S3A_REAL_LOCAL"] == "NO_MEASURABLE_GAIN"
    assert m["selection"]["S3A_OFF"] == "0/10"
    assert m["selection"]["S3A_ON"] == "0/10"
    assert m["full_task"]["S3A_OFF"] == "0/10"
    assert m["full_task"]["S3A_ON"] == "0/10"
    assert m["hard_negative_regression"] == 0
    assert m["safety_regression"] == 0
    assert_freeze_matches_real_artifact(freeze)


def test_s3a_chronology_two_successive_nd_guidance_failures() -> None:
    freeze = load_s3a_boundary_freeze()
    chrono = freeze["chronology"]
    assert chrono["S2"]["offline"] == "positive"
    assert chrono["S2"]["real_selection"] == "0/5"
    assert chrono["S3A"]["design"] == "contrastive"
    assert chrono["S3A"]["real_selection"] == "0/10"
    assert "two successive non-deterministic guidance" in chrono["interpretation"]
    assert_s2_chronology_from_p4()


def test_s3a_boundary_label_exact_and_not_universal() -> None:
    freeze = load_s3a_boundary_freeze()
    assert freeze["boundary"]["label"] == BOUNDARY_LABEL
    assert freeze["boundary"]["label"] == (
        "POSSIBLE_MODEL_SELECTION_BOUNDARY ON_FROZEN_GQ131 FOR_CURRENT_LOCAL_MODEL"
    )
    assert freeze["boundary"]["not_label"] == "PROVEN UNIVERSAL MODEL BOUNDARY"
    assert "UNIVERSAL" not in freeze["boundary"]["label"]
    assert freeze["boundary"]["auto_enter_s3b_s4"] is False
    assert freeze["v1_0_remediation"]["decision"] == "STOP"


def test_s3b_historical_fallback_not_pursued_in_v1_0() -> None:
    freeze = load_s3a_boundary_freeze()
    assert freeze["s3b"]["historical_role"] == S3B_HISTORICAL_ROLE
    assert freeze["s3b"]["v1_0_status"] == S3B_V1_0_STATUS
    assert freeze["s3b"]["historical_artifact_deleted"] is False
    assert_s3b_historical_artifact_preserved()


def test_s3a_claim_language_allows_scoped_forbids_universal() -> None:
    freeze = load_s3a_boundary_freeze()
    assert freeze["claim_language"]["allowed"] == ALLOWED_CLAIM
    assert freeze["claim_language"]["forbidden"] == "GLM cannot select tools."
    for label in FORBIDDEN_CLAIMS:
        assert label in freeze["forbidden_claims"]
    assert "GLM cannot select tools." not in freeze["claim_language"]["allowed"]


def test_s3a_lineage_valid_no_product_drift_flags() -> None:
    freeze = load_s3a_boundary_freeze()
    real = load_s3a_real_artifact()
    assert freeze["real_run_lineage"] == "VALID"
    assert freeze["round_start_master_sha"] == real["head_sha"]
    assert freeze["round_start_master_sha"] == real["tool_s3a_base_sha"]
    assert freeze["product_diff"] == 0
    assert freeze["golden_diff"] == 0
    assert freeze["workflow_diff"] == 0
    assert freeze["runtime_rollout"] is False
    assert freeze["product_change"] is False
    assert freeze["b1_audit"]["product_diff"] == 0
    assert freeze["b1_audit"]["golden_diff"] == 0
    assert freeze["b1_audit"]["workflow_diff"] == 0
    # Production defaults remain off; freeze does not enable runtime S3A.
    assert assert_production_s3a_default() is True
    assert (
        Settings.model_fields["agent_l4_tool_contrastive_selection_enabled"].default
        is False
    )
    assert settings.agent_l4_tool_contrastive_selection_enabled is False
