"""W8 P1 / Gate C — Evidence integrity characterization harness tests.

Characterization suite may report matcher FPs; CI asserts harness integrity,
F2 reproduction, and frozen ground truth — not matcher quality gates.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.core.config import settings
from app.eval.evidence_integrity.cases import (
    F2_EVIDENCE,
    F2_FACT_X1,
    F2_FACT_X2,
    CASE_BY_ID,
    gate_c_cases,
)
from app.eval.evidence_integrity.runner import (
    build_report,
    reproduce_f2,
    run_case,
    run_suite,
)
from app.eval.evidence_integrity.schema import EvalRelation, SCHEMA_VERSION
from app.eval.local_agent_trajectory.cases import EXCERPT_UNRELATED
from app.services.agent.matcher import _SUPPORT_OVERLAP, deterministic_match, EvidenceSnippet
from app.services.agent.types import FactGoal, FactStatus

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "l4_evidence_integrity"
BASELINE_MANIFEST = FIXTURE_DIR / "gate-c-baseline.manifest.json"

REQUIRED_CATEGORIES = {
    "exact_support",
    "keyword_overlap",
    "wrong_value",
    "negation",
    "entity_mismatch",
    "temporal_mismatch",
    "scope_mismatch",
    "partial_support",
    "paraphrase",
    "distractor",
    "conflict",
    "no_evidence",
    "f2_repro",
}


def test_product_defaults_unchanged() -> None:
    assert settings.agent_l4_evidence_matcher_enabled is False
    assert settings.agent_l4_stop_policy_enabled is False
    assert settings.agent_l3_next_action_enabled is False


def test_case_set_size_and_categories() -> None:
    cases = gate_c_cases()
    assert 20 <= len(cases) <= 40
    cats = {c.category for c in cases}
    assert REQUIRED_CATEGORIES <= cats
    # Ground truth frozen in fixture definitions
    assert all(isinstance(c.expected_relation, EvalRelation) for c in cases)
    assert CASE_BY_ID["F2_W8_REPRO"].is_f2_repro is True
    assert CASE_BY_ID["F2_W8_REPRO"].expected_relation == EvalRelation.irrelevant


def test_f2_excerpt_preserved_from_w8() -> None:
    """Historical W8 empty-tool excerpt must remain the F2 evidence source."""
    assert F2_EVIDENCE == EXCERPT_UNRELATED
    assert "住宿标准" in F2_EVIDENCE
    assert "无关" in F2_EVIDENCE


def test_f2_reproduced_offline_without_llm() -> None:
    f2 = reproduce_f2()
    assert f2["reproduced"] is True
    assert f2["fact_goals"]["X1"] == F2_FACT_X1
    assert f2["fact_goals"]["X2"] == F2_FACT_X2
    assert f2["evidence_excerpt"] == F2_EVIDENCE
    assert f2["fact_status_before"] == {"X1": "missing", "X2": "missing"}
    assert f2["fact_status_after"] == {"X1": "covered", "X2": "covered"}
    assert f2["stop_policy"]["reason_code"] == "facts_covered"
    assert f2["root_cause_layer"] == "MATCHER"
    assert f2["stop_policy_root_cause"] is False
    assert f2["threshold_behavior"] == "above_support"
    for score in f2["overlap_scores"].values():
        assert score is not None and score >= _SUPPORT_OVERLAP


def test_real_matcher_entry_used() -> None:
    """Characterization must call product deterministic_match, not a copy."""
    facts = [FactGoal(id="X1", text=F2_FACT_X1, status=FactStatus.missing)]
    snip = EvidenceSnippet(evidence_id="u", text=F2_EVIDENCE)
    match = deterministic_match(facts, (snip,), only_uncovered=True)
    assert match.ok is True
    assert match.source == "deterministic"
    assert any("X1" in item.supports for item in match.items)


def test_suite_runs_deterministic_and_reports_metrics() -> None:
    results, metrics, f2 = run_suite()
    assert metrics.case_count == len(gate_c_cases())
    assert metrics.f2_reproduced is True
    assert f2["reproduced"] is True
    assert 0.0 <= metrics.precision <= 1.0
    assert 0.0 <= metrics.recall <= 1.0
    assert 0.0 <= metrics.coverage_false_positive_rate <= 1.0
    assert 0.0 <= metrics.unsafe_finish_enabling_fp_rate <= 1.0
    # Gate C must surface coverage FP risk (characterization signal, not quality gate)
    assert metrics.coverage_false_positive_count >= 1
    assert metrics.unsafe_finish_enabling_count >= 1
    assert "LEXICAL_OVERLAP_FALSE_POSITIVE" in metrics.failure_taxonomy_counts
    report = build_report(results, metrics, f2)
    assert report["schema_version"] == SCHEMA_VERSION
    assert report["matcher_audit"]["semantic_signal"] is False
    assert report["matcher_audit"]["support_overlap_threshold"] == _SUPPORT_OVERLAP


def test_f2_case_is_coverage_fp_and_unsafe_finish() -> None:
    result = run_case(CASE_BY_ID["F2_W8_REPRO"])
    assert result.expected_relation == "irrelevant"
    assert result.actual_relation == "support"
    assert result.fact_status_after == "covered"
    assert result.coverage_false_positive is True
    assert result.unsafe_finish_enabling is True
    assert result.root_cause_layer == "MATCHER"
    assert result.failure_taxonomy == "LEXICAL_OVERLAP_FALSE_POSITIVE"
    assert result.threshold_band in {"above_support", "near_support"}
    # Secondary X2 also wrongly covered in extras
    sec = result.extras.get("secondary") or {}
    assert sec.get("status_after") == "covered"


def test_exact_support_control_can_pass() -> None:
    result = run_case(CASE_BY_ID["A1"])
    assert result.true_positive or result.matched
    assert result.coverage_false_positive is False


def test_unrelated_negative_control() -> None:
    result = run_case(CASE_BY_ID["L2"])
    assert result.expected_relation == "irrelevant"
    assert result.actual_relation == "irrelevant"
    assert result.fact_status_after == "missing"
    assert result.coverage_false_positive is False


def test_baseline_manifest_frozen() -> None:
    """Manifest records characterization baseline; does not rewrite ground truth."""
    assert BASELINE_MANIFEST.is_file()
    data = json.loads(BASELINE_MANIFEST.read_text(encoding="utf-8"))
    assert data["gate"] == "Gate C"
    assert data["schema_version"] == SCHEMA_VERSION
    assert data["ground_truth_policy"] == "frozen_in_cases_not_matcher_snapshot"
    assert data["w8_p0_historical"]["end_to_end_success_rate"] == 0.875
    assert data["w8_p0_historical"]["f2_case_id"] == "F2"
    assert data["f2_reproduction"]["expected_stable"] is True
    # Harness must still reproduce; rates are informational floor notes
    _, metrics, f2 = run_suite()
    assert f2["reproduced"] is True
    assert metrics.case_count >= data["min_case_count"]
    assert metrics.coverage_false_positive_rate >= data["characterization_floors"][
        "coverage_false_positive_rate_min"
    ]


def test_ground_truth_not_rewritten_to_matcher_bug() -> None:
    """Regression: F2-class cases must keep expected=irrelevant (not support)."""
    for cid in ("B1", "B3", "F2_W8_REPRO", "J2"):
        case = CASE_BY_ID[cid]
        assert case.expected_relation == EvalRelation.irrelevant, cid
