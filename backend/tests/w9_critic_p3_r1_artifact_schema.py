"""W9 P3-R0.3 freeze of the future P3-R1 result artifact schema.

Deterministic contract only. Does not call LM Studio, does not execute P3-R1,
and must never write the reserved result filename.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any

from tests.w9_critic_p2_r1_harness import FIXTURES
from tests.w9_critic_p3_semantic_construct import (
    EXPECTED_BASE_SHA,
    FORMAL_RESULT_ARTIFACT_NAME,
    FORMAL_RESULT_ARTIFACT_PATH,
    FROZEN_TOTAL,
    MODEL_CONFIG,
    NEW_SEMANTIC_DENOMINATOR,
    PROTOCOL_VERSION,
    SCORING_POLICY,
    SEMANTIC_CASE_SHORT_IDS,
    enumerate_semantic_lanes,
    formal_result_artifact_present,
)

ARTIFACT_SCHEMA_VERSION = "p3-r1-semantic-v1"
MEASUREMENT_NAME = "w9_critic_p3_r1_real_local_semantic"
SEMANTIC_CONSTRUCT = "claim_status_exact"
SCHEMA_FILENAME = "w9-critic-p3-r1-real-local-semantic.schema.json"
SCHEMA_PATH = FIXTURES / SCHEMA_FILENAME

FROZEN_MODEL_CONFIG: dict[str, Any] = {
    "provider": "openai_compatible",
    "model_name": "zai-org/glm-4.6v-flash",
    "thinking": "OFF",
    "temperature": 0.0,
    "max_tokens": 512,
    "timeout_seconds": 60,
    "retry_policy": "NONE",
}

TOP_LEVEL_REQUIRED: tuple[str, ...] = (
    "protocol_version",
    "measurement_name",
    "base_sha",
    "run_id",
    "timestamp",
    "model_config",
    "semantic_construct",
    "scoring_policy",
    "frozen_total_cases",
    "semantic_eligible_cases",
    "semantic_executed_cases",
    "semantic_passed_cases",
    "semantic_failed_cases",
    "timeout_count",
    "parse_failure_count",
    "model_capability_result",
    "measurement_state",
    "artifact_schema_version",
    "cases",
)

CASE_REQUIRED: tuple[str, ...] = (
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
)

FORBIDDEN_FIELDS: frozenset[str] = frozenset(
    {
        "chain_of_thought",
        "reasoning_trace",
        "hidden_reason",
        "oracle_explanation",
        "control_plane_decision",
        "recovery_result",
        "final_product_outcome",
    }
)

FAILURE_TAXONOMY: tuple[str, ...] = (
    "SUCCESS",
    "MODEL_CAPABILITY_FAIL",
    "PARSE_FAILURE",
    "TIMEOUT",
    "PROTOCOL_ERROR",
)

MODEL_CAPABILITY_RESULTS: frozenset[str] = frozenset(
    {
        "MODEL_CAPABILITY_PASS",
        "MODEL_CAPABILITY_FAIL",
        "MEASUREMENT_PROTOCOL_INVALID",
        "NOT_APPLICABLE",
    }
)
LAYER_RESULTS: frozenset[str] = frozenset({"PASS", "FAIL", "NOT_APPLICABLE"})
MEASUREMENT_STATES: frozenset[str] = frozenset(
    {"PASS", "PARTIAL", "BLOCKED", "NOT_RUN"}
)
CLAIM_STATUSES: frozenset[str] = frozenset(
    {"SUPPORTED", "UNSUPPORTED", "CONFLICTED", "UNVERIFIABLE"}
)

_EMPTY_HASH = "0" * 64


class ArtifactSchemaError(ValueError):
    """Raised when a candidate P3-R1 artifact violates the frozen schema."""


def load_artifact_schema() -> dict[str, Any]:
    if not SCHEMA_PATH.is_file():
        raise ArtifactSchemaError(f"missing schema contract {SCHEMA_PATH}")
    payload = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ArtifactSchemaError("schema file is not a JSON object")
    return payload


def _walk_forbidden(value: Any, path: str = "$") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            key_s = str(key)
            child_path = f"{path}.{key_s}"
            if key_s in FORBIDDEN_FIELDS:
                raise ArtifactSchemaError(
                    f"forbidden field {key_s!r} at {child_path}"
                )
            _walk_forbidden(child, child_path)
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, child in enumerate(value):
            _walk_forbidden(child, f"{path}[{index}]")


def _require_keys(payload: Mapping[str, Any], required: Sequence[str], path: str) -> None:
    missing = [key for key in required if key not in payload]
    if missing:
        raise ArtifactSchemaError(f"{path} missing fields: {missing}")


def _validate_status_map(value: Any, path: str, *, allow_null: bool) -> None:
    if value is None:
        if allow_null:
            return
        raise ArtifactSchemaError(f"{path} must not be null")
    if not isinstance(value, Mapping):
        raise ArtifactSchemaError(f"{path} must be an object")
    for claim_id, status in value.items():
        if not isinstance(claim_id, str) or not claim_id:
            raise ArtifactSchemaError(f"{path} has invalid claim_id")
        if status not in CLAIM_STATUSES:
            raise ArtifactSchemaError(f"{path}.{claim_id} status {status!r} is not L1")


def _validate_case_l1_independence(case: Mapping[str, Any], path: str) -> None:
    l1 = case["model_capability_result"]
    if l1 not in MODEL_CAPABILITY_RESULTS:
        raise ArtifactSchemaError(f"{path}.model_capability_result invalid")
    if case["timeout"] is True and l1 == "MODEL_CAPABILITY_PASS":
        raise ArtifactSchemaError(f"{path}: TIMEOUT cannot yield L1 PASS")
    if case["parse_valid"] is False and l1 == "MODEL_CAPABILITY_PASS":
        raise ArtifactSchemaError(f"{path}: PARSE_FAILURE cannot yield L1 PASS")
    if case["semantic_correct"] is False and l1 == "MODEL_CAPABILITY_PASS":
        raise ArtifactSchemaError(f"{path}: wrong claim status cannot yield L1 PASS")
    l2 = case.get("control_plane_result")
    l3 = case.get("final_safety_result")
    if l2 is not None and l2 not in LAYER_RESULTS:
        raise ArtifactSchemaError(f"{path}.control_plane_result invalid")
    if l3 is not None and l3 not in LAYER_RESULTS:
        raise ArtifactSchemaError(f"{path}.final_safety_result invalid")
    # L1 FAIL + L2 PASS + L3 PASS is explicitly valid and is not an upgrade.


def validate_p3_r1_artifact(payload: Mapping[str, Any]) -> None:
    if not isinstance(payload, Mapping):
        raise ArtifactSchemaError("artifact must be a JSON object")
    _walk_forbidden(payload)
    _require_keys(payload, TOP_LEVEL_REQUIRED, "$")

    if payload["protocol_version"] != PROTOCOL_VERSION:
        raise ArtifactSchemaError("protocol_version mismatch")
    if payload["measurement_name"] != MEASUREMENT_NAME:
        raise ArtifactSchemaError("measurement_name mismatch")
    if payload["semantic_construct"] != SEMANTIC_CONSTRUCT:
        raise ArtifactSchemaError("semantic_construct must be claim_status_exact")
    if payload["scoring_policy"] != SCORING_POLICY:
        raise ArtifactSchemaError("scoring_policy must be EXACT")
    if payload["artifact_schema_version"] != ARTIFACT_SCHEMA_VERSION:
        raise ArtifactSchemaError("artifact_schema_version mismatch")
    if payload["frozen_total_cases"] != FROZEN_TOTAL:
        raise ArtifactSchemaError("frozen_total_cases mismatch")
    if payload["semantic_eligible_cases"] != NEW_SEMANTIC_DENOMINATOR:
        raise ArtifactSchemaError("semantic_eligible_cases mismatch")
    if payload["model_capability_result"] not in MODEL_CAPABILITY_RESULTS:
        raise ArtifactSchemaError("model_capability_result invalid")
    if payload["measurement_state"] not in MEASUREMENT_STATES:
        raise ArtifactSchemaError("measurement_state invalid")
    if payload.get("best_of_n", False) is not False:
        raise ArtifactSchemaError("best_of_n must be false / absent")
    if payload.get("post_filtering", False) is not False:
        raise ArtifactSchemaError("post_filtering must be false / absent")

    model_config = payload["model_config"]
    if not isinstance(model_config, Mapping):
        raise ArtifactSchemaError("model_config must be an object")
    _require_keys(model_config, tuple(FROZEN_MODEL_CONFIG), "$.model_config")
    for key, expected in FROZEN_MODEL_CONFIG.items():
        observed = model_config[key]
        if key == "temperature":
            if float(observed) != float(expected):
                raise ArtifactSchemaError("model_config.temperature must be 0.0")
        elif observed != expected:
            raise ArtifactSchemaError(f"model_config.{key} mismatch")

    l2 = payload.get("control_plane_result")
    l3 = payload.get("final_safety_result")
    if l2 is not None and l2 not in LAYER_RESULTS:
        raise ArtifactSchemaError("control_plane_result invalid")
    if l3 is not None and l3 not in LAYER_RESULTS:
        raise ArtifactSchemaError("final_safety_result invalid")
    if (
        payload["model_capability_result"] == "MODEL_CAPABILITY_PASS"
        and (
            payload["timeout_count"] > 0
            or payload["parse_failure_count"] > 0
            or payload["semantic_failed_cases"] > 0
        )
    ):
        raise ArtifactSchemaError("L1 PASS cannot include timeout/parse/semantic fails")

    cases = payload["cases"]
    if not isinstance(cases, Sequence) or isinstance(cases, (str, bytes, bytearray)):
        raise ArtifactSchemaError("cases must be an array")
    if len(cases) != payload["semantic_executed_cases"]:
        raise ArtifactSchemaError("semantic_executed_cases must equal len(cases)")

    timeout_count = 0
    parse_failure_count = 0
    passed = 0
    failed = 0
    for index, case in enumerate(cases):
        path = f"$.cases[{index}]"
        if not isinstance(case, Mapping):
            raise ArtifactSchemaError(f"{path} must be an object")
        _require_keys(case, CASE_REQUIRED, path)
        if not isinstance(case["case_id"], str) or not case["case_id"]:
            raise ArtifactSchemaError(f"{path}.case_id invalid")
        if not isinstance(case["input_hash"], str) or len(case["input_hash"]) != 64:
            raise ArtifactSchemaError(f"{path}.input_hash invalid")
        if not isinstance(case["claim_count"], int) or case["claim_count"] < 0:
            raise ArtifactSchemaError(f"{path}.claim_count invalid")
        if not isinstance(case["raw_model_output"], str):
            raise ArtifactSchemaError(f"{path}.raw_model_output must be string")
        if not isinstance(case["parse_valid"], bool):
            raise ArtifactSchemaError(f"{path}.parse_valid must be bool")
        if not isinstance(case["semantic_correct"], bool):
            raise ArtifactSchemaError(f"{path}.semantic_correct must be bool")
        if not isinstance(case["timeout"], bool):
            raise ArtifactSchemaError(f"{path}.timeout must be bool")
        if not isinstance(case["latency_ms"], (int, float)) or case["latency_ms"] < 0:
            raise ArtifactSchemaError(f"{path}.latency_ms invalid")
        stage = case["first_failed_stage"]
        if stage not in (None, *FAILURE_TAXONOMY):
            raise ArtifactSchemaError(f"{path}.first_failed_stage invalid")
        failure_class = case.get("failure_class")
        if failure_class is not None and failure_class not in FAILURE_TAXONOMY:
            raise ArtifactSchemaError(f"{path}.failure_class invalid")
        _validate_status_map(
            case["semantic_status_expected"],
            f"{path}.semantic_status_expected",
            allow_null=False,
        )
        _validate_status_map(
            case["semantic_status_prediction"],
            f"{path}.semantic_status_prediction",
            allow_null=True,
        )
        if case["parse_valid"] is False and case["parsed_output"] is not None:
            raise ArtifactSchemaError(f"{path}: invalid parse must null parsed_output")
        _validate_case_l1_independence(case, path)
        if case["timeout"]:
            timeout_count += 1
            failed += 1
        elif not case["parse_valid"]:
            parse_failure_count += 1
            failed += 1
        elif case["semantic_correct"]:
            passed += 1
        else:
            failed += 1

    if payload["timeout_count"] != timeout_count:
        raise ArtifactSchemaError("timeout_count mismatch vs cases")
    if payload["parse_failure_count"] != parse_failure_count:
        raise ArtifactSchemaError("parse_failure_count mismatch vs cases")
    if payload["semantic_passed_cases"] != passed:
        raise ArtifactSchemaError("semantic_passed_cases mismatch vs cases")
    if payload["semantic_failed_cases"] != failed:
        raise ArtifactSchemaError("semantic_failed_cases mismatch vs cases")
    if passed + failed != payload["semantic_executed_cases"]:
        raise ArtifactSchemaError("passed+failed must equal executed (no post-filter)")


def _claims_payload(statuses: Mapping[str, str]) -> dict[str, Any]:
    return {
        "claims": [
            {"claim_id": claim_id, "status": status, "evidence_refs": []}
            for claim_id, status in statuses.items()
        ]
    }


def build_mock_case(
    short_id: str,
    *,
    kind: str = "SUCCESS",
    control_plane_result: str | None = None,
    final_safety_result: str | None = None,
) -> dict[str, Any]:
    """In-memory mock case. kind is a FAILURE_TAXONOMY member."""
    lane = next(r for r in enumerate_semantic_lanes() if r.short_id == short_id)
    expected = {claim.claim_id: claim.status for claim in lane.semantic_claims}
    claim_count = len(lane.semantic_claims)
    case_id = lane.case_id
    base: dict[str, Any] = {
        "case_id": case_id,
        "input_hash": _EMPTY_HASH,
        "claim_count": claim_count,
        "semantic_status_expected": expected,
        "latency_ms": 12.0,
        "timeout": False,
    }
    if kind == "SUCCESS":
        raw = json.dumps(_claims_payload(expected), ensure_ascii=False)
        base.update(
            {
                "raw_model_output": raw,
                "parsed_output": _claims_payload(expected),
                "parse_valid": True,
                "semantic_status_prediction": expected,
                "semantic_correct": True,
                "first_failed_stage": None,
                "failure_class": "SUCCESS",
                "model_capability_result": "MODEL_CAPABILITY_PASS",
            }
        )
    elif kind == "MODEL_CAPABILITY_FAIL":
        wrong = {claim_id: "UNSUPPORTED" for claim_id in expected}
        if all(status == "UNSUPPORTED" for status in expected.values()):
            wrong = {claim_id: "SUPPORTED" for claim_id in expected}
        raw = json.dumps(_claims_payload(wrong), ensure_ascii=False)
        base.update(
            {
                "raw_model_output": raw,
                "parsed_output": _claims_payload(wrong),
                "parse_valid": True,
                "semantic_status_prediction": wrong,
                "semantic_correct": False,
                "first_failed_stage": "MODEL_CAPABILITY_FAIL",
                "failure_class": "MODEL_CAPABILITY_FAIL",
                "model_capability_result": "MODEL_CAPABILITY_FAIL",
            }
        )
    elif kind == "TIMEOUT":
        base.update(
            {
                "raw_model_output": "",
                "parsed_output": None,
                "parse_valid": False,
                "semantic_status_prediction": None,
                "semantic_correct": False,
                "timeout": True,
                "first_failed_stage": "TIMEOUT",
                "failure_class": "TIMEOUT",
                "model_capability_result": "MODEL_CAPABILITY_FAIL",
            }
        )
    elif kind == "PARSE_FAILURE":
        base.update(
            {
                "raw_model_output": '{"not":"claims"}',
                "parsed_output": None,
                "parse_valid": False,
                "semantic_status_prediction": None,
                "semantic_correct": False,
                "first_failed_stage": "PARSE_FAILURE",
                "failure_class": "PARSE_FAILURE",
                "model_capability_result": "MODEL_CAPABILITY_FAIL",
            }
        )
    elif kind == "INVALID_JSON":
        base.update(
            {
                "raw_model_output": "not-json",
                "parsed_output": None,
                "parse_valid": False,
                "semantic_status_prediction": None,
                "semantic_correct": False,
                "first_failed_stage": "PARSE_FAILURE",
                "failure_class": "PARSE_FAILURE",
                "model_capability_result": "MODEL_CAPABILITY_FAIL",
            }
        )
    elif kind == "PROTOCOL_ERROR":
        base.update(
            {
                "raw_model_output": "",
                "parsed_output": None,
                "parse_valid": False,
                "semantic_status_prediction": None,
                "semantic_correct": False,
                "first_failed_stage": "PROTOCOL_ERROR",
                "failure_class": "PROTOCOL_ERROR",
                "model_capability_result": "MEASUREMENT_PROTOCOL_INVALID",
            }
        )
    else:
        raise ArtifactSchemaError(f"unknown mock kind {kind!r}")
    if control_plane_result is not None:
        base["control_plane_result"] = control_plane_result
    if final_safety_result is not None:
        base["final_safety_result"] = final_safety_result
    return base


def _summarize(cases: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    timeout_count = sum(1 for case in cases if case["timeout"])
    parse_failure_count = sum(
        1 for case in cases if (not case["timeout"] and not case["parse_valid"])
    )
    passed = sum(
        1
        for case in cases
        if case["semantic_correct"] and not case["timeout"] and case["parse_valid"]
    )
    failed = len(cases) - passed
    return {
        "timeout_count": timeout_count,
        "parse_failure_count": parse_failure_count,
        "semantic_passed_cases": passed,
        "semantic_failed_cases": failed,
        "semantic_executed_cases": len(cases),
    }


def build_mock_artifact(
    cases: Sequence[Mapping[str, Any]],
    *,
    control_plane_result: str = "NOT_APPLICABLE",
    final_safety_result: str = "NOT_APPLICABLE",
    measurement_state: str = "PASS",
) -> dict[str, Any]:
    counts = _summarize(cases)
    l1 = (
        "MODEL_CAPABILITY_PASS"
        if counts["semantic_failed_cases"] == 0 and counts["semantic_executed_cases"] > 0
        else "MODEL_CAPABILITY_FAIL"
    )
    if any(
        case["model_capability_result"] == "MEASUREMENT_PROTOCOL_INVALID"
        for case in cases
    ):
        l1 = "MEASUREMENT_PROTOCOL_INVALID"
    return {
        "protocol_version": PROTOCOL_VERSION,
        "measurement_name": MEASUREMENT_NAME,
        "base_sha": EXPECTED_BASE_SHA,
        "run_id": "mock-p3-r0-3-schema-freeze",
        "timestamp": "2026-08-24T00:00:00Z",
        "model_config": dict(FROZEN_MODEL_CONFIG),
        "semantic_construct": SEMANTIC_CONSTRUCT,
        "scoring_policy": SCORING_POLICY,
        "frozen_total_cases": FROZEN_TOTAL,
        "semantic_eligible_cases": NEW_SEMANTIC_DENOMINATOR,
        "semantic_executed_cases": counts["semantic_executed_cases"],
        "semantic_passed_cases": counts["semantic_passed_cases"],
        "semantic_failed_cases": counts["semantic_failed_cases"],
        "timeout_count": counts["timeout_count"],
        "parse_failure_count": counts["parse_failure_count"],
        "best_of_n": False,
        "post_filtering": False,
        "timeout_remains_in_denominator": True,
        "parse_failure_remains_in_denominator": True,
        "model_capability_result": l1,
        "control_plane_result": control_plane_result,
        "final_safety_result": final_safety_result,
        "measurement_state": measurement_state,
        "artifact_schema_version": ARTIFACT_SCHEMA_VERSION,
        "failure_taxonomy": list(FAILURE_TAXONOMY),
        "cases": [dict(case) for case in cases],
    }


def build_mixed_scenario_artifact() -> dict[str, Any]:
    """Cover all 7 eligible cases plus success/fail/timeout/parse/L2-no-upgrade."""
    shorts = list(SEMANTIC_CASE_SHORT_IDS)
    kinds = {
        shorts[0]: "SUCCESS",
        shorts[1]: "SUCCESS",
        shorts[2]: "MODEL_CAPABILITY_FAIL",
        shorts[3]: "TIMEOUT",
        shorts[4]: "INVALID_JSON",
        shorts[5]: "PARSE_FAILURE",
        shorts[6]: "MODEL_CAPABILITY_FAIL",  # L1 fail + L2/L3 pass
    }
    cases = []
    for short in shorts:
        extra: dict[str, str] = {}
        if short == shorts[6]:
            extra = {
                "control_plane_result": "PASS",
                "final_safety_result": "PASS",
            }
        cases.append(build_mock_case(short, kind=kinds[short], **extra))
    return build_mock_artifact(
        cases,
        control_plane_result="PASS",
        final_safety_result="PASS",
        measurement_state="PARTIAL",
    )


def build_all_success_artifact() -> dict[str, Any]:
    cases = [build_mock_case(short, kind="SUCCESS") for short in SEMANTIC_CASE_SHORT_IDS]
    return build_mock_artifact(cases, measurement_state="PASS")


def artifact_schema_ready() -> bool:
    schema = load_artifact_schema()
    required = schema.get("required")
    if not isinstance(required, list):
        return False
    if any(field not in required for field in TOP_LEVEL_REQUIRED):
        return False
    if schema.get("properties", {}).get("artifact_schema_version", {}).get("const") != (
        ARTIFACT_SCHEMA_VERSION
    ):
        return False
    if FORMAL_RESULT_ARTIFACT_NAME != "w9-critic-p3-r1-real-local-semantic.json":
        return False
    if formal_result_artifact_present() or FORMAL_RESULT_ARTIFACT_PATH.exists():
        return False
    if MODEL_CONFIG["primary_model"] != FROZEN_MODEL_CONFIG["model_name"]:
        return False
    validate_p3_r1_artifact(build_all_success_artifact())
    validate_p3_r1_artifact(build_mixed_scenario_artifact())
    return True


def assert_reserved_result_absent() -> None:
    if formal_result_artifact_present() or FORMAL_RESULT_ARTIFACT_PATH.exists():
        raise ArtifactSchemaError(
            f"reserved result {FORMAL_RESULT_ARTIFACT_NAME} must not exist"
        )
    stray = FIXTURES / FORMAL_RESULT_ARTIFACT_NAME
    if stray.exists():
        raise ArtifactSchemaError(
            f"reserved result {FORMAL_RESULT_ARTIFACT_NAME} must not exist"
        )
