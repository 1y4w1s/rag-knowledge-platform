"""W10 E-B43 — Formal Target Scope v2 deterministic tests.

No Formal Measurement · no Formal result write · no LLM/API · no backend/app.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.w10_eb40_response_mode_gate import (
    ResponseMode,
    refuse_perfect_score_for_non_answer,
    t2_t3_denominator_admits,
)
from tests.w10_eb41_t1_companion import load_companion_record
from tests.w10_eb42_t1_formal_readiness import (
    FORMAL_TARGET_SCOPE_SEMANTICS,
    GLOBAL_E_B_FORMAL_READY_SEMANTICS,
)
from tests.w10_eb43_formal_target_scope_v2 import (
    EB42_PROVENANCE_COMMIT,
    FORMAL_OBSERVATION,
    FORMAL_TARGET_SCOPE_SEMANTICS_HISTORICAL,
    FORMAL_T1_RESULT_WRITTEN,
    FROZEN_EVALUATION_BASE_SHA,
    GLOBAL_E_B_FORMAL_READY_SEMANTICS_HISTORICAL,
    MEASUREMENT_SCOPE_ID,
    SCOPE_VERSION,
    FormalMeasurementScope,
    FormalScopeV2Error,
    assert_no_formal_result_written,
    build_formal_result_v2_dry_run,
    clear_active_scopes_for_tests,
    ensure_showcase_scope_frozen,
    freeze_formal_measurement_scope,
    gate_matrix,
    measurement_scope_label,
    na_target_contribution,
    oracle_isolation_ok,
    target_formal_ready,
    writer_compatibility_report,
    E_B_FORMAL_READY,
)


@pytest.fixture(autouse=True)
def _reset_scope_registry() -> None:
    clear_active_scopes_for_tests()
    yield
    clear_active_scopes_for_tests()


def test_historical_eb42_ambiguity_preserved() -> None:
    assert FORMAL_TARGET_SCOPE_SEMANTICS == "AMBIGUOUS"
    assert FORMAL_TARGET_SCOPE_SEMANTICS_HISTORICAL == "AMBIGUOUS"
    assert GLOBAL_E_B_FORMAL_READY_SEMANTICS == "UNDEFINED"
    assert GLOBAL_E_B_FORMAL_READY_SEMANTICS_HISTORICAL == "UNDEFINED"
    # Must NOT rewrite E-B42 to TARGET_SPECIFIC_ALLOWED
    assert FORMAL_TARGET_SCOPE_SEMANTICS_HISTORICAL != "TARGET_SPECIFIC_ALLOWED"
    assert E_B_FORMAL_READY == "NO"


def test_formal_scope_v2_freezes_t1_only() -> None:
    scope = ensure_showcase_scope_frozen()
    assert scope.scope_version == SCOPE_VERSION
    assert scope.measurement_scope_id == MEASUREMENT_SCOPE_ID
    assert scope.authorized_targets == frozenset({"T1"})
    assert scope.not_applicable_targets == frozenset({"T2", "T3"})
    assert measurement_scope_label(scope) == "T1_ONLY"
    assert scope.suite_id == "w9_critic_frozen_12"
    assert scope.case_scope == tuple(f"C{i:02d}" for i in range(1, 12))
    assert scope.c12_status == "INELIGIBLE_NOT_SCORED"
    assert scope.frozen_by == "suoyin_project_owner"
    assert scope.base_sha == FROZEN_EVALUATION_BASE_SHA


def test_t2_t3_na_never_converted_to_pass() -> None:
    for target in ("T2", "T3"):
        row = na_target_contribution(target)
        assert row["status"] == "NOT_APPLICABLE"
        assert row["pass"] is False
        assert row["fail"] is False
        assert row["perfect"] is False
        assert row["equals_pass"] is False
        assert row["equals_100_percent"] is False
        assert row["equals_zero_denominator_success"] is False
        assert row["score"] is None
    with pytest.raises(Exception):
        refuse_perfect_score_for_non_answer(ResponseMode.DEGRADED)


def test_na_targets_excluded_from_denominator() -> None:
    for target in ("T2", "T3"):
        row = na_target_contribution(target)
        assert row["in_denominator"] is False
        assert row["in_aggregate"] is False
    assert t2_t3_denominator_admits(ResponseMode.DEGRADED) is False
    scope = ensure_showcase_scope_frozen()
    dry = build_formal_result_v2_dry_run(scope=scope)
    # Aggregate is T1-only; T2/T3 not scored into denom
    assert dry["targets"]["T2"] == "NOT_APPLICABLE"
    assert dry["targets"]["T3"] == "NOT_APPLICABLE"
    assert dry["targets"]["T1"] == "MEASURED"


def test_t1_input_from_eb41_raw_records() -> None:
    scope = ensure_showcase_scope_frozen()
    dry = build_formal_result_v2_dry_run(scope=scope)
    assert dry["is_formal_result"] is False
    assert dry["formal_measurement_executed"] is False
    assert dry["eligible_count"] == 11
    assert dry["source_identity"] == "suoyin_local_research_product_after_v1"
    assert dry["base_sha"] == FROZEN_EVALUATION_BASE_SHA
    assert len(dry["per_case"]) == 11
    for row in dry["per_case"]:
        assert "gated_scope_ids" in row or "gated_scope_hash" in row
        assert "final_citation_ids" in row
        assert "compliant" in row


def test_candidate_aggregate_cannot_act_as_oracle() -> None:
    candidate = json.loads(
        (
            Path(__file__).resolve().parents[2]
            / "docs"
            / "research"
            / "w10-eb41-t1-companion-reacquisition"
            / "t1-candidate-evaluation.json"
        ).read_text(encoding="utf-8")
    )
    assert candidate.get("is_formal_t1_result") is False
    assert candidate.get("candidate_compliant_count") == 11
    dry = build_formal_result_v2_dry_run()
    # Dry-run must not copy candidate as Formal verdict
    assert dry["is_formal_result"] is False
    assert dry.get("candidate_compliant_count") is None
    assert "candidate_compliant_count" not in dry


def test_corrupted_candidate_summary_does_not_alter_t1_recompute() -> None:
    assert oracle_isolation_ok() is True
    before = build_formal_result_v2_dry_run()
    # Recompute again after corruption probe inside oracle_isolation_ok
    after = build_formal_result_v2_dry_run()
    assert after["aggregate"]["compliant_count"] == before["aggregate"]["compliant_count"]
    assert after["aggregate"]["compliant_count"] == 11


def test_c12_remains_excluded() -> None:
    dry = build_formal_result_v2_dry_run()
    assert dry["excluded_count"] == 1
    assert dry["eligible_count"] == 11
    shorts = {c["case_id_short"] for c in dry["per_case"]}
    assert "C12" not in shorts
    c12 = load_companion_record("C12")
    assert c12.get("status") == "INELIGIBLE_NOT_SCORED" or c12.get(
        "case_id_short"
    ) == "C12"


def test_degraded_valid_for_t1_na_for_t2_t3() -> None:
    scope = ensure_showcase_scope_frozen()
    for i in range(1, 12):
        rec = load_companion_record(f"C{i:02d}")
        assert rec["response_mode"] == "DEGRADED"
    assert target_formal_ready("T1", scope) == "YES"
    assert target_formal_ready("T2", scope) == "NOT_APPLICABLE"
    assert target_formal_ready("T3", scope) == "NOT_APPLICABLE"


def test_authorization_validity_required() -> None:
    g = gate_matrix()
    assert g["AUTHORIZATION_STILL_VALID"] == "YES"
    assert g["OWNER_AUTHORIZATION_ISSUED"] == "YES"
    assert g["SOURCE_APPROVED"] == "YES"
    assert g["AFTER_SOURCE_APPROVED"] == "YES"


def test_exactly_one_active_formal_measurement_scope() -> None:
    ensure_showcase_scope_frozen()
    other = FormalMeasurementScope(
        scope_version=SCOPE_VERSION,
        measurement_scope_id="w10_other_scope_must_fail",
        authorized_targets=frozenset({"T1"}),
        not_applicable_targets=frozenset({"T2", "T3"}),
        excluded_targets=frozenset(),
        suite_id="w9_critic_frozen_12",
        case_scope=tuple(f"C{i:02d}" for i in range(1, 12)),
        source_identity="suoyin_local_research_product_after_v1",
        base_sha=FROZEN_EVALUATION_BASE_SHA,
        runtime_identity="suoyin_backend_venv_cpython_3.11.9_win10_amd64",
        response_mode_policy_ref="w10_eb40_response_mode_gate_v1",
        authorization_ref="docs/research/w10-eb36-human-owner-stamp-issuance/01-approved-owner-stamp.md",
        binding_ref="w10_eb41_t1_companion_v1",
        frozen_by="suoyin_project_owner",
        frozen_at="2026-08-25T11:00:00Z",
    )
    with pytest.raises(FormalScopeV2Error, match="exactly one"):
        freeze_formal_measurement_scope(other)
    # Idempotent same scope ok
    ensure_showcase_scope_frozen()


def test_no_formal_result_written() -> None:
    build_formal_result_v2_dry_run()
    assert_no_formal_result_written()
    assert FORMAL_T1_RESULT_WRITTEN == "NO"
    assert FORMAL_OBSERVATION == "NOT_STARTED"
    assert not (
        Path("docs/research/w10-eb41-t1-companion-reacquisition")
        / "w10-eb2-generation-observation-result.json"
    ).exists()


def test_writer_compatibility_t2_t3_companion_na() -> None:
    scope = ensure_showcase_scope_frozen()
    report = writer_compatibility_report(scope)
    assert report["writer_compatibility_ready"] == "YES"
    assert report["T2_T3_COMPANION_STATUS"] == "NOT_APPLICABLE"
    assert report["FORMAL_T2_T3_SCORE_RESULT_FABRICATED"] == "NO"
    assert report["old_compose_l_obs_unlocked"] == "NO"
    assert report["historical_E_B_FORMAL_READY"] == "NO"


def test_gate_matrix_success_ready_for_t1_formal() -> None:
    g = gate_matrix()
    assert g["eb42_provenance_commit"] == EB42_PROVENANCE_COMMIT
    assert EB42_PROVENANCE_COMMIT != FROZEN_EVALUATION_BASE_SHA
    assert g["FORMAL_TARGET_SCOPE_V2_IMPLEMENTED"] == "YES"
    assert g["FORMAL_SCOPE_V2_FROZEN"] == "YES"
    assert g["FORMAL_MEASUREMENT_SCOPE"] == "T1_ONLY"
    assert g["T1_FORMAL_INPUT_READY"] == "YES"
    assert g["T1_FORMAL_READY"] == "YES"
    assert g["T2_FORMAL_STATUS"] == "NOT_APPLICABLE"
    assert g["T3_FORMAL_STATUS"] == "NOT_APPLICABLE"
    assert g["E_B_FORMAL_READY_V2"] == "YES"
    assert g["MAY_ENTER_T1_FORMAL_MEASUREMENT"] == "YES"
    assert g["MAY_ENTER_T1_FORMAL_MEASUREMENT_V2"] == "YES"
    assert g["E-B_FORMAL_READY"] == "NO"
    assert g["FORMAL_OBSERVATION"] == "NOT_STARTED"
    assert g["EXACT_BLOCKERS"] == "NONE"
    assert g["VERDICT"] == "READY_FOR_T1_FORMAL_MEASUREMENT"
    # Must not claim Formal T1 = 100% (measurement not run)
    dry = build_formal_result_v2_dry_run()
    assert dry["measurement_valid"] is False
    assert dry["formal_measurement_executed"] is False
