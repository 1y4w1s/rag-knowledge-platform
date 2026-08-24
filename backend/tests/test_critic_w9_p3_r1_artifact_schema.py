"""W9 P3-R0.3 schema freeze tests (mock / fixture only; no LM Studio)."""

from __future__ import annotations

import json
import subprocess
from copy import deepcopy
from pathlib import Path

import pytest

from tests.w9_critic_p2_r3_formal_runner import FORMAL_ARTIFACT_PATH as P2_R3_PATH
from tests.w9_critic_p3_r1_artifact_schema import (
    ARTIFACT_SCHEMA_VERSION,
    FAILURE_TAXONOMY,
    FORBIDDEN_FIELDS,
    FROZEN_MODEL_CONFIG,
    SCHEMA_PATH,
    SEMANTIC_CONSTRUCT,
    TOP_LEVEL_REQUIRED,
    ArtifactSchemaError,
    artifact_schema_ready,
    assert_reserved_result_absent,
    build_all_success_artifact,
    build_mixed_scenario_artifact,
    build_mock_artifact,
    build_mock_case,
    load_artifact_schema,
    validate_p3_r1_artifact,
)
from tests.w9_critic_p3_semantic_construct import (
    FORMAL_RESULT_ARTIFACT_NAME,
    FORMAL_RESULT_ARTIFACT_PATH,
    P2_R3_HISTORICAL_ARTIFACT_SHA256,
    POST_61_MASTER_SHA,
    SEMANTIC_CASE_SHORT_IDS,
    file_sha256,
    p2_r3_historical_artifact_diff,
)
from tests.w9_critic_p3_semantic_harness import LM_STUDIO_REQUEST_COUNTER

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_schema_file_loads_and_binds_identity() -> None:
    schema = load_artifact_schema()
    assert SCHEMA_PATH.is_file()
    assert SCHEMA_PATH.name != FORMAL_RESULT_ARTIFACT_NAME
    assert schema["properties"]["artifact_schema_version"]["const"] == (
        ARTIFACT_SCHEMA_VERSION
    )
    assert schema["properties"]["semantic_construct"]["const"] == SEMANTIC_CONSTRUCT
    assert schema["properties"]["scoring_policy"]["const"] == "EXACT"
    required = set(schema["required"])
    assert set(TOP_LEVEL_REQUIRED) <= required
    model_required = schema["properties"]["model_config"]["required"]
    assert set(FROZEN_MODEL_CONFIG) <= set(model_required)
    case_required = set(schema["definitions"]["semanticCase"]["required"])
    assert {
        "case_id",
        "input_hash",
        "claim_count",
        "raw_model_output",
        "parsed_output",
        "parse_valid",
        "semantic_status_prediction",
        "semantic_status_expected",
        "semantic_correct",
        "latency_ms",
        "timeout",
        "first_failed_stage",
        "model_capability_result",
    } <= case_required


def test_reserved_result_artifact_absent() -> None:
    assert_reserved_result_absent()
    assert not FORMAL_RESULT_ARTIFACT_PATH.exists()
    assert FORMAL_RESULT_ARTIFACT_NAME == "w9-critic-p3-r1-real-local-semantic.json"


def test_all_seven_semantic_cases_success_is_valid() -> None:
    payload = build_all_success_artifact()
    validate_p3_r1_artifact(payload)
    shorts = {case["case_id"].split("-", 1)[0] for case in payload["cases"]}
    assert shorts == set(SEMANTIC_CASE_SHORT_IDS)
    assert payload["semantic_executed_cases"] == 7
    assert payload["semantic_passed_cases"] == 7
    assert payload["model_capability_result"] == "MODEL_CAPABILITY_PASS"
    assert payload["model_config"] == FROZEN_MODEL_CONFIG


def test_mixed_scenarios_including_l2_recovery_without_l1_upgrade() -> None:
    payload = build_mixed_scenario_artifact()
    validate_p3_r1_artifact(payload)
    kinds = {case["failure_class"] for case in payload["cases"]}
    assert "SUCCESS" in kinds
    assert "MODEL_CAPABILITY_FAIL" in kinds
    assert "TIMEOUT" in kinds
    assert "PARSE_FAILURE" in kinds
    assert payload["timeout_count"] == 1
    assert payload["parse_failure_count"] == 2
    assert payload["model_capability_result"] == "MODEL_CAPABILITY_FAIL"
    assert payload["control_plane_result"] == "PASS"
    assert payload["final_safety_result"] == "PASS"
    recovered = next(
        case
        for case in payload["cases"]
        if case.get("control_plane_result") == "PASS"
        and case.get("final_safety_result") == "PASS"
    )
    assert recovered["model_capability_result"] == "MODEL_CAPABILITY_FAIL"
    assert recovered["semantic_correct"] is False


def test_timeout_and_invalid_json_and_protocol_error_are_representable() -> None:
    timeout = build_mock_artifact([build_mock_case("C01", kind="TIMEOUT")])
    invalid = build_mock_artifact([build_mock_case("C02", kind="INVALID_JSON")])
    protocol = build_mock_artifact([build_mock_case("C03", kind="PROTOCOL_ERROR")])
    validate_p3_r1_artifact(timeout)
    validate_p3_r1_artifact(invalid)
    validate_p3_r1_artifact(protocol)
    assert timeout["timeout_count"] == 1
    assert invalid["parse_failure_count"] == 1
    assert protocol["cases"][0]["first_failed_stage"] == "PROTOCOL_ERROR"
    assert set(FAILURE_TAXONOMY) == {
        "SUCCESS",
        "MODEL_CAPABILITY_FAIL",
        "PARSE_FAILURE",
        "TIMEOUT",
        "PROTOCOL_ERROR",
    }


def test_forbidden_fields_are_rejected() -> None:
    payload = build_all_success_artifact()
    for field in FORBIDDEN_FIELDS:
        bad = deepcopy(payload)
        bad[field] = "leak"
        with pytest.raises(ArtifactSchemaError, match="forbidden field"):
            validate_p3_r1_artifact(bad)
        nested = deepcopy(payload)
        nested["cases"][0][field] = "leak"
        with pytest.raises(ArtifactSchemaError, match="forbidden field"):
            validate_p3_r1_artifact(nested)


def test_l2_or_l3_cannot_upgrade_l1_pass() -> None:
    case = build_mock_case(
        "C01",
        kind="MODEL_CAPABILITY_FAIL",
        control_plane_result="PASS",
        final_safety_result="PASS",
    )
    upgraded = deepcopy(case)
    upgraded["model_capability_result"] = "MODEL_CAPABILITY_PASS"
    payload = build_mock_artifact([upgraded], control_plane_result="PASS")
    with pytest.raises(ArtifactSchemaError, match="wrong claim status"):
        validate_p3_r1_artifact(payload)


def test_frozen_model_config_rejected_when_mutated() -> None:
    payload = build_all_success_artifact()
    payload["model_config"]["thinking"] = "ON"
    with pytest.raises(ArtifactSchemaError, match="thinking"):
        validate_p3_r1_artifact(payload)
    payload = build_all_success_artifact()
    payload["model_config"]["retry_policy"] = "RETRY"
    with pytest.raises(ArtifactSchemaError, match="retry_policy"):
        validate_p3_r1_artifact(payload)
    payload = build_all_success_artifact()
    payload["semantic_construct"] = "five_action_decision"
    with pytest.raises(ArtifactSchemaError, match="claim_status_exact"):
        validate_p3_r1_artifact(payload)


def test_temp_file_roundtrip_does_not_use_reserved_name(tmp_path: Path) -> None:
    path = tmp_path / "schema-test-p3-r1-mock.json"
    payload = build_mixed_scenario_artifact()
    path.write_text(json.dumps(payload), encoding="utf-8")
    loaded = json.loads(path.read_text(encoding="utf-8"))
    validate_p3_r1_artifact(loaded)
    path.unlink()
    assert not path.exists()
    assert_reserved_result_absent()


def test_artifact_schema_ready_and_no_lm_studio() -> None:
    assert artifact_schema_ready() is True
    assert LM_STUDIO_REQUEST_COUNTER == 0
    assert_reserved_result_absent()


def test_p2_r3_and_backend_app_untouched() -> None:
    assert P2_R3_PATH.is_file()
    assert file_sha256(P2_R3_PATH) == P2_R3_HISTORICAL_ARTIFACT_SHA256
    assert p2_r3_historical_artifact_diff() == 0
    vs_master = subprocess.check_output(
        [
            "git",
            "diff",
            "--name-only",
            "origin/master",
            "--",
            "backend/tests/fixtures/l4_critic/w9-critic-p2-r3-full-product-rerun.json",
        ],
        cwd=REPO_ROOT,
        text=True,
    ).strip()
    assert vs_master == ""
    app_diff = subprocess.check_output(
        ["git", "diff", "--name-only", POST_61_MASTER_SHA, "--", "backend/app"],
        cwd=REPO_ROOT,
        text=True,
    ).strip()
    assert app_diff == ""
