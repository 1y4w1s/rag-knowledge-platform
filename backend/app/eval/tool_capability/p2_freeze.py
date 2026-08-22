"""W8 TOOL P2 real local capability freeze — measured boundary manifest helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

MANIFEST_REL = Path("tests/fixtures/l4_tool_capability/l4-tool-p2-real-capability.manifest.json")

P1_MERGE_SHA = "ba5837bed3a1828363871c2f3c2dd92fd761bbec"
P2_MEASUREMENT_BASE_SHA = P1_MERGE_SHA
STAGE = "TOOL_P2_REAL_LOCAL_CAPABILITY"
FREEZE_VALIDATION_MODE = "REAL_RUN_RESULT_REUSED_FOR_FREEZE"

CASE_IDS = ("GQ-131", "GQ-132", "GQ-149")
DENOMINATOR = 3
STABILITY_TRIALS_PER_CASE = 5
TOTAL_TRIALS = 15

MODEL = "zai-org/glm-4.6v-flash"
THINKING = "OFF"
CONTEXT_TOKENS = 8192
TEMPERATURE = 0
TIMEOUT_SECONDS = 90.0

PRIMARY_SCORE = "0/3"
TRIAL_SUCCESS = "0/15"
PER_CASE_REPEAT = {"GQ-131": "0/5", "GQ-132": "0/5", "GQ-149": "0/5"}

MEASURED_MODEL_SCORE = PRIMARY_SCORE
CAPABILITY_LABEL = "CURRENT_L3_TOOL_CAPABILITY ON_FROZEN_MIGRATED_SUBSET"

RAW_TNA = 10
RECOVERED_TNA = 10
UNRECOVERED_TNA = 0

CONTRACT_MANIFEST_HASH = "e37a61ac1d26d702af569756c607ee3509d62f0b03a2b2c50a7830400fe0d5dc"

FIRST_FAILURE_TAXONOMY = {
    "WRONG_OR_MISSING_TOOL": 5,
    "BUDGET_EXHAUSTED": 10,
}

FAILURE_CHARACTERIZATION = {
    "GQ-131": {
        "layer": "tool_selection",
        "detail": "planner selected semantic_search; contract expects search_documents",
        "primary_taxonomy": "WRONG_OR_MISSING_TOOL",
    },
    "GQ-132": {
        "layer": "post_observation_termination",
        "detail": "tool chain through observation OK; no safe terminal; budget exhausted looping list_knowledge_bases",
        "primary_taxonomy": "BUDGET_EXHAUSTED",
    },
    "GQ-149": {
        "layer": "post_observation_termination",
        "detail": "tool chain through observation OK; no safe terminal; budget exhausted looping search_documents+mode=content",
        "primary_taxonomy": "BUDGET_EXHAUSTED",
    },
}


def manifest_path(repo_root: Path | None = None) -> Path:
    root = repo_root or Path(__file__).resolve().parents[3]
    return root / MANIFEST_REL


def load_p2_freeze_manifest(repo_root: Path | None = None) -> dict[str, Any]:
    return json.loads(manifest_path(repo_root).read_text(encoding="utf-8"))


def measurement_ready_for_freeze(
    *,
    safety_totals: dict[str, int],
    unrecovered_tna: int,
    product_issues: list[Any],
) -> bool:
    """Freeze when measurement is trustworthy — not when the model passes all cases."""
    if product_issues:
        return False
    if unrecovered_tna != 0:
        return False
    return all(v == 0 for v in safety_totals.values())


def assert_manifest_matches_constants(manifest: dict[str, Any]) -> None:
    assert manifest["stage"] == STAGE
    assert manifest["p1_merge_sha"] == P1_MERGE_SHA
    assert manifest["measurement_base_sha"] == P2_MEASUREMENT_BASE_SHA
    assert manifest["case_ids"] == list(CASE_IDS)
    assert manifest["denominator"] == DENOMINATOR
    assert manifest["primary_score"] == PRIMARY_SCORE
    assert manifest["trial_success"] == TRIAL_SUCCESS
    assert manifest["per_case_repeat"] == PER_CASE_REPEAT
    assert manifest["measured_model_score"] == MEASURED_MODEL_SCORE
    assert manifest["measurement_validity"] == "TRUSTWORTHY"
    assert manifest["result"] == "PASS/CHARACTERIZED"
    assert manifest["tool_p2"] == "PASS/FROZEN"
    assert manifest["ready_for_freeze"] is True
    assert manifest["runtime_rollout"] == "NO"
    assert manifest["product_remediation"] == "NO"
    assert manifest["freeze_validation_mode"] == FREEZE_VALIDATION_MODE
    tna = manifest["tna_tracking"]
    assert tna["raw_tool_name_as_action"] == RAW_TNA
    assert tna["recovered_tool_name_as_action"] == RECOVERED_TNA
    assert tna["unrecovered_tool_name_as_action"] == UNRECOVERED_TNA
    assert manifest["first_failure_taxonomy"] == FIRST_FAILURE_TAXONOMY
    safety = manifest["safety_metrics"]
    assert all(safety[k] == 0 for k in safety)
