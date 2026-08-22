"""Gate C runner — calls real EvidenceMatcher / deterministic_match (no LLM)."""

from __future__ import annotations

from typing import Any

from app.eval.evidence_integrity.cases import F2_EVIDENCE, F2_FACT_X1, F2_FACT_X2, gate_c_cases
from app.eval.evidence_integrity.schema import (
    SCHEMA_VERSION,
    CaseResult,
    IntegrityCase,
    SuiteMetrics,
)
from app.eval.evidence_integrity.scoring import (
    aggregate,
    product_relation_to_eval,
    score_case,
)
from app.services.agent.matcher import (
    EvidenceSnippet,
    _PARTIAL_OVERLAP,
    _SUPPORT_OVERLAP,
    _lexical_relation,
    _tokens,
    apply_and_score,
    deterministic_match,
)
from app.services.agent.stop_policy import StopKind, evaluate_stop
from app.services.agent.types import (
    EvidenceRelation,
    EvidenceState,
    FactGoal,
    FactKind,
    FactStatus,
)


def _overlap(fact_text: str, evidence_text: str) -> float | None:
    ft, et = _tokens(fact_text), _tokens(evidence_text)
    if not ft or not et:
        return None
    return len(ft & et) / len(ft)


def _best_relation_for_fact(
    match_items: tuple[Any, ...],
    fact_id: str,
) -> EvidenceRelation | None:
    """Mirror matcher observation ranking for one fact across items."""
    rank = {
        EvidenceRelation.partial: 1,
        EvidenceRelation.supports: 2,
        EvidenceRelation.resolves: 3,
        EvidenceRelation.contradicts: 4,
    }
    best: EvidenceRelation | None = None
    for item in match_items:
        candidates: list[EvidenceRelation] = []
        if fact_id in item.contradicts:
            candidates.append(EvidenceRelation.contradicts)
        if fact_id in item.resolves:
            candidates.append(EvidenceRelation.resolves)
        if fact_id in item.supports:
            candidates.append(EvidenceRelation.supports)
        if fact_id in item.partials:
            candidates.append(EvidenceRelation.partial)
        for rel in candidates:
            if best is None or rank[rel] > rank[best]:
                best = rel
    return best


def _max_overlap(fact_text: str, evidence_texts: tuple[str, ...]) -> float | None:
    scores = [_overlap(fact_text, t) for t in evidence_texts if t.strip()]
    scores = [s for s in scores if s is not None]
    return max(scores) if scores else None


def run_case(case: IntegrityCase) -> CaseResult:
    """Run one characterization case through real deterministic matcher + StopPolicy."""
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

    match = deterministic_match(facts, snippets, only_uncovered=False)
    if match.ok:
        evidence, match = apply_and_score(evidence, match)

    status_after = next(g.status for g in evidence.facts if g.id == "F1")
    product_rel = _best_relation_for_fact(match.items, "F1")
    # Fallback: per-snippet lexical if no items (also surfaces threshold audit)
    if product_rel is None and snippets:
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
        "supports_threshold_constant": _SUPPORT_OVERLAP,
        "partial_threshold_constant": _PARTIAL_OVERLAP,
    }
    if case.secondary_fact_goal:
        sec_status = next(g.status for g in evidence.facts if g.id == "F2")
        sec_rel = _best_relation_for_fact(match.items, "F2")
        extras["secondary"] = {
            "fact_goal": case.secondary_fact_goal,
            "expected": (
                case.secondary_expected.value if case.secondary_expected else None
            ),
            "status_after": sec_status.value,
            "product_relation": sec_rel.value if sec_rel else None,
            "eval_relation": product_relation_to_eval(sec_rel).value,
            "overlap": _max_overlap(case.secondary_fact_goal, case.evidence_texts),
        }

    excerpt = " | ".join(case.evidence_texts)[:240]
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
        evidence_excerpt=excerpt,
        notes=case.notes or case.reason,
        extras=extras,
    )


def reproduce_f2() -> dict[str, Any]:
    """Stable offline F2 false-positive reproduction (no LM Studio)."""
    facts = (
        FactGoal(id="X1", text=F2_FACT_X1, required=True, status=FactStatus.missing),
        FactGoal(id="X2", text=F2_FACT_X2, required=True, status=FactStatus.missing),
    )
    snippet = EvidenceSnippet(evidence_id="unrelated", text=F2_EVIDENCE)
    before = {g.id: g.status.value for g in facts}
    match = deterministic_match(facts, (snippet,), only_uncovered=True)
    evidence = EvidenceState(facts=facts)
    if match.ok:
        evidence, match = apply_and_score(evidence, match)
    after = {g.id: g.status.value for g in evidence.facts}
    overlaps = {
        g.id: _overlap(g.text, F2_EVIDENCE) for g in facts
    }
    lexical = {
        g.id: (
            _lexical_relation(g.text, F2_EVIDENCE).value
            if _lexical_relation(g.text, F2_EVIDENCE)
            else None
        )
        for g in facts
    }
    signal = evaluate_stop(evidence, steps_used=2, max_steps=2)
    reproduced = (
        after.get("X1") == FactStatus.covered.value
        and after.get("X2") == FactStatus.covered.value
        and signal.kind == StopKind.finish
        and signal.reason_code == "facts_covered"
    )
    return {
        "reproduced": reproduced,
        "fact_goals": {"X1": F2_FACT_X1, "X2": F2_FACT_X2},
        "evidence_excerpt": F2_EVIDENCE,
        "matcher_input": {
            "facts": [g.text for g in facts],
            "snippets": [F2_EVIDENCE],
            "source": "deterministic_match",
        },
        "matcher_output": {
            "ok": match.ok,
            "error": match.error,
            "observation": [
                (fid, rel.value) for fid, rel in match.observation.relations
            ],
            "items_supports": [list(i.supports) for i in match.items],
        },
        "fact_status_before": before,
        "fact_status_after": after,
        "overlap_scores": overlaps,
        "lexical_relations": lexical,
        "support_threshold": _SUPPORT_OVERLAP,
        "partial_threshold": _PARTIAL_OVERLAP,
        "threshold_behavior": (
            "above_support"
            if all((overlaps[k] or 0) >= _SUPPORT_OVERLAP for k in overlaps)
            else "other"
        ),
        "why_system_says_covered": (
            "Character-token Jaccard overlap of FactGoal vs EXCERPT_UNRELATED "
            f"reaches {_SUPPORT_OVERLAP}+ because both share 住/宿/标/准; "
            "deterministic_match emits supports → ledger covered → StopPolicy "
            "facts_covered finish. RELATED≠SUPPORTED."
        ),
        "stop_policy": {
            "kind": signal.kind.value if signal.kind else None,
            "reason_code": signal.reason_code,
            "ready": signal.ready,
        },
        "root_cause_layer": "MATCHER",
        "stop_policy_root_cause": False,
    }


def run_suite(
    cases: tuple[IntegrityCase, ...] | None = None,
) -> tuple[list[CaseResult], SuiteMetrics, dict[str, Any]]:
    case_list = cases if cases is not None else gate_c_cases()
    results = [run_case(c) for c in case_list]
    f2 = reproduce_f2()
    metrics = aggregate(results, f2_reproduced=bool(f2["reproduced"]))
    return results, metrics, f2


def build_report(
    results: list[CaseResult],
    metrics: SuiteMetrics,
    f2: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "gate": "Gate C — Evidence Integrity Characterization",
        "matcher_audit": {
            "algorithm": "deterministic lexical token overlap",
            "token_pattern": r"[A-Za-z0-9_]+|[\u4e00-\u9fff]",
            "support_overlap_threshold": _SUPPORT_OVERLAP,
            "partial_overlap_threshold": _PARTIAL_OVERLAP,
            "negation_heuristic": True,
            "semantic_signal": False,
            "embedding": False,
            "llm_judge": False,
            "explicit_support_labels": "fixture path only",
            "entrypoints": [
                "deterministic_match",
                "EvidenceMatcher.match (flag-gated)",
            ],
        },
        "f2_reproduction": f2,
        "metrics": metrics.to_dict(),
        "results": [r.to_dict() for r in results],
        "candidate_fixes_note": (
            "Characterization only — see Gate C report; do not implement here."
        ),
    }
