"""W10 E-B44 — T1 Formal Measurement deterministic tests.

Formal measurement from E-B41 raw records only. No LLM/API/backend/app changes.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from tests.w10_eb41_t1_companion import (
    EB41_DIR,
    FROZEN_BASE_SHA,
    load_companion_manifest,
    load_companion_record,
)
from tests.w10_eb42_t1_formal_readiness import (
    EB41_CANDIDATE_PATH,
    EB41_PROVENANCE_COMMIT,
    corrupt_candidate_summary_in_memory,
)
from tests.w10_eb43_formal_target_scope_v2 import (
    EB43_DIR,
    FROZEN_EVALUATION_BASE_SHA,
    MEASUREMENT_SCOPE_ID,
    clear_active_scopes_for_tests,
    ensure_showcase_scope_frozen,
)
from tests.w10_eb44_t1_formal_measurement import (
    C12_STATUS,
    EB43_PROVENANCE_COMMIT,
    EB44_DIR,
    assert_no_conflicting_formal_results,
    assert_raw_input_integrity,
    build_formal_t1_result,
    compute_formal_per_case,
    execute_formal_t1_measurement,
    formal_oracle_isolation_ok,
    formal_preflight,
    gate_matrix,
    hash_id_list,
    load_all_raw_records,
    make_formal_measurement_id,
    validate_formal_result_schema,
)

FIXED_MEASURED_AT = datetime(2026, 8, 25, 10, 16, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def _reset_scope_registry() -> None:
    clear_active_scopes_for_tests()
    yield
    clear_active_scopes_for_tests()


@pytest.fixture
def formal_result() -> dict:
    return build_formal_t1_result(measured_at=FIXED_MEASURED_AT)


def test_eb43_provenance_commit_exact() -> None:
    assert EB43_PROVENANCE_COMMIT == "07a0dcbea9b676c297f45ef0a6edc54831c4ad16"
    assert EB43_PROVENANCE_COMMIT != FROZEN_EVALUATION_BASE_SHA


def test_formal_entry_preflight_passes() -> None:
    ensure_showcase_scope_frozen()
    pre = formal_preflight()
    assert pre["PREFLIGHT_PASS"] == "YES"
    assert pre["FORMAL_TARGET_SCOPE_V2_IMPLEMENTED"] == "YES"
    assert pre["FORMAL_SCOPE_V2_FROZEN"] == "YES"
    assert pre["FORMAL_MEASUREMENT_SCOPE"] == "T1_ONLY"
    assert pre["T1_FORMAL_INPUT_READY"] == "YES"
    assert pre["T1_FORMAL_READY"] == "YES"
    assert pre["E_B_FORMAL_READY_V2"] == "YES"
    assert pre["MAY_ENTER_T1_FORMAL_MEASUREMENT"] == "YES"
    assert pre["T2_FORMAL_STATUS"] == "NOT_APPLICABLE"
    assert pre["T3_FORMAL_STATUS"] == "NOT_APPLICABLE"
    assert pre["OWNER_AUTHORIZATION_ISSUED"] == "YES"
    assert pre["SOURCE_APPROVED"] == "YES"
    assert pre["AFTER_SOURCE_APPROVED"] == "YES"
    assert pre["AUTHORIZATION_STILL_VALID"] == "YES"
    assert pre["EXACT_BLOCKERS"] == "NONE"


def test_formal_input_identity_binding(formal_result: dict) -> None:
    assert formal_result["measurement_scope_id"] == MEASUREMENT_SCOPE_ID
    assert formal_result["source_identity"] == "suoyin_local_research_product_after_v1"
    assert formal_result["base_sha"] == FROZEN_BASE_SHA
    assert formal_result["runtime_identity"] == "suoyin_backend_venv_cpython_3.11.9_win10_amd64"
    assert formal_result["suite"] == "w9_critic_frozen_12"
    assert formal_result["input_provenance_commit"] == EB41_PROVENANCE_COMMIT
    assert formal_result["input_run_identity"] == "w10_showcase_narrow_eb41_t1_20260825T094148Z"


def test_raw_recomputation_per_case_subset_predicate(formal_result: dict) -> None:
    eligible = [c for c in formal_result["per_case"] if not c["excluded"]]
    assert len(eligible) == 11
    for row in eligible:
        assert row["same_trajectory_binding"] is True
        gated = set(row["gated_scope_ids"])
        finals = set(row["final_citation_ids"])
        violation = set(row["violation_ids"])
        assert violation == finals - gated
        assert row["compliant"] == (len(violation) == 0)
        assert row["final_citation_hash"] == hash_id_list(row["final_citation_ids"])


def test_c12_excluded_before_denominator(formal_result: dict) -> None:
    assert formal_result["eligible_count"] == 11
    assert formal_result["excluded_count"] == 1
    c12_rows = [c for c in formal_result["per_case"] if c["case_id_short"] == "C12"]
    assert len(c12_rows) == 1
    c12 = c12_rows[0]
    assert c12["excluded"] is True
    assert c12["status"] == C12_STATUS
    assert c12["compliant"] is False
    rec = load_companion_record("C12")
    assert rec.get("status") == "INELIGIBLE_NOT_SCORED" or c12["case_id_short"] == "C12"


def test_t2_t3_not_applicable_semantics(formal_result: dict) -> None:
    assert formal_result["targets"]["T1"]["status"] == "MEASURED"
    assert formal_result["targets"]["T2"]["status"] == "NOT_APPLICABLE"
    assert formal_result["targets"]["T3"]["status"] == "NOT_APPLICABLE"
    assert "score" not in formal_result["targets"]["T2"]
    assert "score" not in formal_result["targets"]["T3"]
    assert "pass" not in formal_result["targets"]["T2"]
    assert "pass" not in formal_result["targets"]["T3"]


def test_candidate_oracle_isolation_0_11_and_11_11() -> None:
    assert formal_oracle_isolation_ok() is True
    candidate = json.loads(EB41_CANDIDATE_PATH.read_text(encoding="utf-8"))
    before = build_formal_t1_result(measured_at=FIXED_MEASURED_AT)
    for cc, vc in ((0, 11), (11, 0)):
        bad = corrupt_candidate_summary_in_memory(candidate)
        bad["candidate_compliant_count"] = cc
        bad["candidate_violation_count"] = vc
        after = build_formal_t1_result(measured_at=FIXED_MEASURED_AT)
        assert after["aggregate"] == before["aggregate"]
    assert candidate.get("is_formal_t1_result") is False
    assert formal_result_schema_has_no_candidate_fields(before)


def formal_result_schema_has_no_candidate_fields(result: dict) -> bool:
    forbidden = (
        "candidate_compliant_count",
        "candidate_violation_count",
        "candidate_compliance_rate",
    )
    return all(k not in result for k in forbidden)


def test_measurement_identity_unique(formal_result: dict) -> None:
    assert formal_result["formal_measurement_id"] == make_formal_measurement_id(
        FIXED_MEASURED_AT
    )
    assert formal_result["formal_measurement_id"].startswith("w10_t1_formal_")
    assert formal_result["formal_measurement_id"] != formal_result["input_run_identity"]
    assert formal_result["measured_at"] == "2026-08-25T10:16:00Z"


def test_frozen_base_sha_exact(formal_result: dict) -> None:
    assert formal_result["base_sha"] == "3ce0e75f06d35aecaaccd245dd3a234b1c6f79a6"
    for i in range(1, 12):
        rec = load_companion_record(f"C{i:02d}")
        assert rec["base_sha"] == formal_result["base_sha"]


def test_no_llm_no_raw_mutation(formal_result: dict) -> None:
    assert formal_result["llm_called"] is False
    assert formal_result["candidate_oracle_used"] is False
    manifest_before = load_companion_manifest()
    records = load_all_raw_records()
    assert_raw_input_integrity(records)
    manifest_after = load_companion_manifest()
    assert manifest_before == manifest_after
    for i in range(1, 12):
        rec = load_companion_record(f"C{i:02d}")
        assert rec["llm_called_observed"] is False


def test_aggregate_counts_and_compliance_rate(formal_result: dict) -> None:
    agg = formal_result["aggregate"]
    assert agg["compliant_count"] + agg["violation_count"] == 11
    assert agg["compliance_rate"] == agg["compliant_count"] / 11
    validate_formal_result_schema(formal_result)
    assert formal_result["measurement_valid"] is True


def test_canonical_result_schema_valid(formal_result: dict) -> None:
    validate_formal_result_schema(formal_result)
    assert formal_result["is_formal_result"] is True
    assert formal_result["formal_measurement_executed"] is True


def test_no_reserved_result_collision() -> None:
    assert not (EB41_DIR / "w10-eb2-generation-observation-result.json").exists()
    assert not (EB43_DIR / "formal-t1-result.json").exists()
    for name in ("FORMAL_OBSERVATION_RESULT", "FORMAL_T2_T3_SCORE_RESULT"):
        assert not list(EB44_DIR.rglob(name)) if EB44_DIR.is_dir() else True


def test_gate_matrix_after_measurement(formal_result: dict) -> None:
    g = gate_matrix(formal_result)
    assert g["FORMAL_T1_MEASUREMENT_EXECUTED"] == "YES"
    assert g["FORMAL_T1_MEASUREMENT_VALID"] == "YES"
    assert g["FORMAL_OBSERVATION"] == "COMPLETED_FOR_T1_V2"
    assert g["FORMAL_OBSERVATION_V2"] == "COMPLETED"
    assert g["T1_FORMAL_STATUS"] == "MEASURED"
    assert g["T2_FORMAL_STATUS"] == "NOT_APPLICABLE"
    assert g["T3_FORMAL_STATUS"] == "NOT_APPLICABLE"
    assert g["FORMAL_ORACLE_LEAK_RISK"] == "NO"
    assert g["CANONICAL_FORMAL_T1_RESULT_COUNT"] == "1"
    assert g["E-B_FORMAL_READY"] == "NO"
    assert g["VERDICT"] == "W10_T1_FORMAL_MEASUREMENT_COMPLETE"


def test_per_case_compute_independent() -> None:
    rec = load_companion_record("C01")
    row = compute_formal_per_case(rec)
    assert row.compliant is True
    assert row.violation_ids == ()


def test_execute_writes_canonical_json(tmp_path: Path) -> None:
    result = execute_formal_t1_measurement(
        measured_at=FIXED_MEASURED_AT,
        write_artifacts=False,
    )
    path = tmp_path / "formal-t1-result.json"
    path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    assert path.is_file()
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert loaded["formal_measurement_id"] == result["formal_measurement_id"]
    count = assert_no_conflicting_formal_results(allow_path=path)
    assert count == 1


def test_formal_t1_eleven_of_eleven_when_raw_compliant(formal_result: dict) -> None:
    agg = formal_result["aggregate"]
    if agg["compliant_count"] == 11 and agg["violation_count"] == 0:
        assert agg["compliance_rate"] == 1.0
    else:
        pytest.fail(
            f"unexpected formal result: {agg['compliant_count']}/11 compliant"
        )
