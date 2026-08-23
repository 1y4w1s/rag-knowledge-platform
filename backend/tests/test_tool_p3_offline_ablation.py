"""TOOL P3 offline remediation ablation — deterministic eval-only tests."""

from __future__ import annotations

import json
from pathlib import Path

from app.eval.tool_capability.p2_freeze import (
    assert_manifest_matches_constants,
    load_p2_freeze_manifest,
)
from app.eval.tool_remediation_ablation.audit_s import audit_family_s
from app.eval.tool_remediation_ablation.audit_t import (
    TSubtype,
    audit_family_t,
    classify_trial_t,
    critical_distinction,
)
from app.eval.tool_remediation_ablation.corpus import (
    assert_corpus_integrity,
    first_tool_name,
    reconstruct_trials,
)
from app.eval.tool_remediation_ablation.family_s import (
    NO_HINT,
    apply_s0,
    apply_s2,
    apply_s3,
    apply_s4,
    intent_class_for_query,
    s2_preferred_tool_hint,
)
from app.eval.tool_remediation_ablation.family_t import (
    apply_t1,
    apply_t2,
    apply_t5,
    t2_task_contract_satisfied_hint,
)
from app.eval.tool_remediation_ablation.hard_negatives import (
    build_s_hard_negatives,
    build_s_targets,
    build_t_hard_negatives,
    build_t_targets,
)
from app.eval.tool_remediation_ablation.models import (
    STAGE,
    TARGET_TRIAL_COUNT,
    FailureFamily,
    Verdict,
)
from app.eval.tool_remediation_ablation.runner import build_ablation_manifest, run_ablation

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "l4_tool_capability"
CORPUS_PATH = FIXTURE_DIR / "l4-tool-p3-p2-failure-corpus.json"
MANIFEST_PATH = FIXTURE_DIR / "l4-tool-p3-offline-ablation.manifest.json"


def test_p2_freeze_corpus_integrity_unchanged() -> None:
    """P2 freeze manifest must remain trustworthy and intact."""
    assert_manifest_matches_constants(load_p2_freeze_manifest())


def test_failure_corpus_reconstructs_all_fifteen_trials() -> None:
    assert CORPUS_PATH.is_file()
    trials = reconstruct_trials()
    assert_corpus_integrity(trials)
    assert len(trials) == TARGET_TRIAL_COUNT
    assert sum(1 for t in trials if t.family == FailureFamily.S_TOOL_SELECTION) == 5
    assert sum(1 for t in trials if t.family == FailureFamily.T_POST_OBS_TERMINATION) == 10


def test_family_s_audit_not_model_is_dumb() -> None:
    audit = audit_family_s()
    assert "semantic_search" in audit["root_cause"]
    assert "model is dumb" in audit["not_root_causes"]
    assert audit["both_exposed"] is True
    assert audit["factors"]["ordering"]["first_listed"] == "semantic_search"


def test_family_s_all_gq131_first_tool_semantic_search() -> None:
    trials = [t for t in reconstruct_trials() if t.case_id == "GQ-131"]
    assert len(trials) == 5
    assert all(first_tool_name(t) == "semantic_search" for t in trials)


def test_family_t_is_termination_reasoning_not_evidence_gate() -> None:
    audit = audit_family_t()
    assert audit["subtype_counts"][TSubtype.T_A_TERMINATION_REASONING.value] == 10
    assert audit["subtype_counts"][TSubtype.T_B_EVIDENCE_GATE_CORRECT.value] == 0
    for trial in reconstruct_trials():
        if trial.family != FailureFamily.T_POST_OBS_TERMINATION:
            continue
        dist = critical_distinction(trial)
        assert dist["termination_reasoning_failure"] is True
        assert dist["evidence_gate_blocking"] is False
        labels = classify_trial_t(trial)
        assert TSubtype.T_A_TERMINATION_REASONING in labels
        assert TSubtype.T_E_BUDGET_LOOP in labels


def test_s_hard_negatives_cover_required_classes() -> None:
    classes = {s.intent_class for s in build_s_hard_negatives()}
    assert classes >= {"semantic_qa", "catalog_search", "ambiguous", "oos", "multi_step"}


def test_s2_recovers_targets_without_forcing_all_search() -> None:
    targets = build_s_targets()
    assert len(targets) == 5
    assert all(s2_preferred_tool_hint(s) == "search_documents" for s in targets)
    assert all(apply_s2(s) == "search_documents" for s in targets)
    assert all(apply_s0(s) == "semantic_search" for s in targets)

    hns = {s.sample_id: s for s in build_s_hard_negatives()}
    assert apply_s2(hns["S-HN-semantic_qa"]) == "semantic_search"
    assert apply_s2(hns["S-HN-should_search_documents"]) == "search_documents"
    assert s2_preferred_tool_hint(hns["S-HN-ambiguous"]) == NO_HINT
    assert apply_s2(hns["S-HN-ambiguous"]) == "semantic_search"  # no force
    assert s2_preferred_tool_hint(hns["S-HN-multistep"]) == NO_HINT
    assert apply_s2(hns["S-HN-multistep"]) == "list_knowledge_bases"
    assert s2_preferred_tool_hint(hns["S-HN-oos"]) == NO_HINT
    assert apply_s2(hns["S-HN-oos"]) == "list_knowledge_bases"


def test_s3_guard_only_when_intent_unambiguous() -> None:
    assert intent_class_for_query("How to search documents across knowledge bases?") == "catalog_search"
    targets = build_s_targets()
    assert all(apply_s3(s) == "search_documents" for s in targets)
    ambiguous = next(s for s in build_s_hard_negatives() if s.sample_id == "S-HN-ambiguous")
    assert apply_s3(ambiguous) == ambiguous.selected_tool


def test_s4_is_diagnostic_inventory_ablation() -> None:
    targets = build_s_targets()
    assert all(apply_s4(s) == "search_documents" for s in targets)
    report = run_ablation()
    s4 = next(s for s in report.s_scores if s.candidate_id == "S4")
    assert s4.verdict == Verdict.DIAGNOSTIC_ONLY
    assert s4.scope_expansion is True


def test_t1_blanket_obs_complete_regresses_hard_negatives() -> None:
    hns = {s.sample_id: s for s in build_t_hard_negatives()}
    assert apply_t1(hns["T-HN-wrong_tool_ok_obs"]) == "finish"
    assert apply_t1(hns["T-HN-partial_budget"]) == "finish"
    report = run_ablation()
    t1 = next(s for s in report.t_scores if s.candidate_id == "T1")
    assert t1.verdict == Verdict.REJECT
    assert t1.hard_negative_regressions >= 2


def test_t2_and_t5_recover_targets_with_zero_hn_regression() -> None:
    targets = build_t_targets()
    assert len(targets) == 10
    assert all(apply_t2(s) == "finish" for s in targets)
    assert all(apply_t5(s) == "finish" for s in targets)
    report = run_ablation()
    for cid in ("T2", "T3", "T5"):
        row = next(s for s in report.t_scores if s.candidate_id == cid)
        assert row.target_recovered == 10
        assert row.hard_negative_regressions == 0
        assert row.verdict == Verdict.ACCEPT


def test_t6_stop_policy_diagnostic_only() -> None:
    report = run_ablation()
    t6 = next(s for s in report.t_scores if s.candidate_id == "T6")
    assert t6.verdict == Verdict.DIAGNOSTIC_ONLY
    assert t6.target_recovered == 0


def test_offline_matrix_ready_flags_and_product_diff_zero() -> None:
    report = run_ablation()
    assert report.stage == STAGE
    assert report.product_diff == 0
    assert report.best_s == "S2"
    assert report.best_t == "T2"
    assert report.ready_for_product_selection_fix is True
    assert report.ready_for_product_termination_fix is True
    payload = build_ablation_manifest(report)
    assert payload["state"] == "PASS"
    assert payload["ready_for_product_ablation"] is True
    assert payload["freeze_status"] == "READY_FOR_PRODUCT_EXPERIMENT"
    assert payload["production_fix_proven"] is False
    assert payload["p2_primary_score"] == "0/3"
    assert payload["p2_stability_score"] == "0/15"
    assert payload["s_target_recovery"] == "5/5"
    assert payload["s_hard_negative_regression"] == "0/5"
    assert payload["t_target_recovery"] == "10/10"
    assert payload["t_hard_negative_regression"] == "0/6"
    assert payload["families"]["S"]["false_positive_hint"] == 0
    assert payload["families"]["T"]["false_positive_hint"] == 0
    assert payload["families"]["S"]["freeze_semantics"]["deterministic_override"] is False
    assert payload["families"]["T"]["freeze_semantics"]["force_finish"] is False
    # T2 hint is advisory: targets get hint, incomplete HN must not.
    targets = build_t_targets()
    assert all(t2_task_contract_satisfied_hint(s) == "finish" for s in targets)
    empty = next(s for s in build_t_hard_negatives() if s.sample_id == "T-HN-empty_obs")
    assert t2_task_contract_satisfied_hint(empty) is None


def test_frozen_manifest_fixture_matches_runner() -> None:
    report = run_ablation()
    frozen = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    live = build_ablation_manifest(report)
    assert frozen["families"]["S"]["best_candidate"] == report.best_s
    assert frozen["families"]["T"]["best_candidate"] == report.best_t
    assert frozen["ready_for_product_selection_fix"] == report.ready_for_product_selection_fix
    assert frozen["ready_for_product_termination_fix"] == report.ready_for_product_termination_fix
    assert frozen["product_diff"] == 0
    assert frozen["lm_studio_rerun"] is False
    assert frozen["freeze_status"] == "READY_FOR_PRODUCT_EXPERIMENT"
    assert frozen["production_fix_proven"] is False
    assert frozen["p2_primary_score"] == live["p2_primary_score"]
    assert frozen["p2_stability_score"] == live["p2_stability_score"]
    assert frozen["families"]["S"]["status"] == "READY_FOR_PRODUCT_EXPERIMENT"
    assert frozen["families"]["T"]["status"] == "READY_FOR_PRODUCT_EXPERIMENT"
    assert frozen["families"]["S"]["false_positive_hint"] == 0
    assert frozen["families"]["T"]["false_positive_hint"] == 0
