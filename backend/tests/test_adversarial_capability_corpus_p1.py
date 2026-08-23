"""ADVERSARIAL P1 capability corpus + migration tests (deterministic, no LLM)."""

from __future__ import annotations

from app.eval.adversarial_capability.capability_cases import (
    CAPABILITY_CASES,
    MIGRATION_AUDITS,
    MIGRATION_AUDIT_BY_ID,
)
from app.eval.adversarial_capability.corpus_fixtures import ALL_CORPORA, CORPUS_BY_ID
from app.eval.adversarial_capability.freeze import ROUND_START_MASTER_SHA
from app.eval.adversarial_capability.p1_evaluator import (
    HARD_CONTROL_TRAJECTORIES,
    MockTrajectory,
    evaluate_case,
    evaluate_hard_control,
)
from app.eval.adversarial_capability.p1_freeze import (
    build_p1_manifest,
    capability_valid_denominator,
    load_p1_manifest,
    migration_outcome_counts,
)


def test_p1_valid_denominator_positive() -> None:
    assert capability_valid_denominator() == 4
    manifest = load_p1_manifest()
    assert manifest["CAPABILITY_VALID_DENOMINATOR"] == 4
    assert manifest["round_start_master_sha"] == ROUND_START_MASTER_SHA


def test_corpus_classes_represented() -> None:
    breakdown = load_p1_manifest()["corpus_class_breakdown"]
    assert breakdown["ANSWERABLE"] == 1
    assert breakdown["UNANSWERABLE_IN_CORPUS"] == 1
    assert breakdown["INSUFFICIENT_EVIDENCE"] == 1
    assert breakdown["CONFLICTED_EVIDENCE"] == 1


def test_corpus_fingerprints_stable() -> None:
    for corpus in ALL_CORPORA:
        loaded = CORPUS_BY_ID[corpus.corpus_fixture_id]
        assert loaded.corpus_fingerprint == corpus.corpus_fingerprint


def test_capability_case_fields_complete() -> None:
    required = {
        "case_id",
        "answerability_class",
        "question",
        "corpus_fixture_id",
        "corpus_fingerprint",
        "expected_terminal_class",
        "citation_applicable",
        "migration_reason",
        "in_capability_denominator",
    }
    for case in CAPABILITY_CASES:
        data = case.to_dict()
        for key in required:
            assert key in data and data[key] is not None or data[key] is False


def test_migration_audit_covers_adv20() -> None:
    assert len(MIGRATION_AUDITS) == 20
    counts = migration_outcome_counts()
    assert counts["MIGRATED_VALID"] == 18
    assert counts["NEEDS_NEW_FIXTURE"] == 1
    assert counts["STILL_INVALID"] == 1
    assert MIGRATION_AUDIT_BY_ID["GQ-104"].migration_outcome == "NEEDS_NEW_FIXTURE"
    assert MIGRATION_AUDIT_BY_ID["GQ-110"].migration_outcome == "STILL_INVALID"


def test_ideal_trajectories_pass_all_stages() -> None:
    ideals = {
        "ADV-P1-ANS-001": MockTrajectory(
            case_id="ADV-P1-ANS-001",
            answerability_class="ANSWERABLE",
            retrieval_attempted=True,
            retrieval_hits=("adv-ch-001",),
            evidence_state="sufficient",
            terminal="finish",
            citations=("adv-ch-001",),
        ),
        "ADV-P1-UNA-001": MockTrajectory(
            case_id="ADV-P1-UNA-001",
            answerability_class="UNANSWERABLE_IN_CORPUS",
            retrieval_attempted=True,
            retrieval_hits=("adv-ch-101",),
            evidence_state="absent",
            terminal="refuse",
        ),
        "ADV-P1-PART-001": MockTrajectory(
            case_id="ADV-P1-PART-001",
            answerability_class="INSUFFICIENT_EVIDENCE",
            retrieval_attempted=True,
            retrieval_hits=("adv-ch-201",),
            evidence_state="partial",
            terminal="refuse",
        ),
        "ADV-P1-CON-001": MockTrajectory(
            case_id="ADV-P1-CON-001",
            answerability_class="CONFLICTED_EVIDENCE",
            retrieval_attempted=True,
            retrieval_hits=("adv-ch-301", "adv-ch-302"),
            evidence_state="conflicted",
            terminal="clarify",
            citations=("adv-ch-301",),
        ),
    }
    for case in CAPABILITY_CASES:
        result = evaluate_case(case, ideals[case.case_id])
        assert result.passed, (case.case_id, result.first_failed_stage)


def test_hard_controls_deterministic() -> None:
    for control_id in HARD_CONTROL_TRAJECTORIES:
        assert evaluate_hard_control(control_id) is True


def test_p1_manifest_matches_code() -> None:
    manifest = load_p1_manifest()
    p0_sha = manifest["p0_merge_sha"]
    expected = build_p1_manifest(p0_merge_sha=p0_sha)
    assert manifest["CAPABILITY_VALID_DENOMINATOR"] == expected[
        "CAPABILITY_VALID_DENOMINATOR"
    ]
    assert manifest["golden_rewrite"] is False
    assert manifest["runtime_rollout"] is False
