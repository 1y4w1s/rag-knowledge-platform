"""W8 MEMORY P3 real capability freeze — measured L3/L4/L5 boundary helpers.

Eval/test-only. Does not change product runtime, Golden, or workflow.
Reuses MEMORY P3 real-run artifact (lineage VALID vs measurement base).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

MANIFEST_REL = Path(
    "tests/fixtures/l4_memory_capability/l4-memory-p3-real-capability.manifest.json"
)
ARTIFACT_FIXTURE_REL = Path(
    "tests/fixtures/l4_memory_capability/w8-memory-p3-real-capability.json"
)

STAGE = "MEMORY_P3_REAL_CAPABILITY_FREEZE"
MEASUREMENT_STAGE = "MEMORY_P3_REAL_LOCAL_CAPABILITY"
FREEZE_VALIDATION_MODE = "REAL_RUN_RESULT_REUSED_FOR_FREEZE"
MEMORY_P3_REAL_RUN_LINEAGE = "VALID"

# Measurement base at real-run time (PR #32 merge); lineage still VALID vs later master.
MEMORY_P3_BASE_SHA = "4c81c6340f1789a641ef0d6cbaf42c1efdaa2bc2"
# Characterization commit after rebase onto origin/master (was 38b2d4a pre-rebase).
MEASUREMENT_FEATURE_SHA = "a683bf48cf278ead3fb50bfb7442951461d53b65"

CASE_IDS = ("GA-9", "GA-10", "GA-11", "GA-12")
SEEDED_IDS = ("GA-9", "GA-10")
EMPTY_IDS = ("GA-11", "GA-12")

MODEL = "zai-org/glm-4.6v-flash"
THINKING = "OFF"
CONTEXT_TOKENS = 8192
TEMPERATURE = 0
TIMEOUT_SECONDS = 90.0
SCORED_MODEL_TRAJECTORIES = 30

# Denominator upgrade: L3 now valid measured denom; L4/L5 cannot keep P1 denom 0.
L3_DENOMINATOR = 10
L4_DENOMINATOR = 10
L5_DENOMINATOR = 10
L3_SCORE = "10/10"
L4_SCORE = "0/10"
L5_SCORE = "0/10"

L3_STATUS = "PROVEN"
L4_STATUS = "MEASURED/VALID/LOW"
L5_STATUS = "MEASURED/VALID/LOW"
L4_CLAIM = "NO_SEMANTIC_UTILIZATION_CLAIMED"
L5_CLAIM = "NO_CAUSAL_BENEFIT_DEMONSTRATED"

# Critical causal separation (seeded subset)
LIFECYCLE = {
    "L1_seeded": True,
    "L2_loaded": True,
    "L3_exposed": True,
    "L3_exposed_score": L3_SCORE,
    "L4_utilized": False,
    "L4_utilized_score": L4_SCORE,
    "L5_benefit": False,
    "L5_benefit_score": L5_SCORE,
}

CAUSAL_SEPARATION = {
    "exposure_equals_utilization": False,
    "utilization_equals_benefit": False,
    "proof": "EXPOSURE != UTILIZATION; UTILIZATION != BENEFIT",
}

PRIVACY_SAFETY = {
    "plaintext_leakage": 0,
    "wrong_run_step_memory_acceptance": 0,
    "empty_memory_fake_exposure": 0,
    "false_utilization": 0,
}

CLASSIFICATION = "PASS/CHARACTERIZED/FROZEN"
MEASUREMENT_VALIDITY = "VALID"
READY_FOR_MEMORY_P4 = True
RUNTIME_ROLLOUT = False
PRODUCT_REMEDIATION = False
GOLDEN_MUTATED = False
PRODUCTION_EXPOSURE_TRACE_DEFAULT = False


def manifest_path(repo_root: Path | None = None) -> Path:
    root = repo_root or Path(__file__).resolve().parents[3]
    return root / MANIFEST_REL


def artifact_fixture_path(repo_root: Path | None = None) -> Path:
    root = repo_root or Path(__file__).resolve().parents[3]
    return root / ARTIFACT_FIXTURE_REL


def load_p3_freeze_manifest(repo_root: Path | None = None) -> dict[str, Any]:
    return json.loads(manifest_path(repo_root).read_text(encoding="utf-8"))


def build_p3_freeze_manifest(
    *,
    convergence_round_start_master_sha: str | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": "l4-memory-p3-real-capability-freeze-v1",
        "stage": STAGE,
        "measurement_stage": MEASUREMENT_STAGE,
        "freeze_validation_mode": FREEZE_VALIDATION_MODE,
        "memory_p3_real_run_lineage": MEMORY_P3_REAL_RUN_LINEAGE,
        "memory_p3_base_sha": MEMORY_P3_BASE_SHA,
        "measurement_feature_sha": MEASUREMENT_FEATURE_SHA,
        "convergence_round_start_master_sha": convergence_round_start_master_sha,
        "artifact": "artifacts/benchmarks/tmp/reports/w8-memory-p3-real-capability.json",
        "artifact_fixture": str(ARTIFACT_FIXTURE_REL).replace("\\", "/"),
        "model": MODEL,
        "thinking": THINKING,
        "context_tokens": CONTEXT_TOKENS,
        "temperature": TEMPERATURE,
        "timeout_seconds": TIMEOUT_SECONDS,
        "case_ids": list(CASE_IDS),
        "frozen_seeded_cases": list(SEEDED_IDS),
        "empty_control_cases": list(EMPTY_IDS),
        "scored_model_trajectories": SCORED_MODEL_TRAJECTORIES,
        "classification": CLASSIFICATION,
        "measurement_validity": MEASUREMENT_VALIDITY,
        "lifecycle": LIFECYCLE,
        "causal_separation": CAUSAL_SEPARATION,
        "L3_EXPOSED": {
            "status": L3_STATUS,
            "score": L3_SCORE,
            "denom": L3_DENOMINATOR,
            "passed": 10,
            "GA-9": 1.0,
            "GA-10": 1.0,
            "claim": "L3_EXPOSED PROVEN; do NOT claim utilized/improved from L3 alone",
        },
        "L4_UTILIZED": {
            "status": L4_STATUS,
            "score": L4_SCORE,
            "denom": L4_DENOMINATOR,
            "passed": 0,
            "claim": L4_CLAIM,
        },
        "L5_TASK_BENEFIT": {
            "status": L5_STATUS,
            "score": L5_SCORE,
            "denom": L5_DENOMINATOR,
            "passed": 0,
            "claim": L5_CLAIM,
            "counterfactual": "VALID",
        },
        "denominators": {
            "L3": L3_DENOMINATOR,
            "L4_utilization": L4_DENOMINATOR,
            "L5_task_benefit": L5_DENOMINATOR,
            "note": "Cannot keep P1 L4/L5 denom 0 once L3 is machine-proven.",
            "p1_superseded": {
                "L3": 2,
                "L4_utilization": 0,
                "L5_task_benefit": 0,
            },
        },
        "privacy_safety": PRIVACY_SAFETY,
        "empty_memory_correct_behavior": {
            "score": "0/10",
            "characterization": "unsafe_termination / budget capped",
            "product_issue_filed": False,
        },
        "interpretation": (
            "The memory was genuinely exposed to the model-visible planner context, "
            "but the frozen seeded subset showed no capability-valid semantic "
            "utilization or causal task benefit. This is a valid low-capability "
            "result, not a benchmark failure."
        ),
        "non_goals": [
            "no memory prompt tuning",
            "no ranking change",
            "no selection change",
            "no Golden rewrite",
            "no runtime rollout",
        ],
        "product_remediation": PRODUCT_REMEDIATION,
        "runtime_rollout": RUNTIME_ROLLOUT,
        "golden_mutated": GOLDEN_MUTATED,
        "production_exposure_trace_default": PRODUCTION_EXPOSURE_TRACE_DEFAULT,
        "ready_for_memory_p4": READY_FOR_MEMORY_P4,
        "memory_p3": CLASSIFICATION,
    }


def assert_manifest_matches_constants(manifest: dict[str, Any]) -> None:
    assert manifest["stage"] == STAGE
    assert manifest["freeze_validation_mode"] == FREEZE_VALIDATION_MODE
    assert manifest["memory_p3_real_run_lineage"] == MEMORY_P3_REAL_RUN_LINEAGE
    assert manifest["memory_p3_base_sha"] == MEMORY_P3_BASE_SHA
    assert manifest["classification"] == CLASSIFICATION
    assert manifest["measurement_validity"] == MEASUREMENT_VALIDITY
    assert manifest["L3_EXPOSED"]["status"] == L3_STATUS
    assert manifest["L3_EXPOSED"]["score"] == L3_SCORE
    assert manifest["L3_EXPOSED"]["denom"] == L3_DENOMINATOR
    assert manifest["L4_UTILIZED"]["status"] == L4_STATUS
    assert manifest["L4_UTILIZED"]["score"] == L4_SCORE
    assert manifest["L4_UTILIZED"]["denom"] == L4_DENOMINATOR
    assert manifest["L4_UTILIZED"]["passed"] == 0
    assert manifest["L5_TASK_BENEFIT"]["status"] == L5_STATUS
    assert manifest["L5_TASK_BENEFIT"]["score"] == L5_SCORE
    assert manifest["L5_TASK_BENEFIT"]["denom"] == L5_DENOMINATOR
    assert manifest["L5_TASK_BENEFIT"]["passed"] == 0
    assert manifest["denominators"]["L4_utilization"] == 10
    assert manifest["denominators"]["L5_task_benefit"] == 10
    assert manifest["denominators"]["L4_utilization"] != 0
    assert manifest["denominators"]["L5_task_benefit"] != 0
    life = manifest["lifecycle"]
    assert life["L1_seeded"] is True
    assert life["L2_loaded"] is True
    assert life["L3_exposed"] is True
    assert life["L4_utilized"] is False
    assert life["L5_benefit"] is False
    assert life["L3_exposed_score"] == L3_SCORE
    assert life["L4_utilized_score"] == L4_SCORE
    assert life["L5_benefit_score"] == L5_SCORE
    causal = manifest["causal_separation"]
    assert causal["exposure_equals_utilization"] is False
    assert causal["utilization_equals_benefit"] is False
    privacy = manifest["privacy_safety"]
    assert privacy["plaintext_leakage"] == 0
    assert privacy["wrong_run_step_memory_acceptance"] == 0
    assert privacy["empty_memory_fake_exposure"] == 0
    assert privacy["false_utilization"] == 0
    assert manifest["ready_for_memory_p4"] is True
    assert manifest["runtime_rollout"] is False
    assert manifest["product_remediation"] is False
    assert manifest["golden_mutated"] is False
    assert manifest["production_exposure_trace_default"] is False
    # Do not claim utilized/improved from L3 alone
    claim = manifest["L3_EXPOSED"]["claim"]
    assert "utilized" in claim.lower() or "PROVEN" in claim
    assert "do NOT claim utilized" in claim or "do NOT claim" in claim


def assert_artifact_matches_freeze(artifact: dict[str, Any]) -> None:
    assert artifact["l3_proven"] is True
    assert artifact["measurement_validity"] == "VALID"
    assert artifact["scored_model_trajectories"] == SCORED_MODEL_TRAJECTORIES
    metrics = artifact["metrics"]
    assert metrics["L3_EXPOSED"]["passed"] == 10
    assert metrics["L3_EXPOSED"]["denom"] == 10
    assert metrics["L4_UTILIZED"]["passed"] == 0
    assert metrics["L4_UTILIZED"]["denom"] == 10
    assert metrics["L5_TASK_BENEFIT"]["passed"] == 0
    assert metrics["L5_TASK_BENEFIT"]["denom"] == 10
    privacy = artifact["privacy_audit"]
    assert privacy["plaintext_in_trace"] == 0
    assert privacy["wrong_run_step_acceptance"] == 0
    assert privacy["empty_fake_exposure"] == 0
    assert privacy["false_utilization"] == 0
    assert artifact["product_remediation"] is False
    assert artifact["runtime_rollout"] is False
