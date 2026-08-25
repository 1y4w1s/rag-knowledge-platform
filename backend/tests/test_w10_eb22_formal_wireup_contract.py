"""W10 E-B22 — Formal Wireup Contract tests (deterministic · zero LLM)."""

from __future__ import annotations

from copy import deepcopy

import pytest

from tests.w10_eb17_binding_gate import BindingPolicy
from tests.w10_eb2_generation_observation_contract import (
    ARTIFACT_SCHEMA_VERSION as EB2_SCHEMA,
    PROTOCOL_VERSION as EB2_PROTOCOL,
    RESERVED_RESULT_PATH,
    RUNNER_ID,
    SUITE_ID,
)
from tests.w10_eb22_formal_wireup_contract import (
    E_B_FORMAL_READY,
    FORMAL_WIREUP_DESIGNED,
    FORMAL_WIREUP_IMPLEMENTED,
    FORMAL_WIREUP_INVALID_REASON_CODES,
    L_SCORE_ARTIFACT_KIND,
    L_SCORE_PROTOCOL_VERSION,
    MAY_ENTER_FORMAL_OBSERVATION_WINDOW,
    PARENT_OBSERVATION_PROTOCOL,
    FormalWireupError,
    attempt_formal_compose,
    build_l_obs_skeleton,
    build_l_score_companion,
    compose_l_obs,
    compose_l_score,
    readiness_summary,
    remaining_blockers,
    sample_scorer_result_for_wireup,
    validate_bp_isolation,
    validate_compose_pair,
    validate_gold_after_hash_alignment,
    validate_l_obs_shape,
    validate_l_score_shape,
)


def test_gates_wireup_implemented_formal_still_no() -> None:
    summary = readiness_summary()
    assert summary["FORMAL_WIREUP_DESIGNED"] == "YES"
    assert summary["FORMAL_WIREUP_IMPLEMENTED"] == "YES"
    assert summary["E-B_FORMAL_READY"] == "NO"
    assert summary["MAY_ENTER_FORMAL_OBSERVATION_WINDOW"] == "NO"
    assert summary["claims"]["formal_wireup_contract_implemented"] is True
    assert summary["claims"]["formal_observation"] is False
    assert summary["claims"]["product_faithfulness_proven"] is False
    assert summary["claims"]["reserved_result_written"] is False
    assert FORMAL_WIREUP_IMPLEMENTED == "YES"
    assert FORMAL_WIREUP_DESIGNED == "YES"
    assert E_B_FORMAL_READY == "NO"
    assert MAY_ENTER_FORMAL_OBSERVATION_WINDOW == "NO"
    assert not RESERVED_RESULT_PATH.exists()


def test_remaining_blockers_wireup_implemented_tests_only() -> None:
    blockers = {b["id"]: b for b in remaining_blockers()}
    assert blockers["FORMAL_WIREUP"]["status"] == "IMPLEMENTED_TESTS_ONLY"
    assert blockers["GATE"]["status"] == "NO"
    assert blockers["AG-3"]["status"] == "PARTIAL"


def test_l_obs_schema_valid() -> None:
    l_obs = build_l_obs_skeleton(
        run_id="WIREUP_TEST_run_l_obs",
        base_sha="a" * 40,
        scorer_projection=[
            {
                "case_id": "C01-fully-supported-exact",
                "t2_status": "OBSERVED_SLOT",
                "t3_status": "OBSERVED_SLOT",
            }
        ],
    )
    validate_l_obs_shape(l_obs)
    assert l_obs["protocol_version"] == EB2_PROTOCOL
    assert l_obs["artifact_kind"] == "FORMAL_OBSERVATION_RESULT"
    assert l_obs["measurement_validity"]["measurement_valid"] is False
    assert "FORMAL_GATE_LOCKED" in l_obs["measurement_validity"]["invalid_reasons"]
    assert "t2" not in l_obs
    assert "unsupported_rate" not in l_obs
    case0 = l_obs["per_case_observation"][0]
    assert "t2" not in case0
    assert "unsupported_rate" not in case0


def test_l_score_schema_valid() -> None:
    scorer = sample_scorer_result_for_wireup()
    l_score = build_l_score_companion(
        scorer_result=scorer,
        parent_run_id="WIREUP_TEST_run_pair",
        parent_base_sha="b" * 40,
        binding_policy=BindingPolicy.BP_A,
    )
    validate_l_score_shape(l_score)
    assert l_score["protocol_version"] == L_SCORE_PROTOCOL_VERSION
    assert l_score["artifact_kind"] == L_SCORE_ARTIFACT_KIND
    assert l_score["parent_observation_protocol"] == PARENT_OBSERVATION_PROTOCOL
    assert l_score["formal_measurement"] is False
    assert l_score["implementation_only"] is True
    assert "cases" in l_score and l_score["cases"]
    assert "t2" in l_score and "t3" in l_score
    assert "binding_verdict" in l_score
    assert "honesty" in l_score


def test_run_id_mismatch_rejected() -> None:
    l_obs = build_l_obs_skeleton(run_id="run-A", base_sha="c" * 40)
    l_score = build_l_score_companion(
        scorer_result=sample_scorer_result_for_wireup(),
        parent_run_id="run-B",
        parent_base_sha="c" * 40,
    )
    with pytest.raises(FormalWireupError, match="SCORER_RUN_ID_MISMATCH"):
        validate_compose_pair(l_obs, l_score)


def test_base_sha_mismatch_rejected() -> None:
    l_obs = build_l_obs_skeleton(run_id="run-same", base_sha="d" * 40)
    l_score = build_l_score_companion(
        scorer_result=sample_scorer_result_for_wireup(),
        parent_run_id="run-same",
        parent_base_sha="e" * 40,
    )
    with pytest.raises(FormalWireupError, match="SCORER_BASE_SHA_MISMATCH"):
        validate_compose_pair(l_obs, l_score)


def test_formal_gate_locked_rejected() -> None:
    with pytest.raises(FormalWireupError, match="FORMAL_GATE_LOCKED"):
        compose_l_obs(run_id="x", base_sha="f" * 40)
    with pytest.raises(FormalWireupError, match="FORMAL_GATE_LOCKED"):
        compose_l_score(
            scorer_result=sample_scorer_result_for_wireup(),
            parent_run_id="x",
            parent_base_sha="f" * 40,
        )

    blocked_obs = attempt_formal_compose(target="l_obs", run_id="x", base_sha="f" * 40)
    assert blocked_obs["status"] == "blocked"
    assert blocked_obs["invalid_reason"] == "FORMAL_GATE_LOCKED"
    assert blocked_obs["artifact"] is None

    blocked_score = attempt_formal_compose(
        target="l_score",
        scorer_result=sample_scorer_result_for_wireup(),
        parent_run_id="x",
        parent_base_sha="f" * 40,
    )
    assert blocked_score["status"] == "blocked"
    assert blocked_score["artifact"] is None
    assert not RESERVED_RESULT_PATH.exists()


def test_gold_after_hash_mismatch_rejected() -> None:
    with pytest.raises(FormalWireupError, match="GOLD_AFTER_HASH_MISMATCH"):
        validate_gold_after_hash_alignment(
            after_content_hash="aa" * 32,
            gold_content_sha256="bb" * 32,
        )
    with pytest.raises(FormalWireupError, match="GOLD_AFTER_HASH_MISMATCH"):
        validate_gold_after_hash_alignment(
            after_content_hash=None,
            gold_content_sha256="cc" * 32,
        )
    # aligned (incl. sha256: prefix normalize)
    validate_gold_after_hash_alignment(
        after_content_hash="sha256:" + ("dd" * 32),
        gold_content_sha256="dd" * 32,
    )


def test_bp_b_cannot_claim_product_faithfulness() -> None:
    with pytest.raises(FormalWireupError, match="BP_POLICY_VIOLATION"):
        validate_bp_isolation(
            binding_policy=BindingPolicy.BP_B,
            honesty={"product_faithfulness_proven": True},
            t2_status="OBSERVED_SLOT",
            t3_status="OBSERVED_SLOT",
        )


def test_bp_c_cannot_score_t2_t3() -> None:
    with pytest.raises(FormalWireupError, match="BP_POLICY_VIOLATION"):
        validate_bp_isolation(
            binding_policy=BindingPolicy.BP_C,
            honesty={"product_faithfulness_proven": False},
            t2_status="OBSERVED_SLOT",
            t3_status="NOT_APPLICABLE",
        )
    # BP-C with non-observed statuses is fine
    validate_bp_isolation(
        binding_policy=BindingPolicy.BP_C,
        honesty={"product_faithfulness_proven": False},
        t2_status="NOT_APPLICABLE",
        t3_status="NOT_APPLICABLE",
    )


def test_missing_companion_rejected() -> None:
    l_obs = build_l_obs_skeleton(
        run_id="run-companion",
        base_sha="1" * 40,
        targets_measured=("T2", "T3"),
    )
    with pytest.raises(FormalWireupError, match="SCORER_COMPANION_MISSING"):
        validate_compose_pair(l_obs, None, require_companion=True)


def test_forbidden_keys_rejected() -> None:
    l_obs = build_l_obs_skeleton(run_id="run-forbid", base_sha="2" * 40)
    bad = deepcopy(l_obs)
    bad["unsupported_rate"] = 0.5
    with pytest.raises(FormalWireupError, match="forbidden"):
        validate_l_obs_shape(bad)

    bad_case = deepcopy(l_obs)
    bad_case["per_case_observation"][0]["t2"] = {"unsupported_rate": 0.1}
    with pytest.raises(FormalWireupError, match="forbidden|must not live"):
        validate_l_obs_shape(bad_case)

    bad_notes = deepcopy(l_obs)
    bad_notes["notes"] = "suite unsupported_rate=0.12 stuffed here"
    with pytest.raises(FormalWireupError, match="rates"):
        validate_l_obs_shape(bad_notes)

    l_score = build_l_score_companion(
        scorer_result=sample_scorer_result_for_wireup(),
        parent_run_id="run-forbid",
        parent_base_sha="2" * 40,
    )
    bad_score = deepcopy(l_score)
    bad_score["llm_judge"] = True
    with pytest.raises(FormalWireupError, match="forbidden"):
        validate_l_score_shape(bad_score)

    # formal_measurement=true while gate NO
    bad_formal = deepcopy(l_score)
    bad_formal["formal_measurement"] = True
    bad_formal["implementation_only"] = False
    with pytest.raises(FormalWireupError, match="FORMAL_GATE_LOCKED"):
        validate_l_score_shape(bad_formal)


def test_eb2_identity_unchanged() -> None:
    summary = readiness_summary()
    identity = summary["eb2_identity"]
    assert identity["protocol_version"] == EB2_PROTOCOL
    assert identity["protocol_version"] == "w10_eb2_generation_observation_v1"
    assert identity["artifact_schema_version"] == EB2_SCHEMA
    assert identity["suite_id"] == SUITE_ID
    assert identity["runner_id"] == RUNNER_ID
    assert PARENT_OBSERVATION_PROTOCOL == EB2_PROTOCOL

    l_obs = build_l_obs_skeleton(run_id="id-check", base_sha="3" * 40)
    assert l_obs["protocol_version"] == "w10_eb2_generation_observation_v1"
    assert l_obs["artifact_schema_version"] == "w10-eb2-generation-observation-v1"


def test_aligned_pair_and_bp_a_candidate_ok() -> None:
    run_id = "run-aligned"
    base_sha = "4" * 40
    l_obs = build_l_obs_skeleton(run_id=run_id, base_sha=base_sha)
    l_score = build_l_score_companion(
        scorer_result=sample_scorer_result_for_wireup(
            binding_policy=BindingPolicy.BP_A
        ),
        parent_run_id=run_id,
        parent_base_sha=base_sha,
        binding_policy=BindingPolicy.BP_A,
    )
    validate_compose_pair(l_obs, l_score)
    validate_bp_isolation(
        binding_policy=BindingPolicy.BP_A,
        honesty={"product_faithfulness_proven": False},
        t2_status="OBSERVED_SLOT",
        t3_status="OBSERVED_SLOT",
        after_source="compatibility_materialization_author_owned",
    )
    # Compat pack cannot claim product faithfulness
    with pytest.raises(FormalWireupError, match="COMPAT_PACK_AS_PRODUCT_FAITHFULNESS"):
        validate_bp_isolation(
            binding_policy=BindingPolicy.BP_A,
            honesty={"product_faithfulness_proven": True},
            after_source="compatibility_materialization_author_owned",
        )


def test_invalid_reason_allowlist_frozen() -> None:
    expected = {
        "FORMAL_GATE_LOCKED",
        "BINDING_INCOMPATIBLE",
        "GOLD_AFTER_HASH_MISMATCH",
        "SCORER_COMPANION_MISSING",
        "SCORER_RUN_ID_MISMATCH",
        "SCORER_BASE_SHA_MISMATCH",
        "BP_POLICY_VIOLATION",
        "WIRING_ONLY_POINTER_AS_PRODUCT",
        "COMPAT_PACK_AS_PRODUCT_FAITHFULNESS",
        "LLM_CALLED_FREEZE_VIOLATION",
    }
    assert FORMAL_WIREUP_INVALID_REASON_CODES == expected
