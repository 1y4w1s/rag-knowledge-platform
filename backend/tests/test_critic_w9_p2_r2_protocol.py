"""W9 P2-R2 production-path measurement protocol tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.core.config import settings
from app.services.agent.tools.scope import AgentToolScope
from tests.w9_critic_p2_r1_harness import (
    load_frozen_suite,
    score_observation,
    stable_uuid,
)
from tests.w9_critic_p2_r2_protocol import (
    VALIDATION_PATH,
    FinalSafetyScore,
    HarnessMode,
    MeasurementClassification,
    ProductPathFlags,
    _foreign_evidence,
    _scoped_evidence,
    assess_case_product_path_eligibility,
    build_c12_protocol_proof,
    build_tool_scope,
    execute_defense_in_depth_probe,
    execute_production_path_case,
    score_final_output,
    score_production_observation,
    write_validation_artifact,
)

FIXTURES = Path(__file__).parent / "fixtures" / "l4_critic"
CORRECTION_PATH = FIXTURES / "w9-critic-p2-r1-independent-review.json"
HISTORICAL_P2_PATH = FIXTURES / "w9-critic-p2-offline-product.json"
P2B_PATH = FIXTURES / "w9-critic-p2b-c11-remediation.json"
P2_R1_ARTIFACT_PATH = FIXTURES / "w9-critic-p2-r1-offline-product.json"


# ── Task 7A: illegal direct foreign injection → MEASUREMENT_PROTOCOL_INVALID ──


def test_illegal_direct_foreign_injection_is_protocol_invalid() -> None:
    suite = load_frozen_suite()
    case = next(
        item for item in suite.cases if item["case_id"] == "C12-out-of-scope-provenance"
    )
    flags = assess_case_product_path_eligibility(
        case, mode=HarnessMode.DEFENSE_IN_DEPTH_PROBE
    )
    assert flags.direct_foreign_injection is True
    assert flags.product_path_eligible is False


@pytest.mark.asyncio
async def test_defense_in_depth_probe_foreign_citation_fails_final_scorer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    suite = load_frozen_suite()
    case = next(
        item for item in suite.cases if item["case_id"] == "C12-out-of-scope-provenance"
    )
    observed = await execute_defense_in_depth_probe(
        monkeypatch, case, suite.reports["C12-out-of-scope-provenance"]
    )
    score: FinalSafetyScore = observed["final_safety_score"]
    assert observed["mode"] == HarnessMode.DEFENSE_IN_DEPTH_PROBE.value
    assert score.foreign_kb_reference_count >= 1
    assert score.safe_outcome is False
    old_scored = score_observation(
        observed,
        suite.oracle["C12-out-of-scope-provenance"],
        suite.reports["C12-out-of-scope-provenance"],
    )
    assert old_scored["safe_outcome"] is True


# ── Task 7B: correct scoped evidence → eligible ──


def test_scoped_evidence_cases_are_product_path_eligible() -> None:
    suite = load_frozen_suite()
    for case in suite.cases:
        if case["case_id"] == "C12-out-of-scope-provenance":
            continue
        flags = assess_case_product_path_eligibility(
            case, mode=HarnessMode.PRODUCTION_PATH
        )
        assert flags.product_path_eligible is True
        assert _scoped_evidence(case)


@pytest.mark.asyncio
async def test_c01_production_path_executes_and_passes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    suite = load_frozen_suite()
    case = next(item for item in suite.cases if item["case_id"] == "C01-fully-supported-exact")
    observed = await execute_production_path_case(
        monkeypatch, case, suite.reports["C01-fully-supported-exact"]
    )
    scored = score_production_observation(
        observed,
        suite.oracle["C01-fully-supported-exact"],
        suite.reports["C01-fully-supported-exact"],
        case=case,
    )
    assert scored["product_path_eligible"] is True
    assert scored["pass"] is True
    assert isinstance(observed["tool_scope"], AgentToolScope)


# ── Task 7C: real recovery retrieval respects KB scope ──


@pytest.mark.asyncio
async def test_c06_production_recovery_respects_kb_scope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    suite = load_frozen_suite()
    case_id = "C06-required-fact-missing"
    case = next(item for item in suite.cases if item["case_id"] == case_id)
    observed = await execute_production_path_case(
        monkeypatch, case, suite.reports[case_id]
    )
    scored = score_production_observation(
        observed, suite.oracle[case_id], suite.reports[case_id], case=case
    )
    allowed = observed["allowed_kb_id"]
    assert all(kb == allowed for kb in observed["critic_calls"][-1]["kb_ids"])
    assert scored["product_path_eligible"] is True
    assert scored["pass"] is True


# ── Task 7D/E: final output citation scope safety ──


def test_final_output_no_foreign_citation_passes_scope_safety() -> None:
    allowed = str(stable_uuid("kb-main"))
    score = score_final_output(
        content="Allowed answer[片段1]",
        citations=[{"kb_id": allowed, "chunk_id": "c1"}],
        allowed_kb_id=allowed,
    )
    assert score.final_citation_scope_valid is True
    assert score.safe_outcome is True


def test_final_output_foreign_citation_must_fail_safe_outcome() -> None:
    allowed = str(stable_uuid("kb-main"))
    foreign = str(stable_uuid("kb-other"))
    score = score_final_output(
        content="Unsafe answer[片段1]",
        citations=[{"kb_id": foreign, "chunk_id": "c1"}],
        allowed_kb_id=allowed,
    )
    assert score.foreign_kb_reference_count == 1
    assert score.safe_outcome is False


def test_final_output_foreign_citation_fails_even_on_refusal_terminal() -> None:
    allowed = str(stable_uuid("kb-main"))
    foreign = str(stable_uuid("kb-other"))
    score = score_final_output(
        content="当前知识库中没有找到与您问题相关的依据。",
        citations=[{"kb_id": foreign, "chunk_id": "c1"}],
        allowed_kb_id=allowed,
    )
    assert score.safe_outcome is False


# ── Task 7F/G: post-mutation final-output scoring boundary ──


def test_pre_revision_safe_post_revision_foreign_fails_final_scorer() -> None:
    allowed = str(stable_uuid("kb-main"))
    foreign = str(stable_uuid("kb-other"))
    pre = score_final_output(
        content="safe draft",
        citations=[{"kb_id": allowed, "chunk_id": "c1"}],
        allowed_kb_id=allowed,
    )
    post = score_final_output(
        content="mutated unsafe[片段1]",
        citations=[{"kb_id": foreign, "chunk_id": "c2"}],
        allowed_kb_id=allowed,
        critic_calls=[
            {"kb_ids": [allowed], "chunk_ids": ["c1"]},
            {"kb_ids": [allowed, foreign], "chunk_ids": ["c1", "c2"]},
        ],
    )
    assert pre.safe_outcome is True
    assert post.safe_outcome is False
    assert post.post_recovery_scope_violation is True


def test_pre_revision_foreign_final_removes_foreign_scores_on_final_only() -> None:
    allowed = str(stable_uuid("kb-main"))
    foreign = str(stable_uuid("kb-other"))
    pre = score_final_output(
        content="draft with foreign",
        citations=[{"kb_id": foreign, "chunk_id": "c1"}],
        allowed_kb_id=allowed,
    )
    post = score_final_output(
        content="clean final[片段1]",
        citations=[{"kb_id": allowed, "chunk_id": "c2"}],
        allowed_kb_id=allowed,
        critic_calls=[
            {"kb_ids": [foreign], "chunk_ids": ["c1"]},
            {"kb_ids": [allowed], "chunk_ids": ["c2"]},
        ],
    )
    assert pre.safe_outcome is False
    assert post.safe_outcome is True


# ── Task 7H: critic OFF baseline — eligibility shouldn't depend on critic ──


def test_product_path_eligibility_independent_of_critic_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    suite = load_frozen_suite()
    case = next(item for item in suite.cases if item["case_id"] == "C01-fully-supported-exact")
    monkeypatch.setattr(settings, "rag_critic_enabled", False)
    flags_on = assess_case_product_path_eligibility(case, mode=HarnessMode.PRODUCTION_PATH)
    monkeypatch.setattr(settings, "rag_critic_enabled", True)
    flags_off = assess_case_product_path_eligibility(case, mode=HarnessMode.PRODUCTION_PATH)
    assert flags_on == flags_off
    assert flags_on.product_path_eligible is True


# ── Task 6: C12 production-path protocol proof ──


@pytest.mark.asyncio
async def test_c12_production_path_protocol_proof(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    suite = load_frozen_suite()
    case = next(
        item for item in suite.cases if item["case_id"] == "C12-out-of-scope-provenance"
    )
    assert _foreign_evidence(case)
    assert not _scoped_evidence(case)

    production = await execute_production_path_case(
        monkeypatch, case, suite.reports["C12-out-of-scope-provenance"]
    )
    probe = await execute_defense_in_depth_probe(
        monkeypatch, case, suite.reports["C12-out-of-scope-provenance"]
    )
    prod_scored = score_production_observation(
        production,
        suite.oracle["C12-out-of-scope-provenance"],
        suite.reports["C12-out-of-scope-provenance"],
        case=case,
    )
    probe_score: FinalSafetyScore = probe["final_safety_score"]

    proof = build_c12_protocol_proof()
    proof.update(
        {
            "PRODUCT_PATH_ELIGIBLE": prod_scored["product_path_eligible"],
            "REAL_SCOPE_USED": production["product_path_flags"].real_scope_used,
            "DIRECT_FOREIGN_INJECTION": False,
            "PRODUCTION_ORCHESTRATION_USED": production[
                "product_path_flags"
            ].production_orchestration_used,
            "SHARED_BUDGET_USED": production["product_path_flags"].shared_budget_used,
            "FINAL_OUTPUT_SCORING_USED": True,
            "FOREIGN_FINAL_CITATION_DETECTED": probe_score.foreign_kb_reference_count > 0,
            "SAFE_SCORER_FALSE_PASS_ELIMINATED": probe_score.safe_outcome is False,
            "production_path_classification": prod_scored["classification"],
            "probe_safe_outcome": probe_score.safe_outcome,
            "probe_foreign_kb_reference_count": probe_score.foreign_kb_reference_count,
        }
    )
    write_validation_artifact(proof)

    assert prod_scored["product_path_eligible"] is False
    assert prod_scored["classification"] == (
        MeasurementClassification.MEASUREMENT_PROTOCOL_INVALID.value
    )
    assert production["product_path_flags"].direct_foreign_injection is False
    assert probe_score.safe_outcome is False
    assert probe_score.foreign_kb_reference_count >= 1

    saved = json.loads(VALIDATION_PATH.read_text(encoding="utf-8"))
    assert saved["PRODUCT_PATH_ELIGIBLE"] is False
    assert saved["DIRECT_FOREIGN_INJECTION"] is False
    assert saved["SAFE_SCORER_FALSE_PASS_ELIMINATED"] is True


# ── Task 8: historical evidence integrity ──


def test_p2_r1_history_preserved() -> None:
    correction = json.loads(CORRECTION_PATH.read_text(encoding="utf-8"))
    artifact = json.loads(P2_R1_ARTIFACT_PATH.read_text(encoding="utf-8"))
    historical = json.loads(HISTORICAL_P2_PATH.read_text(encoding="utf-8"))
    assert correction["state"] == "BLOCKED"
    assert correction["classification"] == "MEASUREMENT_PROTOCOL_MISMATCH"
    assert artifact["state"] == "PARTIAL"
    assert artifact["executed_case_count"] == 12
    assert historical["state"] == "PARTIAL"
    c11_hist = next(
        item
        for item in historical["case_results"]
        if item["case_id"] == "C11-citation-format-only-defect"
    )
    assert c11_hist["trajectory_result"] == {
        "status": "skipped_unavailable",
        "attempt_count": 0,
    }


def test_p2b_c11_regression_fixture_unchanged() -> None:
    payload = json.loads(P2B_PATH.read_text(encoding="utf-8"))
    assert payload["state"] == "PASS"


@pytest.mark.asyncio
async def test_c12_original_internal_injection_still_runnable_as_probe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    suite = load_frozen_suite()
    case = next(
        item for item in suite.cases if item["case_id"] == "C12-out-of-scope-provenance"
    )
    result = await execute_defense_in_depth_probe(
        monkeypatch, case, suite.reports["C12-out-of-scope-provenance"]
    )
    assert result["mode"] == HarnessMode.DEFENSE_IN_DEPTH_PROBE.value


# ── Product-path eligibility definition coverage ──


def test_product_path_flags_p1_p8_contract() -> None:
    eligible = ProductPathFlags(
        production_equivalent_entry=True,
        real_scope_used=True,
        production_orchestration_used=True,
        shared_budget_used=True,
        direct_foreign_injection=False,
        prepare_gate_path_used=True,
        final_output_scoring_used=True,
        evidence_via_legitimate_path=True,
        final_scope_validation_used=True,
    )
    assert eligible.product_path_eligible is True
    ineligible = ProductPathFlags(
        production_equivalent_entry=True,
        real_scope_used=True,
        production_orchestration_used=True,
        shared_budget_used=True,
        direct_foreign_injection=True,
        prepare_gate_path_used=False,
        final_output_scoring_used=True,
        evidence_via_legitimate_path=False,
        final_scope_validation_used=True,
    )
    assert ineligible.product_path_eligible is False


def test_real_scope_construction_from_case_scope() -> None:
    suite = load_frozen_suite()
    case = next(item for item in suite.cases if item["case_id"] == "C01-fully-supported-exact")
    scope = build_tool_scope(case)
    allowed = stable_uuid("kb-main")
    assert scope.is_kb_visible(allowed)
    assert scope.require_kb_visible(stable_uuid("kb-other")) is not None


@pytest.mark.asyncio
async def test_production_path_cases_c02_c11_regression(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    suite = load_frozen_suite()
    for case_id in (
        "C02-supported-paraphrase-low-lexical",
        "C11-citation-format-only-defect",
    ):
        case = next(item for item in suite.cases if item["case_id"] == case_id)
        observed = await execute_production_path_case(
            monkeypatch, case, suite.reports[case_id]
        )
        scored = score_production_observation(
            observed, suite.oracle[case_id], suite.reports[case_id], case=case
        )
        assert scored["product_path_eligible"] is True
        assert scored["final_safety_score"].safe_outcome is True
