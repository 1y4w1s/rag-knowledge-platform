"""W9 P3 protocol freeze tests (no LM Studio, no formal result artifact)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.w9_critic_p2_r3_batch_runner import (
    C12_CASE_ID,
    PRODUCT_PATH_ELIGIBLE_EXPECTED,
)
from tests.w9_critic_p2_r3_formal_runner import (
    EXPECTED_BASE_SHA as P2_R3_EXPECTED_BASE_SHA,
)
from tests.w9_critic_p3_protocol import (
    ACCEPTABLE_ACTION_POLICY,
    DRY_RUN_ARTIFACT_NAME,
    DRY_RUN_ARTIFACT_PATH,
    EXPECTED_BASE_SHA,
    FORMAL_ARTIFACT_NAME,
    FORMAL_ARTIFACT_PATH,
    FROZEN_TOTAL,
    MODEL_CONFIG,
    P2_R3_HISTORICAL_BASE_SHA,
    POST_61_MASTER_SHA,
    PROTOCOL_VERSION,
    SEMANTIC_ELIGIBLE,
    SEMANTIC_INELIGIBLE,
    FormalP3ArtifactForbidden,
    LmStudioForbidden,
    ObservationKind,
    P3ProtocolRunner,
    SemanticVerdict,
    aggregate_semantic_results,
    build_and_write_dry_run_plan,
    enumerate_p3_eligibility,
    request_lm_studio,
    score_semantic_trial,
    verify_p3_denominator,
)


def _eligible_item():
    return next(
        item for item in enumerate_p3_eligibility() if item.case_id != C12_CASE_ID
    )


def _c12_item():
    return next(
        item for item in enumerate_p3_eligibility() if item.case_id == C12_CASE_ID
    )


def test_p3_base_sha_is_post_61_master_not_p2_r3_history() -> None:
    assert EXPECTED_BASE_SHA == POST_61_MASTER_SHA
    assert P2_R3_EXPECTED_BASE_SHA == P2_R3_HISTORICAL_BASE_SHA
    assert EXPECTED_BASE_SHA != P2_R3_EXPECTED_BASE_SHA


def test_p3_model_config_is_frozen() -> None:
    assert MODEL_CONFIG == {
        "primary_model": "zai-org/glm-4.6v-flash",
        "thinking": "OFF",
        "temperature": 0.0,
        "max_tokens": 512,
        "timeout_seconds": 60,
        "retry": "NONE",
        "output": "structured_json_only",
    }
    assert ACCEPTABLE_ACTION_POLICY == "EXACT"


def test_p3_denominator_reuses_frozen_eleven_plus_one() -> None:
    eligibility = enumerate_p3_eligibility()
    split = verify_p3_denominator(eligibility)
    assert split == {
        "frozen_total": 12,
        "semantic_eligible": 11,
        "semantic_ineligible": 1,
        "semantic_denominator": 11,
    }
    assert FROZEN_TOTAL == 12
    assert SEMANTIC_ELIGIBLE == PRODUCT_PATH_ELIGIBLE_EXPECTED == 11
    assert SEMANTIC_INELIGIBLE == 1


def test_c12_is_protocol_invalid_probe_excluded_from_semantic_denominator() -> None:
    record = score_semantic_trial(
        _c12_item(),
        expected_action="RETRIEVE_MISSING_EVIDENCE",
        observation_kind=ObservationKind.STRUCTURED_JSON,
        observed_action="RETRIEVE_MISSING_EVIDENCE",
    )
    assert record.verdict == SemanticVerdict.MEASUREMENT_PROTOCOL_INVALID.value
    assert record.classification == "MEASUREMENT_PROTOCOL_INVALID"
    assert record.probe_classification == "DEFENSE_IN_DEPTH_PROBE"
    assert record.in_semantic_denominator is False
    assert record.semantic_eligible is False


def test_exact_action_policy_for_eligible_cases() -> None:
    item = _eligible_item()
    pass_record = score_semantic_trial(
        item,
        expected_action="ACCEPT",
        observation_kind=ObservationKind.STRUCTURED_JSON,
        observed_action="ACCEPT",
    )
    fail_record = score_semantic_trial(
        item,
        expected_action="ACCEPT",
        observation_kind=ObservationKind.STRUCTURED_JSON,
        observed_action="REFUSE",
    )
    assert pass_record.action_policy == "EXACT"
    assert pass_record.verdict == SemanticVerdict.MODEL_CAPABILITY_PASS.value
    assert pass_record.in_semantic_denominator is True
    assert fail_record.verdict == SemanticVerdict.MODEL_CAPABILITY_FAIL.value
    assert fail_record.in_semantic_denominator is True


def test_timeout_is_capability_fail_and_stays_in_denominator() -> None:
    record = score_semantic_trial(
        _eligible_item(),
        expected_action="ACCEPT",
        observation_kind=ObservationKind.TIMEOUT,
    )
    assert record.timeout is True
    assert record.verdict == SemanticVerdict.MODEL_CAPABILITY_FAIL.value
    assert record.in_semantic_denominator is True


def test_parse_failure_is_capability_fail_and_stays_in_denominator() -> None:
    record = score_semantic_trial(
        _eligible_item(),
        expected_action="ACCEPT",
        observation_kind=ObservationKind.PARSE_FAILURE,
    )
    assert record.parse_failure is True
    assert record.verdict == SemanticVerdict.MODEL_CAPABILITY_FAIL.value
    assert record.in_semantic_denominator is True


def test_hidden_recovery_never_converts_fail_to_pass() -> None:
    record = score_semantic_trial(
        _eligible_item(),
        expected_action="ACCEPT",
        observation_kind=ObservationKind.TIMEOUT,
        hidden_recovery=True,
        recovered_action="ACCEPT",
    )
    assert record.hidden_recovery is True
    assert record.recovered_action == "ACCEPT"
    assert record.verdict == SemanticVerdict.MODEL_CAPABILITY_FAIL.value
    assert record.in_semantic_denominator is True


def test_lane_a_and_lane_b_denominators_match() -> None:
    eligibility = enumerate_p3_eligibility()
    lane_a = verify_p3_denominator(eligibility)["semantic_denominator"]
    records = [
        score_semantic_trial(
            item,
            expected_action="ACCEPT",
            observation_kind=ObservationKind.STRUCTURED_JSON,
            observed_action="ACCEPT",
        )
        for item in eligibility
    ]
    lane_b = aggregate_semantic_results(records, lane="B")
    assert lane_a == lane_b.semantic_denominator == 11
    assert lane_b.frozen_total == 12
    assert lane_b.semantic_ineligible == 1
    assert lane_b.protocol_invalid == 1
    assert lane_b.passed == 11
    assert sum(1 for item in records if item.in_semantic_denominator) == 11


def test_timeout_and_parse_failure_keep_denominator_at_eleven() -> None:
    eligibility = enumerate_p3_eligibility()
    records = []
    for index, item in enumerate(eligibility):
        if item.case_id == C12_CASE_ID:
            records.append(score_semantic_trial(item, expected_action="REFUSE"))
            continue
        kind = (
            ObservationKind.TIMEOUT
            if index == 0
            else (
                ObservationKind.PARSE_FAILURE
                if index == 1
                else ObservationKind.STRUCTURED_JSON
            )
        )
        records.append(
            score_semantic_trial(
                item,
                expected_action="ACCEPT",
                observation_kind=kind,
                observed_action="ACCEPT"
                if kind is ObservationKind.STRUCTURED_JSON
                else None,
            )
        )
    aggregate = aggregate_semantic_results(records)
    assert aggregate.semantic_denominator == 11
    assert aggregate.timeout_count == 1
    assert aggregate.parse_failure_count == 1
    assert aggregate.failed == 2
    assert aggregate.passed == 9
    assert aggregate.passed + aggregate.failed == 11


def test_lm_studio_is_forbidden_in_freeze_window() -> None:
    with pytest.raises(LmStudioForbidden):
        request_lm_studio("http://localhost:1234")
    runner = P3ProtocolRunner(execution_enabled=True)
    with pytest.raises(LmStudioForbidden):
        runner.plan_batch()


def test_p3_namespace_rejects_p2_r3_artifact_names(tmp_path: Path) -> None:
    runner = P3ProtocolRunner()
    with pytest.raises(ValueError, match="P2-R3"):
        runner.write_dry_run_artifact(
            {"x": 1}, tmp_path / "dry-run-w9-critic-p2-r3-batch-plan.json"
        )
    with pytest.raises(FormalP3ArtifactForbidden):
        runner.write_formal_artifact({"x": 1})
    assert FORMAL_ARTIFACT_NAME == "w9-critic-p3-r1-real-local-semantic.json"


def test_dry_run_plan_flags_and_p3_artifact() -> None:
    runner = P3ProtocolRunner(dry_run=True, execution_enabled=False)
    plan = runner.plan_batch()
    path = runner.write_dry_run_artifact(plan)
    assert path == DRY_RUN_ARTIFACT_PATH
    assert path.name == DRY_RUN_ARTIFACT_NAME
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["protocol"] == PROTOCOL_VERSION
    assert saved["base_sha"] == POST_61_MASTER_SHA
    assert saved["dry_run"] is True
    assert saved["formal_measurement"] is False
    assert saved["real_model_capability_measured"] is False
    assert saved["lm_studio_requests"] == 0
    assert saved["denominator"]["semantic_denominator"] == 11
    assert saved["lane_a_denominator"] == 11
    assert saved["c12"]["classification"] == "MEASUREMENT_PROTOCOL_INVALID"
    assert saved["acceptable_action_policy"] == "EXACT"
    assert FORMAL_ARTIFACT_PATH.exists() is False
    assert saved["formal_artifact_present"] is False
    assert "p2-r3" not in path.name


def test_build_and_write_dry_run_plan_is_idempotent_for_schema() -> None:
    path = build_and_write_dry_run_plan()
    assert path.exists()
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["dry_run"] is True
    assert payload["formal_measurement"] is False
    assert payload["real_model_capability_measured"] is False
