"""W9 P3-R0.1 semantic construct re-freeze gates (dry-run / mock only)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from app.eval.local_model_profile.adapter import OpenAICompatibleAdapter

from tests.w9_critic_p2_r1_harness import load_frozen_suite
from tests.w9_critic_p2_r3_formal_runner import FORMAL_ARTIFACT_PATH as P2_R3_PATH
from tests.w9_critic_p3_semantic_construct import (
    DETERMINISTIC_ONLY_SHORT_IDS,
    EXPECTED_BASE_SHA,
    FORMAL_RESULT_ARTIFACT_PATH,
    HIDDEN_RECOVERY_CANNOT_UPGRADE_L1,
    MODEL_CONFIG,
    NEW_SEMANTIC_DENOMINATOR,
    P2_R3_HISTORICAL_ARTIFACT_SHA256,
    PARSE_FAILURE_REMAINS_IN_DENOMINATOR,
    POST_61_MASTER_SHA,
    PROTOCOL_FIXTURE_PATH,
    PROTOCOL_INVALID_SHORT_IDS,
    PROTOCOL_VERSION,
    SCORING_POLICY,
    SEMANTIC_CASE_SHORT_IDS,
    SEMANTIC_CLAIM_COUNT,
    TIMEOUT_REMAINS_IN_DENOMINATOR,
    CaseLaneRecord,
    FormalP3ArtifactForbidden,
    LmStudioForbidden,
    MeasurementLayer,
    ModelCapabilityResult,
    ObservationKind,
    assert_denominator_invariants,
    assert_no_oracle_leakage,
    assert_oracle_uniqueness_freezes,
    build_model_input,
    build_protocol_freeze_document,
    enumerate_semantic_lanes,
    file_sha256,
    formal_result_artifact_present,
    p2_r3_historical_artifact_diff,
    request_lm_studio,
    score_l1_observation,
    short_case_id,
    write_formal_p3_result,
)
from tests.w9_critic_p3_semantic_harness import (
    ADAPTER_CLASS,
    DryRunSemanticAdapter,
    build_eligible_model_requests,
    make_profile_adapter,
    oracle_leakage_count,
    parse_claim_status_payload,
    regression_gate_report,
    run_mock_lane_a_and_b,
    write_dry_run_plan,
    write_protocol_fixture,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_base_sha_is_post_61() -> None:
    assert POST_61_MASTER_SHA == "ef79178e8dbfe9a9dec0526ef8b003732a819020"
    assert EXPECTED_BASE_SHA == POST_61_MASTER_SHA
    head = subprocess.check_output(
        ["git", "merge-base", POST_61_MASTER_SHA, "HEAD"],
        cwd=REPO_ROOT,
        text=True,
    ).strip()
    assert head == POST_61_MASTER_SHA


def test_protocol_fixture_and_dry_run_plan_write() -> None:
    doc = write_protocol_fixture()
    plan = write_dry_run_plan()
    assert PROTOCOL_FIXTURE_PATH.is_file()
    assert doc["protocol"] == PROTOCOL_VERSION
    assert doc["scoring_policy"] == SCORING_POLICY
    assert doc["acceptable_set"] is None
    assert doc["research_question"]
    assert doc["semantic_construct_definition"]
    assert doc["denominator"]["semantic_eligible"] == NEW_SEMANTIC_DENOMINATOR
    assert plan["gates"]["SEMANTIC_DENOMINATOR_LANE_A_B_MATCH"] == "YES"
    assert plan["real_model_capability_measured"] is False


def test_semantic_denominator_is_seven_cases_ten_claims() -> None:
    records = enumerate_semantic_lanes()
    accounting = assert_denominator_invariants(records)
    assert accounting["semantic_eligible"] == 7
    assert accounting["semantic_claim_count"] == SEMANTIC_CLAIM_COUNT == 10
    assert {short_case_id(c) for c in accounting["SEMANTIC_CASES"]} == set(
        SEMANTIC_CASE_SHORT_IDS
    )
    assert {short_case_id(c) for c in accounting["DETERMINISTIC_ONLY_CASES"]} == set(
        DETERMINISTIC_ONLY_SHORT_IDS
    )
    assert {short_case_id(c) for c in accounting["PROTOCOL_INVALID_CASES"]} == set(
        PROTOCOL_INVALID_SHORT_IDS
    )


def test_deterministic_and_protocol_invalid_excluded_from_l1() -> None:
    accounting = assert_denominator_invariants()
    assert accounting["DETERMINISTIC_CASES_IN_L1_DENOMINATOR"] == 0
    assert accounting["PROTOCOL_INVALID_CASES_IN_L1_DENOMINATOR"] == 0
    for record in enumerate_semantic_lanes():
        if record.lane in {"DETERMINISTIC_ONLY", "PROTOCOL_INVALID", "OWNER_ABSENT"}:
            assert record.in_l1_denominator is False
            assert record.semantic_eligible is False
            assert (
                score_l1_observation(
                    lane=record,
                    observation_kind=ObservationKind.STRUCTURED_JSON,
                    observed_statuses={},
                )
                is ModelCapabilityResult.NOT_APPLICABLE
            )


def test_oracle_uniqueness_freezes() -> None:
    assert_oracle_uniqueness_freezes()
    records = {r.short_id: r for r in enumerate_semantic_lanes()}
    assert records["C04"].semantic_claims[0].status == "UNSUPPORTED"
    assert records["C09"].semantic_claims[1].claim_id == "C09-CL2"
    assert records["C09"].semantic_claims[1].status == "UNVERIFIABLE"


def test_five_action_is_not_l1_object() -> None:
    doc = build_protocol_freeze_document()
    forbidden = set(doc["model_output_schema"]["not_l1_object"])
    assert forbidden == {
        "ACCEPT",
        "REVISE_FROM_EXISTING_EVIDENCE",
        "RETRIEVE_MISSING_EVIDENCE",
        "CLARIFY",
        "REFUSE",
    }
    assert doc["primary_metric"] == MeasurementLayer.L1_MODEL_SEMANTIC_CAPABILITY.value


def test_model_inputs_have_zero_oracle_leakage() -> None:
    suite = load_frozen_suite()
    requests = build_eligible_model_requests()
    assert len(requests) == NEW_SEMANTIC_DENOMINATOR
    assert oracle_leakage_count(requests) == 0
    for req in requests:
        assert_no_oracle_leakage(req.wire_payload())
    for case in suite.cases:
        if short_case_id(str(case["case_id"])) not in SEMANTIC_CASE_SHORT_IDS:
            continue
        payload = build_model_input(case)
        assert "deterministic_context" not in payload
        assert "known_conflict" not in json.dumps(payload)


def test_adapter_profile_thinking_off_no_http() -> None:
    adapter = make_profile_adapter()
    assert isinstance(adapter, OpenAICompatibleAdapter)
    assert ADAPTER_CLASS is OpenAICompatibleAdapter
    assert adapter.model == MODEL_CONFIG["primary_model"]
    assert adapter.timeout_seconds == MODEL_CONFIG["timeout_seconds"]
    dry = DryRunSemanticAdapter(adapter)
    with pytest.raises(LmStudioForbidden):
        dry.complete(messages=[{"role": "user", "content": "x"}])
    with pytest.raises(LmStudioForbidden):
        request_lm_studio()


def test_timeout_and_parse_failure_remain_in_denominator() -> None:
    assert TIMEOUT_REMAINS_IN_DENOMINATOR is True
    assert PARSE_FAILURE_REMAINS_IN_DENOMINATOR is True
    lane = next(r for r in enumerate_semantic_lanes() if r.semantic_eligible)
    for kind in (ObservationKind.TIMEOUT, ObservationKind.PARSE_FAILURE):
        verdict = score_l1_observation(lane=lane, observation_kind=kind)
        assert verdict is ModelCapabilityResult.MODEL_CAPABILITY_FAIL
        assert lane.in_l1_denominator is True


def test_hidden_recovery_cannot_upgrade_l1() -> None:
    assert HIDDEN_RECOVERY_CANNOT_UPGRADE_L1 is True
    lane = next(r for r in enumerate_semantic_lanes() if r.short_id == "C01")
    wrong = {c.claim_id: "UNSUPPORTED" for c in lane.semantic_claims}
    verdict = score_l1_observation(
        lane=lane,
        observation_kind=ObservationKind.STRUCTURED_JSON,
        observed_statuses=wrong,
        hidden_recovery_success=True,
    )
    assert verdict is ModelCapabilityResult.MODEL_CAPABILITY_FAIL


def test_exact_claim_status_pass_and_parse_helper() -> None:
    lane = next(r for r in enumerate_semantic_lanes() if r.short_id == "C03")
    exact = {c.claim_id: c.status for c in lane.semantic_claims}
    assert (
        score_l1_observation(
            lane=lane,
            observation_kind=ObservationKind.STRUCTURED_JSON,
            observed_statuses=exact,
        )
        is ModelCapabilityResult.MODEL_CAPABILITY_PASS
    )
    parsed = parse_claim_status_payload(
        json.dumps(
            {
                "claims": [
                    {"claim_id": "C03-CL1", "status": "SUPPORTED", "evidence_refs": ["E1"]},
                    {
                        "claim_id": "C03-CL2",
                        "status": "UNSUPPORTED",
                        "evidence_refs": ["E1"],
                    },
                ]
            }
        )
    )
    assert parsed == exact
    assert parse_claim_status_payload("not-json") is ObservationKind.PARSE_FAILURE


def test_p2_r3_historical_artifact_untouched() -> None:
    assert P2_R3_PATH.is_file()
    assert file_sha256(P2_R3_PATH) == P2_R3_HISTORICAL_ARTIFACT_SHA256
    assert p2_r3_historical_artifact_diff() == 0


def test_backend_app_diff_vs_post_61_is_zero() -> None:
    changed = subprocess.check_output(
        ["git", "diff", "--name-only", POST_61_MASTER_SHA, "--", "backend/app"],
        cwd=REPO_ROOT,
        text=True,
    ).strip()
    assert changed == ""


def test_formal_result_artifact_absent_and_write_forbidden() -> None:
    assert formal_result_artifact_present() is False
    assert not FORMAL_RESULT_ARTIFACT_PATH.exists()
    with pytest.raises(FormalP3ArtifactForbidden):
        write_formal_p3_result({"x": 1})


def test_lane_a_b_match_and_full_regression_gates() -> None:
    payload = run_mock_lane_a_and_b()
    assert payload["gates"]["SEMANTIC_DENOMINATOR_LANE_A"] == 7
    assert payload["gates"]["SEMANTIC_DENOMINATOR_LANE_B"] == 7
    assert payload["gates"]["LM_STUDIO_REQUESTS"] == 0
    report = regression_gate_report()
    assert report["P3_CONSTRUCT_VALIDITY"] == "PASS"
    assert report["P3_SEMANTIC_PROTOCOL_REFROZEN"] == "YES"
    assert report["P3_EXECUTION_CONTRACT_READY"] == "YES"
    assert report["P3_REAL_RUN_READY"] == "YES"
    assert report["NEW_SEMANTIC_DENOMINATOR"] == 7
    assert report["SCORING_POLICY"] == "EXACT"
    assert report["backend_app_diff_vs_post_61"] == 0
    assert report["P2_R3_HISTORICAL_ARTIFACT_DIFF"] == 0
    assert report["FORMAL_RESULT_ARTIFACT_PRESENT"] is False


def test_c07_expected_calls_zero() -> None:
    c07 = next(r for r in enumerate_semantic_lanes() if r.short_id == "C07")
    assert isinstance(c07, CaseLaneRecord)
    assert c07.expected_semantic_calls == 0
    assert c07.semantic_claims == ()
    assert c07.lane == "OWNER_ABSENT"
