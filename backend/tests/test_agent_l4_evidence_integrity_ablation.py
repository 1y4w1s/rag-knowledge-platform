"""Gate C Remediation P0 — offline matcher ablation tests (eval-only)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from app.eval.evidence_integrity.ablation import (
    GATE_C_BASELINE,
    choose_recommendation,
    run_ablation,
    run_candidate,
)
from app.eval.evidence_integrity.candidates import CANDIDATES
from app.eval.evidence_integrity.cases import gate_c_cases
from app.eval.evidence_integrity.runner import run_suite

BACKEND_ROOT = Path(__file__).resolve().parents[1]
MATCHER_PATH = BACKEND_ROOT / "app" / "services" / "agent" / "matcher.py"
MATCHER_RUNTIME_PATH = BACKEND_ROOT / "app" / "services" / "agent" / "matcher_runtime.py"
STOP_POLICY_PATH = BACKEND_ROOT / "app" / "services" / "agent" / "stop_policy.py"
RUNTIME_PATH = BACKEND_ROOT / "app" / "services" / "agent" / "runtime.py"


def test_ablation_scope_audit_paths_exist() -> None:
    """Scope audit: ablation references product paths that must remain importable."""
    assert MATCHER_PATH.is_file()
    assert MATCHER_RUNTIME_PATH.is_file()
    assert STOP_POLICY_PATH.is_file()
    assert RUNTIME_PATH.is_file()


def test_gate_c_baseline_reproduced_in_ablation() -> None:
    report = run_ablation(include_threshold_diagnostics=False)
    assert report["baseline_reproduced"] is True
    assert report["case_count"] == 29
    base = report["baseline"]["metrics"]
    assert base["precision"] == GATE_C_BASELINE["precision"]
    assert base["recall"] == GATE_C_BASELINE["recall"]
    assert base["coverage_false_positive_rate"] == GATE_C_BASELINE["coverage_false_positive_rate"]
    assert base["unsafe_finish_enabling_fp_rate"] == GATE_C_BASELINE[
        "unsafe_finish_enabling_fp_rate"
    ]


def test_ablation_has_required_candidates() -> None:
    report = run_ablation(include_threshold_diagnostics=False)
    ids = {item["candidate_id"] for item in report["candidates"]}
    assert {"A", "B", "C"} <= ids
    assert len(gate_c_cases()) == 29


def test_candidate_b_fixes_f2_and_reduces_unsafe_finish() -> None:
    spec = next(c for c in CANDIDATES if c.candidate_id == "B")
    _, report = run_candidate(spec)
    assert report.f2["f2_fixed"] is True
    assert report.f2["unsafe_finish_enabled"] is False
    assert report.metrics.unsafe_finish_enabling_fp_rate == 0.0
    assert report.metrics.coverage_false_positive_rate == 0.0
    assert report.metrics.recall >= 0.70


def test_candidate_a_improves_but_does_not_fix_f2_alone() -> None:
    spec = next(c for c in CANDIDATES if c.candidate_id == "A")
    _, report = run_candidate(spec)
    assert report.metrics.precision > GATE_C_BASELINE["precision"]
    assert report.metrics.coverage_false_positive_rate < GATE_C_BASELINE[
        "coverage_false_positive_rate"
    ]
    assert report.f2["f2_fixed"] is False


def test_threshold_diagnostic_does_not_replace_guarded_candidates() -> None:
    report = run_ablation(include_threshold_diagnostics=True)
    by_id = {item["candidate_id"]: item for item in report["threshold_diagnostics"]}
    assert by_id["THRESHOLD_0.45"]["metrics"]["precision"] == GATE_C_BASELINE["precision"]
    assert by_id["THRESHOLD_0.55"]["f2"]["f2_fixed"] is False
    best = report["recommendation"]["best_candidate"]
    assert best["candidate_id"] in {"B", "A+B", "A+B+C", "C"}


def test_false_negative_audit_documents_paraphrase_tradeoff() -> None:
    spec = next(c for c in CANDIDATES if c.candidate_id == "B")
    results, report = run_candidate(spec)
    i1 = next(r for r in results if r.case_id == "I1")
    assert i1.expected_relation == "support"
    assert i1.actual_relation == "partial"
    assert i1.false_negative is True
    assert i1.category == "paraphrase"
    assert report.metrics.false_negative >= 1


def test_recommendation_prefers_guarded_candidate_over_threshold_only() -> None:
    reports = [run_candidate(spec)[1] for spec in CANDIDATES]
    rec = choose_recommendation(reports)
    assert rec["recommended_fix"] in {"A+B+C", "A+B", "B", "C"}
    assert rec["do_not_implement_yet"] is True
    assert rec["runtime_rollout_ready"] is False


def test_gate_c_harness_still_passes() -> None:
    _, metrics, f2 = run_suite()
    assert metrics.case_count == 29
    assert f2["reproduced"] is True


if __name__ == "__main__":
    raise SystemExit(
        subprocess.call(
            [sys.executable, "-m", "pytest", __file__, "-q"],
            cwd=str(BACKEND_ROOT),
        )
    )
