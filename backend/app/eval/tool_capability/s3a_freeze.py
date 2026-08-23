"""TOOL S3A real-result + V1.0 selection-boundary freeze (eval/test-only).

Locks measured S3A outcomes and the V1.0 remediation STOP decision.
Does not change production defaults or runtime rollout.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

FREEZE_RELATIVE_PATH = Path(
    "tests/fixtures/l4_tool_capability/w8-tool-s3a-boundary-freeze.json"
)

SCHEMA_VERSION = "w8-tool-s3a-boundary-freeze-v1"
STAGE = "TOOL_S3A_REAL_LOCAL_BOUNDARY_FREEZE"
AUDIT_NAME = "TOOL S3A Real Result + V1.0 Selection Boundary Freeze"

REAL_ARTIFACT_RELATIVE_PATH = Path(
    "tests/fixtures/l4_tool_capability/w8-tool-s3a-real-revalidation.json"
)
P5_MANIFEST_RELATIVE_PATH = Path(
    "tests/fixtures/l4_tool_capability/l4-tool-p5-offline-characterization.manifest.json"
)
P4_MANIFEST_RELATIVE_PATH = Path(
    "tests/fixtures/l4_tool_capability/l4-tool-p4-real-ablation.manifest.json"
)

BOUNDARY_LABEL = (
    "POSSIBLE_MODEL_SELECTION_BOUNDARY ON_FROZEN_GQ131 FOR_CURRENT_LOCAL_MODEL"
)
V1_0_REMEDIATION_DECISION = "STOP"
CAPABILITY_LABEL = "NO_MEASURABLE_GAIN"
S3B_V1_0_STATUS = "NOT_PURSUED_IN_V1_0"
S3B_HISTORICAL_ROLE = "FALLBACK_CANDIDATE"
REAL_RUN_LINEAGE = "VALID"

FORBIDDEN_CLAIMS = frozenset(
    {
        "PROVEN UNIVERSAL MODEL BOUNDARY",
        "GLM cannot select tools.",
        "GLM cannot select tools",
        "UNIVERSAL_MODEL_BOUNDARY",
        "FIXED",
        "PRODUCTION_READY",
        "RUNTIME_ROLLOUT_YES",
    }
)

ALLOWED_CLAIM = (
    "For frozen GQ-131 with GLM-4.6V-Flash Thinking OFF, neither S2 advisory "
    "preference nor S3A contrastive selection framing produced measurable "
    "tool-selection gain."
)

REQUIRED_TOP_LEVEL_KEYS = frozenset(
    {
        "schema_version",
        "stage",
        "audit_name",
        "round_start_master_sha",
        "real_run_lineage",
        "product_diff",
        "golden_diff",
        "workflow_diff",
        "runtime_rollout",
        "product_change",
        "real_run_reference",
        "measured_results",
        "chronology",
        "boundary",
        "v1_0_remediation",
        "s3b",
        "claim_language",
        "forbidden_claims",
        "freeze_verdict",
    }
)


def freeze_path(repo_backend_root: Path | None = None) -> Path:
    root = repo_backend_root or Path(__file__).resolve().parents[3]
    return root / FREEZE_RELATIVE_PATH


def real_artifact_path(repo_backend_root: Path | None = None) -> Path:
    root = repo_backend_root or Path(__file__).resolve().parents[3]
    return root / REAL_ARTIFACT_RELATIVE_PATH


def p5_manifest_path(repo_backend_root: Path | None = None) -> Path:
    root = repo_backend_root or Path(__file__).resolve().parents[3]
    return root / P5_MANIFEST_RELATIVE_PATH


def p4_manifest_path(repo_backend_root: Path | None = None) -> Path:
    root = repo_backend_root or Path(__file__).resolve().parents[3]
    return root / P4_MANIFEST_RELATIVE_PATH


@lru_cache(maxsize=1)
def load_s3a_boundary_freeze() -> dict[str, Any]:
    path = freeze_path()
    payload = json.loads(path.read_text(encoding="utf-8"))
    missing = REQUIRED_TOP_LEVEL_KEYS - set(payload)
    if missing:
        raise ValueError(f"S3A boundary freeze missing keys: {sorted(missing)}")
    return payload


def load_s3a_real_artifact() -> dict[str, Any]:
    return json.loads(real_artifact_path().read_text(encoding="utf-8"))


def assert_s3a_boundary_freeze_invariants(
    freeze: dict[str, Any] | None = None,
) -> None:
    """Lock S3A measured result + V1.0 STOP boundary (eval/test-only)."""
    data = freeze or load_s3a_boundary_freeze()
    assert data["schema_version"] == SCHEMA_VERSION
    assert data["stage"] == STAGE
    assert data["audit_name"] == AUDIT_NAME

    assert data["product_diff"] == 0
    assert data["golden_diff"] == 0
    assert data["workflow_diff"] == 0
    assert data["runtime_rollout"] is False
    assert data["product_change"] is False
    assert data["real_run_lineage"] == REAL_RUN_LINEAGE

    measured = data["measured_results"]
    assert measured["S3A_REAL_LOCAL"] == CAPABILITY_LABEL
    assert measured["selection"]["S3A_OFF"] == "0/10"
    assert measured["selection"]["S3A_ON"] == "0/10"
    assert measured["full_task"]["S3A_OFF"] == "0/10"
    assert measured["full_task"]["S3A_ON"] == "0/10"
    assert measured["hard_negative_regression"] == 0
    assert measured["safety_regression"] == 0
    assert measured["delta_selection_on_minus_off"] == 0

    chronology = data["chronology"]
    assert chronology["S2"]["offline"] == "positive"
    assert chronology["S2"]["real_selection"] == "0/5"
    assert chronology["S3A"]["design"] == "contrastive"
    assert chronology["S3A"]["real_selection"] == "0/10"
    assert "two successive non-deterministic guidance" in chronology["interpretation"]

    boundary = data["boundary"]
    assert boundary["label"] == BOUNDARY_LABEL
    assert boundary["label"] != "PROVEN UNIVERSAL MODEL BOUNDARY"
    assert "UNIVERSAL" not in boundary["label"]
    assert boundary["scope"] == "ON_FROZEN_GQ131"
    assert boundary["model_scope"] == "FOR_CURRENT_LOCAL_MODEL"
    assert boundary["auto_enter_s3b_s4"] is False
    assert boundary["auto_prompt_escalation"] is False
    assert boundary["auto_deterministic_router"] is False

    rem = data["v1_0_remediation"]
    assert rem["decision"] == V1_0_REMEDIATION_DECISION
    assert rem["decision"] == "STOP"
    assert rem["runtime_rollout"] == "NO"
    assert rem["reopen_requires"] == "future_evidence"

    s3b = data["s3b"]
    assert s3b["historical_role"] == S3B_HISTORICAL_ROLE
    assert s3b["v1_0_status"] == S3B_V1_0_STATUS
    assert s3b["historical_artifact_deleted"] is False
    assert s3b["reason"].startswith("second real guidance experiment")

    claims = data["claim_language"]
    assert claims["allowed"] == ALLOWED_CLAIM
    assert claims["forbidden"] == "GLM cannot select tools."
    for label in FORBIDDEN_CLAIMS:
        assert label in data["forbidden_claims"]

    verdict = data["freeze_verdict"]
    assert verdict["TOOL_S3A"] == "PASS/FROZEN"
    assert verdict["Result"] == CAPABILITY_LABEL
    assert verdict["V1_0_remediation"] == V1_0_REMEDIATION_DECISION
    assert verdict["Boundary"] == "POSSIBLE_MODEL_SELECTION_BOUNDARY"
    assert verdict["S3B"] == S3B_V1_0_STATUS
    assert verdict["runtime_rollout"] == "NO"
    assert verdict["REAL_RUN_LINEAGE"] == REAL_RUN_LINEAGE


def assert_freeze_matches_real_artifact(
    freeze: dict[str, Any] | None = None,
) -> None:
    """Freeze numbers must match the checked-in S3A real-revalidation artifact."""
    data = freeze or load_s3a_boundary_freeze()
    real = load_s3a_real_artifact()
    ref = data["real_run_reference"]

    assert real["schema_version"] == "w8-tool-s3a-real-revalidation-v1"
    assert real["capability_label"] == CAPABILITY_LABEL
    assert real["POSSIBLE_MODEL_SELECTION_BOUNDARY"] is True
    assert real["runtime_rollout"] is False
    assert real["frozen_case"]["case_id"] == "GQ-131"
    assert real["model_config"]["model"] == "zai-org/glm-4.6v-flash"
    assert real["model_config"]["thinking"] == "OFF"

    off = real["selection_metrics"]["S3A_OFF"]["counts"]
    on = real["selection_metrics"]["S3A_ON"]["counts"]
    assert off["selection_correct"] == 0
    assert on["selection_correct"] == 0
    assert off["full_task_pass"] == 0
    assert on["full_task_pass"] == 0
    assert real["selection_metrics"]["delta_selection_on_minus_off"] == 0
    assert real["hard_negatives"]["regression_count"] == 0
    assert all(int(v) == 0 for v in real["safety_metrics"].values())

    assert ref["run_id"] == real["run_id"]
    assert ref["head_sha"] == real["head_sha"]
    assert ref["tool_s3a_base_sha"] == real["tool_s3a_base_sha"]
    assert data["round_start_master_sha"] == real["head_sha"]


def assert_s3b_historical_artifact_preserved() -> None:
    """P5 offline characterization must still record S3B as historical FALLBACK."""
    manifest = json.loads(p5_manifest_path().read_text(encoding="utf-8"))
    assert manifest["recommendation"]["fallback"] == "S3B"
    assert manifest["s3b_freeze"]["role"] == "FALLBACK"
    assert manifest["candidate_verdicts"]["S3B"] == "FALLBACK"
    # V1.0 decision lives in the new freeze; do not delete this historical record.
    freeze = load_s3a_boundary_freeze()
    assert freeze["s3b"]["historical_artifact_deleted"] is False
    assert freeze["s3b"]["historical_p5_manifest"] == P5_MANIFEST_RELATIVE_PATH.as_posix()


def assert_s2_chronology_from_p4() -> None:
    """S2 real 0/5 chronology is anchored to the P4 freeze manifest."""
    p4 = json.loads(p4_manifest_path().read_text(encoding="utf-8"))
    s2 = p4["s2_selection_improvement_gq131"]
    assert s2["00"] == "0/5"
    assert s2["10"] == "0/5"
    assert p4["s2_validation"] == "NO_MEASURABLE_GAIN"
    freeze = load_s3a_boundary_freeze()
    assert freeze["chronology"]["S2"]["real_selection"] == "0/5"
    assert freeze["chronology"]["S2"]["p4_anchor"] == P4_MANIFEST_RELATIVE_PATH.as_posix()
