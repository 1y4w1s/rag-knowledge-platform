"""W8 P7 P2 real schema revalidation tests (manifest + deterministic replay)."""

from __future__ import annotations

import json

from app.eval.schema_ablation.p2_freeze import (
    FINAL_UNRECOVERED_SCHEMA_FAILURE,
    FRESH_RAW_TNA,
    FRESH_RECOVERED_TNA,
    FRESH_UNRECOVERED_TNA,
    FROZEN_REPLAY_RECOVERED_COUNT,
    FROZEN_REPLAY_TARGET_COUNT,
    FREEZE_VALIDATION_MODE,
    P7_CLOSEOUT_BASE_SHA,
    P7_P1_FEATURE_SHA,
    P7_P1_MERGE_SHA,
    STAGE,
    assert_manifest_matches_constants,
    load_p2_freeze_manifest,
    manifest_path,
    run_frozen_target_replay,
)


def test_p2_freeze_manifest_frozen_fields() -> None:
    manifest = load_p2_freeze_manifest()
    assert manifest["schema_version"] == "w8-p7-p2-real-schema-revalidation-v1"
    assert manifest["stage"] == STAGE
    assert manifest["p7_closeout_base_sha"] == P7_CLOSEOUT_BASE_SHA
    assert manifest["model"] == "zai-org/glm-4.6v-flash"
    assert manifest["thinking"] == "OFF"
    assert manifest["freeze_validation_mode"] == FREEZE_VALIDATION_MODE
    assert manifest["raw_model_tna_count"] == FRESH_RAW_TNA
    assert manifest["final_unrecovered_schema_failure"] == FINAL_UNRECOVERED_SCHEMA_FAILURE
    assert manifest["w8_p7_p2"] == "PASS/FROZEN"
    assert manifest["gate_h"] == "PASS/FROZEN"
    assert_manifest_matches_constants(manifest)


def test_p2_freeze_manifest_lineage_shas() -> None:
    manifest = load_p2_freeze_manifest()
    assert manifest["p7_p1_merge_sha"] == P7_P1_MERGE_SHA
    assert manifest["p7_p1_feature_sha"] == P7_P1_FEATURE_SHA
    assert manifest["base_sha"] == P7_CLOSEOUT_BASE_SHA
    assert manifest["comparison"]["historical_unrecovered_schema_failures"] == "9/226"
    assert manifest["comparison"]["fresh_unrecovered_schema_failures"] == "0/166"
    assert manifest["comparison"]["fresh_raw_tool_name_as_action"] == "7/166"


def test_p2_freeze_manifest_file_tracked_fixture() -> None:
    path = manifest_path()
    assert path.is_file()
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["fresh_recovered_tool_name_as_action"] == FRESH_RECOVERED_TNA
    assert payload["fresh_unrecovered_tool_name_as_action"] == FRESH_UNRECOVERED_TNA
    assert payload["false_accepts"] == 0
    assert payload["unsafe_finish"] == 0


def test_p2_frozen_replay_nine_of_nine_product_parser() -> None:
    replay = run_frozen_target_replay()
    assert replay["target_count"] == FROZEN_REPLAY_TARGET_COUNT
    assert replay["recovered_count"] == FROZEN_REPLAY_RECOVERED_COUNT
    assert replay["false_accepts"] == 0


def test_p2_freeze_real_run_metrics_not_direct_comparison() -> None:
    manifest = load_p2_freeze_manifest()
    assert manifest["comparison"]["note"] == "NOT_DIRECT_MODEL_CAPABILITY_COMPARISON"
    assert manifest["not_measured"]["golden_168_regression"] == "NOT_MEASURED"
