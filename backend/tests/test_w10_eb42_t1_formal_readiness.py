"""W10 E-B42 — T1 Formal readiness deterministic tests.

No Formal measurement · no Formal result write · no LLM/API/LM Studio · no reacquisition.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.w10_eb40_response_mode_gate import (
    ResponseMode,
    t2_t3_denominator_admits,
)
from tests.w10_eb41_t1_companion import (
    FROZEN_BASE_SHA,
    compute_subset,
    load_companion_manifest,
    load_companion_record,
)
from tests.w10_eb42_t1_formal_readiness import (
    AFTER_SOURCE_APPROVED,
    AUDIT_AS_OF,
    AUTHORIZATION_STILL_VALID,
    EB41_CANDIDATE_PATH,
    EB41_DIR,
    EB41_PROVENANCE_COMMIT,
    FORMAL_OBSERVATION,
    FORMAL_ORACLE_LEAK_RISK,
    FORMAL_TARGET_SCOPE_SEMANTICS,
    FORMAL_TARGET_SCOPING_GAP,
    FORMAL_T1_RESULT_WRITTEN,
    FROZEN_EVALUATION_BASE_SHA,
    GLOBAL_E_B_FORMAL_READY_SEMANTICS,
    L_OBS_T1_ONLY_COMPATIBLE,
    MAY_ENTER_FORMAL_OBSERVATION_WINDOW,
    MAY_ENTER_T1_FORMAL_MEASUREMENT,
    OWNER_AUTHORIZATION_ISSUED,
    SOURCE_APPROVED,
    T1_FORMAL_INPUT_IMMUTABLE,
    T1_FORMAL_INPUT_READY,
    T1_FORMAL_READY,
    T2_FORMAL_STATUS,
    T2_T3_NA_COMPANION_ALLOWED,
    T3_FORMAL_STATUS,
    assert_authorization_still_valid,
    assert_l_obs_t1_only_compose_pair_compatible,
    assert_no_formal_artifacts_created,
    assert_provenance_distinct_from_freeze,
    candidate_vs_raw_separation_ok,
    corrupt_candidate_summary_in_memory,
    formal_t1_compute_from_raw_record,
    formal_t1_suite_from_raw_records,
    future_formal_t1_result_schema_checklist,
    gate_matrix,
    verify_record_hashes_against_manifest,
    E_B_FORMAL_READY,
)


def test_eb41_provenance_distinct_from_frozen_base() -> None:
    assert_provenance_distinct_from_freeze()
    assert EB41_PROVENANCE_COMMIT != FROZEN_EVALUATION_BASE_SHA
    assert FROZEN_EVALUATION_BASE_SHA == FROZEN_BASE_SHA
    assert EB41_PROVENANCE_COMMIT.startswith("2951914")


def test_raw_records_integrity_and_identity() -> None:
    verified = verify_record_hashes_against_manifest()
    assert len(verified) == 11
    manifest = load_companion_manifest()
    assert manifest["base_sha"] == FROZEN_BASE_SHA
    assert manifest["source_identity"] == "suoyin_local_research_product_after_v1"
    assert manifest["capture_mode"] == "product_stream"
    assert (
        manifest["runtime_identity"]
        == "suoyin_backend_venv_cpython_3.11.9_win10_amd64"
    )


def test_same_trajectory_binding_on_all_eligible() -> None:
    for i in range(1, 12):
        rec = load_companion_record(f"C{i:02d}")
        assert rec["same_trajectory_binding"] is True
        assert rec["T1_SAME_EXECUTION_BINDING_REQUIRED"] is True
        assert "eb38" not in str(rec.get("final_citation_source_kind") or "")


def test_subset_predicate_contract() -> None:
    holds, unique, out = compute_subset(["A", "a", "X"], ["a", "b"])
    assert holds is False
    assert unique == ("a", "x")
    assert out == ("x",)
    holds2, _, out2 = compute_subset(["a"], ["a", "b"])
    assert holds2 is True
    assert out2 == ()
    holds3, _, _ = compute_subset([], [])
    assert holds3 is True


def test_candidate_summary_not_used_as_oracle() -> None:
    assert candidate_vs_raw_separation_ok() is True
    candidate = json.loads(EB41_CANDIDATE_PATH.read_text(encoding="utf-8"))
    corrupted = corrupt_candidate_summary_in_memory(candidate)
    assert corrupted["candidate_compliant_count"] == 0
    raw = formal_t1_suite_from_raw_records()
    assert raw["compliant_count"] == 11
    assert raw["is_formal_result"] is False
    assert FORMAL_ORACLE_LEAK_RISK == "NO"


def test_c12_excluded_from_formal_intent_denom() -> None:
    c12 = formal_t1_compute_from_raw_record(load_companion_record("C12"))
    assert c12.excluded is True
    assert c12.compliant is False
    suite = formal_t1_suite_from_raw_records()
    assert suite["eligible_count"] == 11
    assert suite["excluded_count"] == 1


def test_t2_t3_remain_not_applicable() -> None:
    assert T2_FORMAL_STATUS == "NOT_APPLICABLE"
    assert T3_FORMAL_STATUS == "NOT_APPLICABLE"
    for i in range(1, 12):
        rec = load_companion_record(f"C{i:02d}")
        assert rec["response_mode"] == "DEGRADED"
        assert t2_t3_denominator_admits(ResponseMode.DEGRADED) is False


def test_degraded_does_not_auto_exclude_t1() -> None:
    for i in range(1, 12):
        rec = load_companion_record(f"C{i:02d}")
        assert rec["response_mode"] == "DEGRADED"
        row = formal_t1_compute_from_raw_record(rec)
        assert row.excluded is False


def test_no_formal_artifact_created() -> None:
    assert_no_formal_artifacts_created()
    assert FORMAL_T1_RESULT_WRITTEN == "NO"
    assert FORMAL_OBSERVATION == "NOT_STARTED"
    reserved = Path("backend/tests/fixtures") / "l4_critic"
    # E-B2 reserved result must remain absent under research dirs
    assert not (
        EB41_DIR / "w10-eb2-generation-observation-result.json"
    ).exists()


def test_authorization_still_valid() -> None:
    assert_authorization_still_valid(as_of=AUDIT_AS_OF)
    assert OWNER_AUTHORIZATION_ISSUED == "YES"
    assert SOURCE_APPROVED == "YES"
    assert AFTER_SOURCE_APPROVED == "YES"
    assert AUTHORIZATION_STILL_VALID == "YES"


def test_source_base_runtime_identity_exact() -> None:
    manifest = load_companion_manifest()
    assert manifest["base_sha"] == "3ce0e75f06d35aecaaccd245dd3a234b1c6f79a6"
    assert manifest["source_identity"] == "suoyin_local_research_product_after_v1"
    assert manifest["capture_mode"] == "product_stream"
    assert (
        manifest["runtime_identity"]
        == "suoyin_backend_venv_cpython_3.11.9_win10_amd64"
    )
    assert manifest["companion_run"].startswith("w10_showcase_narrow_")


def test_no_llm_on_records() -> None:
    for i in range(1, 12):
        rec = load_companion_record(f"C{i:02d}")
        assert rec["llm_called"] is False
        assert rec["llm_called_observed"] is False


def test_l_obs_t1_only_wireup_compatible() -> None:
    assert_l_obs_t1_only_compose_pair_compatible()
    assert L_OBS_T1_ONLY_COMPATIBLE == "YES"
    assert T2_T3_NA_COMPANION_ALLOWED == "YES"


def test_target_scope_semantics_ambiguous_blocks_t1_formal() -> None:
    assert FORMAL_TARGET_SCOPE_SEMANTICS == "AMBIGUOUS"
    assert FORMAL_TARGET_SCOPING_GAP == "YES"
    assert GLOBAL_E_B_FORMAL_READY_SEMANTICS == "UNDEFINED"
    assert T1_FORMAL_INPUT_READY == "YES"
    assert T1_FORMAL_INPUT_IMMUTABLE == "YES"
    assert T1_FORMAL_READY == "NO"
    assert MAY_ENTER_T1_FORMAL_MEASUREMENT == "NO"
    assert E_B_FORMAL_READY == "NO"
    assert MAY_ENTER_FORMAL_OBSERVATION_WINDOW == "NO"


def test_future_schema_checklist_only_no_write() -> None:
    checklist = future_formal_t1_result_schema_checklist()
    assert checklist["measurement_scope=T1_ONLY"] is True
    assert checklist["T2_status=NOT_APPLICABLE"] is True
    # Must not materialize Formal result
    assert_no_formal_artifacts_created()


def test_gate_matrix_verdict() -> None:
    g = gate_matrix()
    assert g["VERDICT"] == "BLOCKED_PENDING_FORMAL_TARGET_SCOPING_REPAIR"
    assert g["T1_FORMAL_READY"] == "NO"
    assert g["FORMAL_OBSERVATION"] == "NOT_STARTED"
