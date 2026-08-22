"""Gate C scoring: map product matcher output → eval metrics / taxonomy."""

from __future__ import annotations

from collections import Counter
from typing import Any

from app.eval.evidence_integrity.schema import (
    CaseResult,
    EvalRelation,
    FailureTaxonomy,
    SuiteMetrics,
)
from app.services.agent.types import EvidenceRelation, FactStatus

_PRODUCT_TO_EVAL = {
    EvidenceRelation.supports: EvalRelation.support,
    EvidenceRelation.resolves: EvalRelation.support,
    EvidenceRelation.partial: EvalRelation.partial,
    EvidenceRelation.contradicts: EvalRelation.contradict,
}


def product_relation_to_eval(rel: EvidenceRelation | None) -> EvalRelation:
    if rel is None:
        return EvalRelation.irrelevant
    return _PRODUCT_TO_EVAL.get(rel, EvalRelation.irrelevant)


def status_implies_full_cover(status: FactStatus) -> bool:
    return status == FactStatus.covered


def classify_threshold_band(
    overlap: float | None,
    *,
    support_threshold: float,
    partial_threshold: float,
) -> str:
    if overlap is None:
        return "no_score"
    if overlap >= support_threshold:
        margin = overlap - support_threshold
        if margin <= 0.08:
            return "near_support"
        return "above_support"
    if overlap >= partial_threshold:
        return "partial_band"
    return "below"


def classify_failure(
    *,
    category: str,
    expected: EvalRelation,
    actual: EvalRelation,
    coverage_fp: bool,
    false_negative: bool,
) -> FailureTaxonomy:
    if actual == expected or (
        not coverage_fp and not false_negative and actual != EvalRelation.support
    ):
        # matched or soft TN — refine below
        pass

    if coverage_fp or (
        expected in (EvalRelation.irrelevant, EvalRelation.partial, EvalRelation.contradict)
        and actual == EvalRelation.support
    ):
        mapping = {
            "keyword_overlap": FailureTaxonomy.LEXICAL_OVERLAP_FALSE_POSITIVE,
            "f2_repro": FailureTaxonomy.LEXICAL_OVERLAP_FALSE_POSITIVE,
            "wrong_value": FailureTaxonomy.VALUE_MISMATCH_FALSE_POSITIVE,
            "negation": FailureTaxonomy.NEGATION_FALSE_POSITIVE,
            "entity_mismatch": FailureTaxonomy.ENTITY_MISMATCH_FALSE_POSITIVE,
            "temporal_mismatch": FailureTaxonomy.TEMPORAL_MISMATCH_FALSE_POSITIVE,
            "scope_mismatch": FailureTaxonomy.SCOPE_MISMATCH_FALSE_POSITIVE,
            "partial_support": FailureTaxonomy.PARTIAL_AS_FULL_FALSE_POSITIVE,
            "distractor": FailureTaxonomy.DISTRACTOR_FALSE_POSITIVE,
            "conflict": FailureTaxonomy.CONTRADICTION_MISCLASSIFIED,
            "no_evidence": FailureTaxonomy.LEXICAL_OVERLAP_FALSE_POSITIVE,
        }
        return mapping.get(category, FailureTaxonomy.UNKNOWN)

    if false_negative and category == "paraphrase":
        return FailureTaxonomy.SEMANTIC_PARAPHRASE_FALSE_NEGATIVE

    if expected == EvalRelation.contradict and actual != EvalRelation.contradict:
        return FailureTaxonomy.CONTRADICTION_MISCLASSIFIED

    if false_negative:
        return FailureTaxonomy.UNKNOWN

    return FailureTaxonomy.NONE


def score_case(
    *,
    case_id: str,
    category: str,
    expected: EvalRelation,
    acceptable: tuple[EvalRelation, ...],
    actual: EvalRelation,
    product_relation: EvidenceRelation | None,
    status_before: FactStatus,
    status_after: FactStatus,
    overlap: float | None,
    support_threshold: float,
    partial_threshold: float,
    stop_kind: str | None,
    stop_reason: str | None,
    evidence_excerpt: str,
    notes: str = "",
    extras: dict[str, Any] | None = None,
) -> CaseResult:
    allowed = {expected, *acceptable}
    matched = actual in allowed

    # Binary framing for precision/recall on SUPPORT decision
    expect_support = expected == EvalRelation.support
    pred_support = actual == EvalRelation.support

    true_positive = expect_support and pred_support
    false_positive = (not expect_support) and pred_support
    false_negative = expect_support and (not pred_support)
    true_negative = (not expect_support) and (not pred_support)

    # Stronger coverage FP: should not full-cover required fact
    should_not_cover = expected != EvalRelation.support
    coverage_fp = should_not_cover and status_implies_full_cover(status_after)

    contradiction_correct = (
        expected == EvalRelation.contradict and actual == EvalRelation.contradict
    )
    partial_correct = expected == EvalRelation.partial and actual == EvalRelation.partial

    # Unsafe finish: matcher FP → StopPolicy would finish with facts_covered
    unsafe = bool(
        coverage_fp
        and stop_kind == "finish"
        and (stop_reason or "") == "facts_covered"
    )

    taxonomy = classify_failure(
        category=category,
        expected=expected,
        actual=actual,
        coverage_fp=coverage_fp,
        false_negative=false_negative,
    )

    if coverage_fp or false_positive:
        root = "MATCHER"
    elif unsafe and not coverage_fp:
        root = "STOP"
    else:
        root = "NONE"

    return CaseResult(
        case_id=case_id,
        category=category,
        expected_relation=expected.value,
        actual_relation=actual.value,
        product_relation=product_relation.value if product_relation else None,
        fact_status_before=status_before.value,
        fact_status_after=status_after.value,
        overlap_score=None if overlap is None else round(overlap, 6),
        support_threshold=support_threshold,
        partial_threshold=partial_threshold,
        threshold_band=classify_threshold_band(
            overlap,
            support_threshold=support_threshold,
            partial_threshold=partial_threshold,
        ),
        matched=matched,
        coverage_false_positive=coverage_fp,
        false_positive=false_positive or coverage_fp,
        false_negative=false_negative,
        true_positive=true_positive,
        true_negative=true_negative and not coverage_fp,
        contradiction_correct=contradiction_correct,
        partial_correct=partial_correct,
        unsafe_finish_enabling=unsafe,
        stop_kind=stop_kind,
        stop_reason=stop_reason,
        failure_taxonomy=taxonomy.value,
        root_cause_layer=root,
        evidence_excerpt=evidence_excerpt[:240],
        notes=notes,
        extras=extras or {},
    )


def aggregate(results: list[CaseResult], *, f2_reproduced: bool) -> SuiteMetrics:
    n = len(results)
    tp = sum(1 for r in results if r.true_positive)
    tn = sum(1 for r in results if r.true_negative)
    fp = sum(1 for r in results if r.false_positive)
    fn = sum(1 for r in results if r.false_negative)
    cov_fp = sum(1 for r in results if r.coverage_false_positive)
    unsafe = sum(1 for r in results if r.unsafe_finish_enabling)
    cc = sum(1 for r in results if r.contradiction_correct)
    pc = sum(1 for r in results if r.partial_correct)

    # Coverage-FP denominator: cases that must NOT full-cover
    non_support = [r for r in results if r.expected_relation != EvalRelation.support.value]
    cov_den = len(non_support) or 1
    # Unsafe finish rate over cases that check propagation or had coverage FP path
    stop_checked = [
        r
        for r in results
        if r.expected_relation != EvalRelation.support.value and r.stop_kind is not None
    ]
    unsafe_den = len(stop_checked) or 1

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    # classic rates over binary labels
    neg = tn + fp
    pos = tp + fn
    fpr = fp / neg if neg else 0.0
    fnr = fn / pos if pos else 0.0

    by_cat: dict[str, dict[str, Any]] = {}
    cats = sorted({r.category for r in results})
    for cat in cats:
        subset = [r for r in results if r.category == cat]
        by_cat[cat] = {
            "count": len(subset),
            "false_positive": sum(1 for r in subset if r.false_positive),
            "false_negative": sum(1 for r in subset if r.false_negative),
            "coverage_false_positive": sum(1 for r in subset if r.coverage_false_positive),
            "unsafe_finish_enabling": sum(1 for r in subset if r.unsafe_finish_enabling),
            "matched": sum(1 for r in subset if r.matched),
        }

    tax = Counter(r.failure_taxonomy for r in results if r.failure_taxonomy != "NONE")

    return SuiteMetrics(
        case_count=n,
        true_positive=tp,
        true_negative=tn,
        false_positive=fp,
        false_negative=fn,
        contradiction_correct=cc,
        partial_correct=pc,
        precision=round(precision, 4),
        recall=round(recall, 4),
        false_positive_rate=round(fpr, 4),
        false_negative_rate=round(fnr, 4),
        coverage_false_positive_rate=round(cov_fp / cov_den, 4),
        unsafe_finish_enabling_fp_rate=round(unsafe / unsafe_den, 4),
        coverage_false_positive_count=cov_fp,
        unsafe_finish_enabling_count=unsafe,
        by_category=by_cat,
        failure_taxonomy_counts=dict(tax),
        f2_reproduced=f2_reproduced,
    )
