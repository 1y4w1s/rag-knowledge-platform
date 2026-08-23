"""MEMORY P4 offline utilization ablation — deterministic tests."""

from __future__ import annotations

import json
from pathlib import Path

from app.eval.memory_utilization_ablation.candidates import (
    has_instruction_conflict,
    render_candidate,
)
from app.eval.memory_utilization_ablation.corpus import (
    assert_corpus_integrity,
    baseline_formatted_block,
    reconstruct_trials,
)
from app.eval.memory_utilization_ablation.evaluator_audit import (
    audit_l4_semantics,
    build_hard_negatives,
    score_hard_negative,
)
from app.eval.memory_utilization_ablation.models import (
    CandidateId,
    RootCauseTaxonomy,
    Verdict,
)
from app.eval.memory_utilization_ablation.root_cause import (
    classify_trial,
    reconstruct_info_flow,
)
from app.eval.memory_utilization_ablation.runner import (
    build_ablation_manifest,
    run_ablation,
)


def test_p3_frozen_corpus_integrity_unchanged() -> None:
    trials = reconstruct_trials()
    assert_corpus_integrity(trials)
    with_mem = [t for t in trials if t.condition == "WITH_MEMORY"]
    assert len(with_mem) == 10
    assert all(t.l3_passed for t in with_mem)
    assert all(not t.l4_passed for t in with_mem)
    assert all(not t.l5_passed for t in with_mem)


def test_info_flow_reconstructed_for_with_memory() -> None:
    trials = reconstruct_trials()
    sample = next(
        t for t in trials if t.condition == "WITH_MEMORY" and t.case_id == "GA-9"
    )
    flow = reconstruct_info_flow(sample)
    assert flow.loaded is True
    assert flow.memory_section_present is True
    assert flow.utilization_verdict is False
    assert flow.benefit_verdict is False
    assert "不覆盖" in flow.planner_instruction_conflict


def test_dominant_root_cause_is_instruction_priority_conflict() -> None:
    trials = reconstruct_trials()
    with_mem = [t for t in trials if t.condition == "WITH_MEMORY"]
    dominant, _ = classify_trial(with_mem[0])
    assert dominant == RootCauseTaxonomy.M4_INSTRUCTION_PRIORITY_CONFLICT
    report = run_ablation()
    assert report.dominant_root_cause == RootCauseTaxonomy.M4_INSTRUCTION_PRIORITY_CONFLICT


def test_evaluator_blind_spot_is_partial_not_yes() -> None:
    audit = audit_l4_semantics()
    assert audit["blind_spot"] == "PARTIAL"
    assert audit["true_positive_english"] is True
    assert audit["exact_json_echo_not_enough"] is True
    assert audit["hard_negative_false_utilization_ids"] == []
    assert audit["ga10_query_echo_full_utilization"] is False


def test_hard_negatives_do_not_false_utilize() -> None:
    for sample in build_hard_negatives():
        assert score_hard_negative(sample) is False, sample.sample_id


def test_baseline_has_instruction_conflict_candidates_remove_it() -> None:
    trials = reconstruct_trials()
    sample = next(t for t in trials if t.condition == "WITH_MEMORY" and t.seeds)
    c0 = render_candidate(CandidateId.C0_BASELINE, sample.seeds, sample.query)
    assert has_instruction_conflict(c0) is True
    for cid in (
        CandidateId.C1_CONTRASTIVE_LABEL,
        CandidateId.C2_STRUCTURED_BLOCK,
        CandidateId.C3_TASK_BINDING,
    ):
        rendered = render_candidate(cid, sample.seeds, sample.query)
        assert has_instruction_conflict(rendered) is False


def test_candidates_do_not_force_answer_content() -> None:
    trials = reconstruct_trials()
    sample = next(
        t for t in trials if t.case_id == "GA-9" and t.condition == "WITH_MEMORY"
    )
    banned = "preferred language for retrieval is english"
    for cid in CandidateId:
        rendered = render_candidate(cid, sample.seeds, sample.query)
        assert banned not in rendered.lower()


def test_privacy_no_extra_secrets_or_cross_user() -> None:
    trials = reconstruct_trials()
    sample = next(
        t for t in trials if t.condition == "WITH_MEMORY" and t.case_id == "GA-10"
    )
    for cid in CandidateId:
        rendered = render_candidate(cid, sample.seeds, sample.query)
        assert "other_user" not in rendered.lower()
        assert "password" not in rendered.lower()
        assert "api_key" not in rendered.lower()
        assert "docker" in rendered.lower() or "topic" in rendered.lower()


def test_primary_and_fallback_selection_and_l5_discipline() -> None:
    report = run_ablation()
    assert report.primary == CandidateId.C1_CONTRASTIVE_LABEL.value
    assert report.fallback == CandidateId.C2_STRUCTURED_BLOCK.value
    assert report.ready_for_product_experiment is True
    assert report.l5_fixed is False
    assert report.product_diff == 0
    by_id = {s.candidate_id: s for s in report.scores}
    assert by_id[report.primary].verdict == Verdict.READY_FOR_PRODUCT_EXPERIMENT
    assert by_id[report.primary].false_utilization_on_hard_negatives == 0.0
    assert by_id[CandidateId.C6_RELEVANCE_FILTER.value].verdict == Verdict.DIAGNOSTIC_ONLY
    assert by_id[CandidateId.C0_BASELINE.value].verdict == Verdict.REJECT


def test_manifest_roundtrip_and_fixture_written() -> None:
    manifest = build_ablation_manifest()
    assert manifest["l5_fixed"] is False
    assert manifest["product_diff"] == 0
    assert manifest["primary"] == CandidateId.C1_CONTRASTIVE_LABEL.value
    out = Path("tests/fixtures/l4_memory_capability/l4-memory-p4-ablation.manifest.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    loaded = json.loads(out.read_text(encoding="utf-8"))
    assert loaded["ready_for_product_experiment"] is True


def test_baseline_formatted_block_matches_product_disclaimer() -> None:
    trials = reconstruct_trials()
    sample = next(t for t in trials if t.seeds)
    block = baseline_formatted_block(sample.seeds)
    assert "不覆盖检索结果" in block
