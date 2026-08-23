"""MEMORY C1 real null-result freeze — measured OFF/ON L3/L4/L5 boundary.

Eval/test-only. Does not change product runtime, Golden, or workflow.
Reuses MEMORY C1 real-run artifact (lineage VALID vs measurement base).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

MANIFEST_REL = Path(
    "tests/fixtures/l4_memory_capability/l4-memory-c1-real-null-result.manifest.json"
)
ARTIFACT_FIXTURE_REL = Path(
    "tests/fixtures/l4_memory_capability/w8-memory-c1-real-revalidation.json"
)

STAGE = "MEMORY_C1_REAL_NULL_RESULT_FREEZE"
MEASUREMENT_STAGE = "MEMORY_C1_REAL_LOCAL_REVALIDATION"
FREEZE_VALIDATION_MODE = "REAL_RUN_RESULT_REUSED_FOR_FREEZE"
REAL_RUN_LINEAGE = "VALID"

# Real-run base recorded in the C1 revalidation artifact (PR#40 ancestors present).
MEMORY_C1_BASE_SHA = "f4d1e7c7234df6cbf8f0e4b102c3316651805f55"
# Original measurement harness commit (pre-cherry-pick onto freeze branch).
MEASUREMENT_FEATURE_SHA = "9e63e6151416b3fbc0eac1a01424b24fd26b7537"

SEEDED_IDS = ("GA-9", "GA-10")
MODEL = "zai-org/glm-4.6v-flash"
THINKING = "OFF"
SCORED_MODEL_TRAJECTORIES = 30

C1_REAL_LOCAL_STATE = "NO_MEASURABLE_GAIN"
CLASSIFICATION = "NO_MEASURABLE_GAIN"
MEASUREMENT_VALIDITY = "VALID"

# Contemporaneous real-run scores (OFF vs ON)
L3_OFF = "10/10"
L3_ON = "10/10"
L4_OFF = "0/10"
L4_ON = "0/10"
L5_OFF_CONTROL = "0/10"
L5_ON = "0/10"
FALSE_UTILIZATION = 0

OFFLINE_PROXY_REAL_MISMATCH = "OBSERVED"
OFFLINE_PROXY_NOTE = (
    "P4 offline liked C1 (apparent_utilization_recovery=1.0 / READY_FOR_PRODUCT_EXPERIMENT); "
    "real local GA-9/GA-10 showed 0 measurable L4/L5 gain. Future MEMORY remediation cannot "
    "rely on the same offline proxy alone."
)

INTERPRETATION_ALLOWED = (
    "C1 did not produce capability-valid semantic utilization or causal task benefit "
    "on frozen GA-9/GA-10."
)
INTERPRETATION_FORBIDDEN = [
    "memory does not work",
    "model cannot use memory universally",
    "C1 proves model boundary",
]

SAFETY_FREEZE = {
    "l3_instrumentation_regression": 0,
    "false_utilization": 0,
    "privacy_leak": 0,
    "wrong_scope_exposure": 0,
}

PRIVACY_SAFETY = {
    "plaintext_leakage": 0,
    "wrong_scope": 0,
    "wrong_run_step_acceptance": 0,
    "empty_fake_exposure": 0,
    "false_utilization": 0,
}

READY_FOR_C2_DECISION_GATE = True
RUNTIME_ROLLOUT = False
PRODUCT_REMEDIATION = False
GOLDEN_MUTATED = False
PRODUCTION_C1_DEFAULT = False


def manifest_path(repo_root: Path | None = None) -> Path:
    root = repo_root or Path(__file__).resolve().parents[3]
    return root / MANIFEST_REL


def artifact_fixture_path(repo_root: Path | None = None) -> Path:
    root = repo_root or Path(__file__).resolve().parents[3]
    return root / ARTIFACT_FIXTURE_REL


def load_c1_freeze_manifest(repo_root: Path | None = None) -> dict[str, Any]:
    return json.loads(manifest_path(repo_root).read_text(encoding="utf-8"))


def load_c1_real_artifact(repo_root: Path | None = None) -> dict[str, Any]:
    path = artifact_fixture_path(repo_root)
    return json.loads(path.read_text(encoding="utf-8"), strict=False)


def build_c1_freeze_manifest(
    *,
    convergence_round_start_master_sha: str | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": "l4-memory-c1-real-null-result-freeze-v1",
        "stage": STAGE,
        "measurement_stage": MEASUREMENT_STAGE,
        "freeze_validation_mode": FREEZE_VALIDATION_MODE,
        "REAL_RUN_LINEAGE": REAL_RUN_LINEAGE,
        "memory_c1_base_sha": MEMORY_C1_BASE_SHA,
        "measurement_feature_sha": MEASUREMENT_FEATURE_SHA,
        "convergence_round_start_master_sha": convergence_round_start_master_sha,
        "artifact": "artifacts/benchmarks/tmp/reports/w8-memory-c1-real-revalidation.json",
        "artifact_fixture": str(ARTIFACT_FIXTURE_REL).replace("\\", "/"),
        "model": MODEL,
        "thinking": THINKING,
        "frozen_seeded_cases": list(SEEDED_IDS),
        "scored_model_trajectories": SCORED_MODEL_TRAJECTORIES,
        "C1_REAL_LOCAL_STATE": C1_REAL_LOCAL_STATE,
        "classification": CLASSIFICATION,
        "measurement_validity": MEASUREMENT_VALIDITY,
        "contemporaneous": {
            "L3_EXPOSED": {"OFF": L3_OFF, "ON": L3_ON},
            "L4_UTILIZED": {"OFF": L4_OFF, "ON": L4_ON},
            "L5_TASK_BENEFIT": {"OFF_control": L5_OFF_CONTROL, "ON": L5_ON},
            "false_utilization": FALSE_UTILIZATION,
        },
        "OFFLINE_PROXY_REAL_MISMATCH": OFFLINE_PROXY_REAL_MISMATCH,
        "offline_proxy_note": OFFLINE_PROXY_NOTE,
        "interpretation_discipline": {
            "allowed": INTERPRETATION_ALLOWED,
            "forbidden": list(INTERPRETATION_FORBIDDEN),
        },
        "safety_freeze": SAFETY_FREEZE,
        "privacy_safety": PRIVACY_SAFETY,
        "product_remediation": PRODUCT_REMEDIATION,
        "runtime_rollout": RUNTIME_ROLLOUT,
        "golden_mutated": GOLDEN_MUTATED,
        "production_c1_default": PRODUCTION_C1_DEFAULT,
        "ready_for_c2_decision_gate": READY_FOR_C2_DECISION_GATE,
        "non_goals": [
            "no C2 product implementation",
            "no memory prompt tuning beyond frozen measurement",
            "no Golden rewrite",
            "no runtime rollout",
            "no model re-run",
        ],
    }


def assert_manifest_matches_constants(manifest: dict[str, Any]) -> None:
    assert manifest["stage"] == STAGE
    assert manifest["freeze_validation_mode"] == FREEZE_VALIDATION_MODE
    assert manifest["REAL_RUN_LINEAGE"] == REAL_RUN_LINEAGE
    assert manifest["memory_c1_base_sha"] == MEMORY_C1_BASE_SHA
    assert manifest["C1_REAL_LOCAL_STATE"] == C1_REAL_LOCAL_STATE
    assert manifest["classification"] == CLASSIFICATION
    assert manifest["measurement_validity"] == MEASUREMENT_VALIDITY
    cont = manifest["contemporaneous"]
    assert cont["L3_EXPOSED"]["OFF"] == L3_OFF
    assert cont["L3_EXPOSED"]["ON"] == L3_ON
    assert cont["L4_UTILIZED"]["OFF"] == L4_OFF
    assert cont["L4_UTILIZED"]["ON"] == L4_ON
    assert cont["L5_TASK_BENEFIT"]["OFF_control"] == L5_OFF_CONTROL
    assert cont["L5_TASK_BENEFIT"]["ON"] == L5_ON
    assert cont["false_utilization"] == FALSE_UTILIZATION
    assert manifest["OFFLINE_PROXY_REAL_MISMATCH"] == OFFLINE_PROXY_REAL_MISMATCH
    disc = manifest["interpretation_discipline"]
    assert disc["allowed"] == INTERPRETATION_ALLOWED
    for banned in INTERPRETATION_FORBIDDEN:
        assert banned in disc["forbidden"]
    safety = manifest["safety_freeze"]
    assert safety["l3_instrumentation_regression"] == 0
    assert safety["false_utilization"] == 0
    assert safety["privacy_leak"] == 0
    assert safety["wrong_scope_exposure"] == 0
    privacy = manifest["privacy_safety"]
    assert privacy["plaintext_leakage"] == 0
    assert privacy["wrong_scope"] == 0
    assert privacy["false_utilization"] == 0
    assert manifest["ready_for_c2_decision_gate"] is True
    assert manifest["runtime_rollout"] is False
    assert manifest["product_remediation"] is False
    assert manifest["golden_mutated"] is False
    assert manifest["production_c1_default"] is False


def assert_artifact_matches_freeze(artifact: dict[str, Any]) -> None:
    assert artifact["schema_version"] == "w8-memory-c1-real-revalidation-v1"
    assert artifact["classification"] == CLASSIFICATION
    assert artifact["ready_for_freeze"] is True
    assert artifact["runtime_rollout"] is False
    assert artifact["product_remediation"] is False
    assert artifact["memory_c1_base_sha"] == MEMORY_C1_BASE_SHA
    metrics = artifact["metrics"]
    assert metrics["scored_trajectories"] == SCORED_MODEL_TRAJECTORIES
    assert metrics["L3_EXPOSED"]["OFF_WITH_MEMORY"]["passed"] == 10
    assert metrics["L3_EXPOSED"]["ON_WITH_MEMORY"]["passed"] == 10
    assert metrics["L4_UTILIZED"]["OFF_WITH_MEMORY"]["passed"] == 0
    assert metrics["L4_UTILIZED"]["ON_WITH_MEMORY"]["passed"] == 0
    assert metrics["L5_TASK_BENEFIT"]["OFF_control"]["passed"] == 0
    assert metrics["L5_TASK_BENEFIT"]["ON"]["passed"] == 0
    privacy = artifact["privacy_audit"]
    assert privacy["plaintext_in_trace"] == 0
    assert privacy["wrong_scope"] == 0
    assert privacy["false_utilization"] == 0
    assert privacy["empty_fake_exposure"] == 0
    assert artifact["hard_negatives"]["false_utilization_count"] == 0
