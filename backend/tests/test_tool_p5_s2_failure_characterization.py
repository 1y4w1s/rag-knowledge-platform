"""TOOL Selection P5 — S2 failure characterization offline tests (eval-only)."""

from __future__ import annotations

import json
from pathlib import Path

from app.eval.tool_selection_p5.candidates import apply_s3a, apply_s3e, score_all
from app.eval.tool_selection_p5.characterize import characterize_s2_failure
from app.eval.tool_selection_p5.corpus import (
    assert_corpus_integrity,
    build_target_samples,
    reconstruct_trials,
)
from app.eval.tool_selection_p5.hard_negatives import build_hard_negatives
from app.eval.tool_selection_p5.models import EXPECTED_TOOL, STUBBORN_TOOL, Verdict
from app.eval.tool_selection_p5.runner import run_characterization, write_manifest

FIX = Path(__file__).resolve().parent / "fixtures" / "l4_tool_capability"


def test_corpus_integrity_gq131_conditions_10_11():
    trials = reconstruct_trials()
    assert_corpus_integrity(trials)
    assert all(t.first_tool == STUBBORN_TOOL for t in trials)
    assert all(t.preferred_hint == EXPECTED_TOOL for t in trials)
    assert all(t.hint_emitted for t in trials)
    assert all(t.planner_followed_hint is False for t in trials)


def test_d3_hypotheses_supported_from_frozen_evidence():
    report = characterize_s2_failure()
    assert report["hypotheses"]["A_saw_hint_but_ignored"]["supported"] is True
    assert report["hypotheses"]["E_preferred_tool_treated_as_non_binding_advice"]["supported"] is True
    assert report["hypotheses"]["F_planner_prior_favoring_semantic_search"]["supported"] is True
    assert report["primary_mechanisms"] == ["A", "E", "F"]
    assert report["frozen_roots"]["A"]
    assert report["frozen_roots"]["E"]
    assert report["frozen_roots"]["F"]
    s2 = report["s2_failure"]
    assert s2["HINT_DELIVERY_SUCCESS"] is True
    assert s2["TOOL_SELECTION_SUCCESS"] is False
    assert s2["inequality_holds"] is True
    assert s2["inequality"] == "HINT_DELIVERY_SUCCESS != TOOL_SELECTION_SUCCESS"


def test_hard_negatives_cover_required_classes():
    classes = {s.intent_class for s in build_hard_negatives()}
    assert classes >= {
        "semantic_qa",
        "catalog_search",
        "ambiguous",
        "multi_tool",
        "oos",
        "both_reasonable",
    }


def test_offline_candidates_primary_fallback_and_guards():
    targets = build_target_samples()
    hns = build_hard_negatives()
    scores = {s.candidate_id: s for s in score_all(targets, hns)}
    assert scores["S0"].target_recovered == 0
    assert scores["S3A"].verdict == Verdict.PRIMARY
    assert scores["S3A"].hard_negative_regressions == 0
    assert scores["S3B"].verdict == Verdict.FALLBACK
    assert scores["S3E"].verdict == Verdict.DIAGNOSTIC_ONLY
    assert scores["S3F"].verdict == Verdict.DIAGNOSTIC_ONLY
    both = next(s for s in hns if s.sample_id == "P5-HN-both-reasonable")
    # Do not hard-route both-reasonable retrieval entirely to search_documents
    assert apply_s3a(both) == both.selected_tool
    assert scores["S3E"].target_recovered == len(targets)
    assert apply_s3e(targets[0]) == EXPECTED_TOOL


def test_runner_manifest_ready_product_diff_zero(tmp_path):
    report = run_characterization()
    assert report["product_diff"] == 0
    assert report["golden_diff"] == 0
    assert report["workflow_diff"] == 0
    assert report["lm_studio_used"] is False
    assert report["recommendation"]["primary"] == "S3A"
    assert report["recommendation"]["fallback"] == "S3B"
    assert report["recommendation"]["candidate_status"] == "READY_FOR_PRODUCT_EXPERIMENT"
    assert set(report["recommendation"]["never_claim"]) >= {
        "FIXED",
        "REAL_VALIDATED",
        "PRODUCTION_READY",
    }
    assert report["s3a_freeze"]["status"] == "READY_FOR_PRODUCT_EXPERIMENT"
    assert report["s3b_freeze"]["role"] == "FALLBACK"
    assert report["d11"]["ready_for_product_experiment"] == "YES"
    assert report["d11"]["runtime_rollout"] == "NO"
    assert report["d11"]["hint_delivery_ne_tool_selection"] is True
    out = write_manifest(tmp_path / "p5.json")
    assert out.is_file()
    fixture = FIX / "l4-tool-p5-offline-characterization.manifest.json"
    assert fixture.is_file()
    compact = json.loads(fixture.read_text(encoding="utf-8"))
    assert compact["product_diff"] == 0
    assert compact["recommendation"]["primary"] == "S3A"
