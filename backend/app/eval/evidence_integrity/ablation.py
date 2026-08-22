"""Gate C remediation P0 — offline matcher ablation (eval-only).

Compares BASELINE vs candidate matchers on the frozen 29-case ground truth.
Does **not** modify product matcher, StopPolicy, or runtime.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.eval.evidence_integrity.candidates import (
    CANDIDATES,
    THRESHOLD_DIAGNOSTICS,
    CandidateSpec,
    baseline_match,
    eval_match,
    threshold_relation,
)
from app.eval.evidence_integrity.cases import (
    F2_EVIDENCE,
    F2_FACT_X1,
    F2_FACT_X2,
    gate_c_cases,
)
from app.eval.evidence_integrity.runner import _best_relation_for_fact, _max_overlap, _overlap
from app.eval.evidence_integrity.schema import CaseResult, SuiteMetrics
from app.eval.evidence_integrity.scoring import aggregate, product_relation_to_eval, score_case
from app.services.agent.matcher import (
    EvidenceSnippet,
    MatchResult,
    _PARTIAL_OVERLAP,
    _SUPPORT_OVERLAP,
    _lexical_relation,
    apply_and_score,
)
from app.services.agent.stop_policy import StopKind, evaluate_stop
from app.services.agent.types import EvidenceState, FactGoal, FactKind, FactStatus

GATE_C_BASELINE = {
    "precision": 0.1667,
    "recall": 0.8000,
    "coverage_false_positive_rate": 0.8333,
    "unsafe_finish_enabling_fp_rate": 0.9091,
    "case_count": 29,
}


@dataclass(slots=True)
class CandidateReport:
    candidate_id: str
    description: str
    metrics: SuiteMetrics
    f2: dict[str, Any]
    delta: dict[str, float]
    false_negative_audit: list[dict[str, Any]] = field(default_factory=list)
    category_breakdown: dict[str, dict[str, Any]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "description": self.description,
            "metrics": self.metrics.to_dict(),
            "f1": _f1(self.metrics.precision, self.metrics.recall),
            "f2": self.f2,
            "delta_vs_baseline": self.delta,
            "false_negative_audit": self.false_negative_audit,
            "category_breakdown": self.category_breakdown,
        }


def _f1(precision: float, recall: float) -> float:
    if precision + recall == 0:
        return 0.0
    return round(2 * precision * recall / (precision + recall), 4)


def _match_for_candidate(
    spec: CandidateSpec,
    facts: tuple[FactGoal, ...],
    snippets: tuple[EvidenceSnippet, ...],
    *,
    only_uncovered: bool,
) -> MatchResult:
    if spec.relation_fn is not None:
        return eval_match(
            facts,
            snippets,
            spec.relation_fn,
            only_uncovered=only_uncovered,
            source=f"eval_{spec.candidate_id.lower()}",
        )
    assert spec.use_product_deterministic
    return baseline_match(facts, snippets, only_uncovered=only_uncovered)


def run_case_with_candidate(
    case: Any,
    spec: CandidateSpec,
) -> CaseResult:
    facts = [
        FactGoal(
            id="F1",
            text=case.fact_goal,
            kind=FactKind.lookup,
            required=True,
            status=FactStatus.missing,
        )
    ]
    if case.secondary_fact_goal:
        facts.append(
            FactGoal(
                id="F2",
                text=case.secondary_fact_goal,
                kind=FactKind.lookup,
                required=True,
                status=FactStatus.missing,
            )
        )

    snippets = tuple(
        EvidenceSnippet(evidence_id=f"e{i}", text=text, confidence=1.0)
        for i, text in enumerate(case.evidence_texts)
        if text.strip()
    )

    evidence = EvidenceState(facts=tuple(facts))
    status_before = facts[0].status

    match = _match_for_candidate(spec, tuple(facts), snippets, only_uncovered=False)
    if match.ok:
        evidence, match = apply_and_score(evidence, match)

    status_after = next(g.status for g in evidence.facts if g.id == "F1")
    product_rel = _best_relation_for_fact(match.items, "F1")
    if product_rel is None and snippets and spec.relation_fn is not None:
        product_rel = spec.relation_fn(case.fact_goal, snippets[0].text)
    elif product_rel is None and snippets:
        product_rel = _lexical_relation(case.fact_goal, snippets[0].text)

    actual = product_relation_to_eval(product_rel)
    overlap = _max_overlap(case.fact_goal, case.evidence_texts)

    stop_kind: str | None = None
    stop_reason: str | None = None
    if case.check_stop_propagation or case.is_f2_repro:
        signal = evaluate_stop(evidence, steps_used=2, max_steps=2)
        stop_kind = signal.kind.value if signal.kind else None
        stop_reason = signal.reason_code or None

    extras: dict[str, Any] = {
        "match_ok": match.ok,
        "match_error": match.error,
        "match_source": match.source,
        "item_count": len(match.items),
        "coverage_ratio": match.coverage_ratio if match.ok else 0.0,
        "candidate_id": spec.candidate_id,
    }
    if case.secondary_fact_goal:
        sec_status = next(g.status for g in evidence.facts if g.id == "F2")
        sec_rel = _best_relation_for_fact(match.items, "F2")
        extras["secondary"] = {
            "status_after": sec_status.value,
            "product_relation": sec_rel.value if sec_rel else None,
        }

    return score_case(
        case_id=case.case_id,
        category=case.category,
        expected=case.expected_relation,
        acceptable=case.acceptable_relations,
        actual=actual,
        product_relation=product_rel,
        status_before=status_before,
        status_after=status_after,
        overlap=overlap,
        support_threshold=_SUPPORT_OVERLAP,
        partial_threshold=_PARTIAL_OVERLAP,
        stop_kind=stop_kind,
        stop_reason=stop_reason,
        evidence_excerpt=" | ".join(case.evidence_texts)[:240],
        notes=case.notes or case.reason,
        extras=extras,
    )


def reproduce_f2_with_candidate(spec: CandidateSpec) -> dict[str, Any]:
    facts = (
        FactGoal(id="X1", text=F2_FACT_X1, required=True, status=FactStatus.missing),
        FactGoal(id="X2", text=F2_FACT_X2, required=True, status=FactStatus.missing),
    )
    snippet = EvidenceSnippet(evidence_id="unrelated", text=F2_EVIDENCE)
    match = _match_for_candidate(spec, facts, (snippet,), only_uncovered=True)
    evidence = EvidenceState(facts=facts)
    if match.ok:
        evidence, match = apply_and_score(evidence, match)
    after = {g.id: g.status.value for g in evidence.facts}

    x1_rel = _best_relation_for_fact(match.items, "X1")
    if x1_rel is None and spec.relation_fn is not None:
        x1_rel = spec.relation_fn(F2_FACT_X1, F2_EVIDENCE)
    elif x1_rel is None:
        x1_rel = _lexical_relation(F2_FACT_X1, F2_EVIDENCE)

    signal = evaluate_stop(evidence, steps_used=2, max_steps=2)
    baseline_reproduced = (
        after.get("X1") == FactStatus.covered.value
        and after.get("X2") == FactStatus.covered.value
        and signal.kind == StopKind.finish
        and signal.reason_code == "facts_covered"
    )
    unsafe_finish = (
        baseline_reproduced
        and signal.kind == StopKind.finish
        and signal.reason_code == "facts_covered"
    )
    return {
        "reproduced_under_baseline_bug": baseline_reproduced,
        "f2_relation": product_relation_to_eval(x1_rel).value,
        "product_relation": x1_rel.value if x1_rel else None,
        "fact_status_after": after,
        "unsafe_finish_enabled": unsafe_finish,
        "f2_fixed": not baseline_reproduced or after.get("X1") != FactStatus.covered.value,
        "stop_policy": {
            "kind": signal.kind.value if signal.kind else None,
            "reason_code": signal.reason_code,
        },
        "overlap_scores": {g.id: _overlap(g.text, F2_EVIDENCE) for g in facts},
    }


def _false_negative_audit(
    baseline_results: list[CaseResult],
    candidate_results: list[CaseResult],
) -> list[dict[str, Any]]:
    by_id = {r.case_id: r for r in baseline_results}
    audit: list[dict[str, Any]] = []
    for cand in candidate_results:
        base = by_id[cand.case_id]
        if base.true_positive and cand.false_negative:
            audit.append(
                {
                    "case_id": cand.case_id,
                    "category": cand.category,
                    "expected": cand.expected_relation,
                    "baseline_actual": base.actual_relation,
                    "candidate_actual": cand.actual_relation,
                    "baseline_status": base.fact_status_after,
                    "candidate_status": cand.fact_status_after,
                }
            )
        elif base.matched and not cand.matched and cand.false_negative:
            audit.append(
                {
                    "case_id": cand.case_id,
                    "category": cand.category,
                    "expected": cand.expected_relation,
                    "baseline_actual": base.actual_relation,
                    "candidate_actual": cand.actual_relation,
                    "note": "acceptable_match_lost",
                }
            )
    return audit


def _category_breakdown(results: list[CaseResult]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for cat in sorted({r.category for r in results}):
        subset = [r for r in results if r.category == cat]
        out[cat] = {
            "count": len(subset),
            "matched": sum(1 for r in subset if r.matched),
            "false_positive": sum(1 for r in subset if r.false_positive),
            "false_negative": sum(1 for r in subset if r.false_negative),
            "coverage_false_positive": sum(1 for r in subset if r.coverage_false_positive),
            "unsafe_finish_enabling": sum(1 for r in subset if r.unsafe_finish_enabling),
            "contradiction_correct": sum(1 for r in subset if r.contradiction_correct),
            "partial_correct": sum(1 for r in subset if r.partial_correct),
        }
    return out


def _delta(metrics: SuiteMetrics) -> dict[str, float]:
    return {
        "precision": round(metrics.precision - GATE_C_BASELINE["precision"], 4),
        "recall": round(metrics.recall - GATE_C_BASELINE["recall"], 4),
        "coverage_false_positive_rate": round(
            metrics.coverage_false_positive_rate
            - GATE_C_BASELINE["coverage_false_positive_rate"],
            4,
        ),
        "unsafe_finish_enabling_fp_rate": round(
            metrics.unsafe_finish_enabling_fp_rate
            - GATE_C_BASELINE["unsafe_finish_enabling_fp_rate"],
            4,
        ),
        "false_negative_rate": round(metrics.false_negative_rate, 4),
    }


def run_candidate(spec: CandidateSpec) -> tuple[list[CaseResult], CandidateReport]:
    cases = gate_c_cases()
    results = [run_case_with_candidate(c, spec) for c in cases]
    f2 = reproduce_f2_with_candidate(spec)
    metrics = aggregate(results, f2_reproduced=bool(f2["reproduced_under_baseline_bug"]))
    report = CandidateReport(
        candidate_id=spec.candidate_id,
        description=spec.description,
        metrics=metrics,
        f2=f2,
        delta=_delta(metrics),
        category_breakdown=_category_breakdown(results),
    )
    return results, report


def run_ablation(
    *,
    include_threshold_diagnostics: bool = True,
) -> dict[str, Any]:
    cases = gate_c_cases()
    baseline_results, baseline_report = run_candidate(
        next(c for c in CANDIDATES if c.candidate_id == "BASELINE")
    )

    baseline_ok = (
        baseline_report.metrics.case_count == GATE_C_BASELINE["case_count"]
        and baseline_report.metrics.precision == GATE_C_BASELINE["precision"]
        and baseline_report.metrics.recall == GATE_C_BASELINE["recall"]
        and baseline_report.metrics.coverage_false_positive_rate
        == GATE_C_BASELINE["coverage_false_positive_rate"]
        and baseline_report.metrics.unsafe_finish_enabling_fp_rate
        == GATE_C_BASELINE["unsafe_finish_enabling_fp_rate"]
        and baseline_report.f2["reproduced_under_baseline_bug"] is True
    )

    candidate_reports: list[CandidateReport] = []
    candidate_results_map: dict[str, list[CaseResult]] = {}
    for spec in CANDIDATES:
        if spec.candidate_id == "BASELINE":
            candidate_reports.append(baseline_report)
            candidate_results_map[spec.candidate_id] = baseline_results
            continue
        results, report = run_candidate(spec)
        report.false_negative_audit = _false_negative_audit(baseline_results, results)
        candidate_reports.append(report)
        candidate_results_map[spec.candidate_id] = results

    threshold_reports: list[dict[str, Any]] = []
    if include_threshold_diagnostics:
        for label, threshold in THRESHOLD_DIAGNOSTICS:
            spec = CandidateSpec(
                candidate_id=label,
                description=f"Threshold-only diagnostic support_overlap={threshold}",
                relation_fn=threshold_relation(threshold),
            )
            _, report = run_candidate(spec)
            threshold_reports.append(report.to_dict())

    recommendation = choose_recommendation(candidate_reports)

    return {
        "gate": "Gate C Remediation P0 — Offline Matcher Ablation",
        "master_expected": "48a86e43b1c7ace34a136a5815281c6e328cc05f",
        "baseline_reproduced": baseline_ok,
        "case_count": len(cases),
        "frozen_baseline": GATE_C_BASELINE,
        "baseline": baseline_report.to_dict(),
        "candidates": [r.to_dict() for r in candidate_reports if r.candidate_id != "BASELINE"],
        "threshold_diagnostics": threshold_reports,
        "recommendation": recommendation,
        "scope_audit": {
            "matcher_modified": False,
            "threshold_modified": False,
            "stop_policy_modified": False,
            "runtime_modified": False,
            "golden_modified": False,
            "llm_called": False,
            "flags_changed": False,
            "rollout": False,
        },
    }


def choose_recommendation(reports: list[CandidateReport]) -> dict[str, Any]:
    """Pick best non-baseline candidate using Gate C remediation priorities."""
    scored: list[tuple[float, CandidateReport]] = []
    for report in reports:
        if report.candidate_id == "BASELINE":
            continue
        m = report.metrics
        f2 = report.f2
        if not f2.get("f2_fixed"):
            continue
        if m.recall < 0.70:
            continue
        # Lower unsafe finish + coverage FP is better; higher precision/recall better.
        score = (
            (1.0 - m.unsafe_finish_enabling_fp_rate) * 5.0
            + (1.0 - m.coverage_false_positive_rate) * 3.0
            + m.precision * 2.0
            + m.recall * 1.5
            - m.false_negative_rate * 1.0
        )
        scored.append((score, report))

    if not scored:
        fallback = next((r for r in reports if r.candidate_id == "A+B+C"), None)
        fallback = fallback or next((r for r in reports if r.candidate_id == "A+B"), None)
        best = fallback or next(r for r in reports if r.candidate_id == "B")
    else:
        scored.sort(key=lambda item: item[0], reverse=True)
        best = scored[0][1]
        tied = [item[1] for item in scored if abs(item[0] - scored[0][0]) < 1e-9]
        for preferred in ("A+B+C", "A+B", "B", "C", "A"):
            match = next((r for r in tied if r.candidate_id == preferred), None)
            if match is not None:
                best = match
                break

    tradeoff = {
        "safety": (
            f"unsafe_finish {GATE_C_BASELINE['unsafe_finish_enabling_fp_rate']:.4f}"
            f" -> {best.metrics.unsafe_finish_enabling_fp_rate:.4f}; "
            f"coverage_fp {GATE_C_BASELINE['coverage_false_positive_rate']:.4f}"
            f" -> {best.metrics.coverage_false_positive_rate:.4f}"
        ),
        "recall": (
            f"{GATE_C_BASELINE['recall']:.4f} -> {best.metrics.recall:.4f} "
            f"(FN audit {len(best.false_negative_audit)} cases)"
        ),
        "complexity": "Deterministic regex/token guards + claim heuristics; no LLM",
        "determinism": "Fully offline; CI-safe",
        "runtime_cost": "O(tokens) per fact-evidence pair; comparable to lexical matcher",
        "model_dependency": "None",
        "rollback": "Eval-only in this PR; product rollback remains flag/threshold unchanged",
        "maintainability": "Guards isolated in eval/candidates.py until product design sign-off",
    }

    return {
        "recommended_fix": best.candidate_id,
        "recommended_product_design": (
            "Apply deterministic guards (value/year/entity/negation) before emitting "
            "supports; require answer-bearing content for lookup/value FactGoals; "
            "cap lexical overlap at partial unless strong-support passes (A+B+C policy)."
            if best.candidate_id == "A+B+C"
            else best.description
        ),
        "do_not_implement_yet": True,
        "best_candidate": best.to_dict(),
        "tradeoff": tradeoff,
        "ready_for_matcher_fix_implementation": best.f2.get("f2_fixed") is True
        and best.metrics.recall >= 0.70
        and best.metrics.unsafe_finish_enabling_fp_rate <= 0.15,
        "runtime_rollout_ready": False,
    }


def format_summary(report: dict[str, Any]) -> str:
    """Human-readable summary for tests / CLI."""
    lines = [
        f"baseline_reproduced={report['baseline_reproduced']}",
        f"cases={report['case_count']}",
    ]
    base = report["baseline"]["metrics"]
    lines.append(
        "BASELINE "
        f"precision={base['precision']} recall={base['recall']} "
        f"coverage_fp={base['coverage_false_positive_rate']} "
        f"unsafe={base['unsafe_finish_enabling_fp_rate']}"
    )
    for cand in report["candidates"]:
        m = cand["metrics"]
        f2 = cand["f2"]
        lines.append(
            f"{cand['candidate_id']} "
            f"precision={m['precision']} recall={m['recall']} "
            f"coverage_fp={m['coverage_false_positive_rate']} "
            f"unsafe={m['unsafe_finish_enabling_fp_rate']} "
            f"f2_fixed={f2['f2_fixed']}"
        )
    rec = report["recommendation"]
    lines.append(f"RECOMMENDED={rec['recommended_fix']}")
    return "\n".join(lines)
