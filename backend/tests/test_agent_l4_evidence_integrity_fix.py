"""Gate C Remediation P1 — product hardened EvidenceMatcher regression tests."""

from __future__ import annotations

from app.eval.evidence_integrity.ablation import GATE_C_BASELINE, run_candidate
from app.eval.evidence_integrity.candidates import CANDIDATES, eval_match
from app.eval.evidence_integrity.cases import (
    CASE_BY_ID,
    F2_EVIDENCE,
    F2_FACT_X1,
    F2_FACT_X2,
    gate_c_cases,
)
from app.eval.evidence_integrity.runner import _best_relation_for_fact
from app.eval.evidence_integrity.scoring import aggregate, product_relation_to_eval, score_case
from app.services.agent.matcher import (
    EvidenceSnippet,
    _hardened_relation,
    _lexical_relation,
    apply_and_score,
    deterministic_match,
    match_from_fixture,
)
from app.services.agent.stop_policy import StopKind, evaluate_stop
from app.services.agent.types import (
    EvidenceRelation,
    EvidenceState,
    FactGoal,
    FactKind,
    FactStatus,
)

PRODUCT_HARDENED_EXPECTED = {
    "precision": 1.0000,
    "recall": 0.8000,
    "coverage_false_positive_rate": 0.0000,
    "unsafe_finish_enabling_fp_rate": 0.0000,
}


def _product_match(
    facts: tuple[FactGoal, ...],
    snippets: tuple[EvidenceSnippet, ...],
    *,
    only_uncovered: bool = False,
):
    return deterministic_match(facts, snippets, only_uncovered=only_uncovered)


def _run_product_gate_c_suite() -> tuple[list, object, dict]:
    results = []
    for case in gate_c_cases():
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
        match = _product_match(tuple(facts), snippets, only_uncovered=False)
        if match.ok:
            evidence, match = apply_and_score(evidence, match)
        status_after = next(g.status for g in evidence.facts if g.id == "F1")
        product_rel = _best_relation_for_fact(match.items, "F1")
        if product_rel is None and snippets:
            product_rel = _hardened_relation(case.fact_goal, snippets[0].text)
        stop_kind = stop_reason = None
        if case.check_stop_propagation or case.is_f2_repro:
            signal = evaluate_stop(evidence, steps_used=2, max_steps=2)
            stop_kind = signal.kind.value if signal.kind else None
            stop_reason = signal.reason_code or None
        results.append(
            score_case(
                case_id=case.case_id,
                category=case.category,
                expected=case.expected_relation,
                acceptable=case.acceptable_relations,
                actual=product_relation_to_eval(product_rel),
                product_relation=product_rel,
                status_before=status_before,
                status_after=status_after,
                overlap=None,
                support_threshold=0.45,
                partial_threshold=0.22,
                stop_kind=stop_kind,
                stop_reason=stop_reason,
                evidence_excerpt=" | ".join(case.evidence_texts)[:240],
                notes=case.notes or case.reason,
                extras={"match_source": match.source},
            )
        )
    f2 = _reproduce_f2_product()
    metrics = aggregate(results, f2_reproduced=bool(f2["legacy_baseline_reproduced"]))
    return results, metrics, f2


def _reproduce_f2_product() -> dict:
    facts = (
        FactGoal(id="X1", text=F2_FACT_X1, required=True, status=FactStatus.missing),
        FactGoal(id="X2", text=F2_FACT_X2, required=True, status=FactStatus.missing),
    )
    snippet = EvidenceSnippet(evidence_id="unrelated", text=F2_EVIDENCE)
    legacy_match = eval_match(
        facts, (snippet,), _lexical_relation, only_uncovered=True, source="legacy"
    )
    evidence = EvidenceState(facts=facts)
    match = _product_match(facts, (snippet,), only_uncovered=True)
    if match.ok:
        evidence, match = apply_and_score(evidence, match)
    after = {g.id: g.status.value for g in evidence.facts}
    x1_rel = _best_relation_for_fact(match.items, "X1") or _hardened_relation(
        F2_FACT_X1, F2_EVIDENCE
    )
    signal = evaluate_stop(evidence, steps_used=2, max_steps=2)
    legacy_evidence = EvidenceState(facts=facts)
    if legacy_match.ok:
        legacy_evidence, _ = apply_and_score(legacy_evidence, legacy_match)
    legacy_after = {g.id: g.status.value for g in legacy_evidence.facts}
    legacy_signal = evaluate_stop(legacy_evidence, steps_used=2, max_steps=2)
    legacy_reproduced = (
        legacy_after.get("X1") == FactStatus.covered.value
        and legacy_after.get("X2") == FactStatus.covered.value
        and legacy_signal.kind == StopKind.finish
        and legacy_signal.reason_code == "facts_covered"
    )
    return {
        "legacy_baseline_reproduced": legacy_reproduced,
        "f2_relation": product_relation_to_eval(x1_rel).value,
        "product_relation": x1_rel.value if x1_rel else None,
        "fact_status_after": after,
        "unsafe_finish_enabled": signal.kind == StopKind.finish
        and signal.reason_code == "facts_covered",
        "f2_fixed": after.get("X1") != FactStatus.covered.value,
        "stop_policy": {
            "kind": signal.kind.value if signal.kind else None,
            "reason_code": signal.reason_code,
        },
    }


def test_legacy_baseline_still_reproducible() -> None:
    spec = next(c for c in CANDIDATES if c.candidate_id == "BASELINE")
    _, report = run_candidate(spec)
    assert report.metrics.precision == GATE_C_BASELINE["precision"]
    assert report.metrics.recall == GATE_C_BASELINE["recall"]
    assert report.metrics.coverage_false_positive_rate == GATE_C_BASELINE[
        "coverage_false_positive_rate"
    ]
    assert report.metrics.unsafe_finish_enabling_fp_rate == GATE_C_BASELINE[
        "unsafe_finish_enabling_fp_rate"
    ]
    assert report.f2["reproduced_under_baseline_bug"] is True


def test_product_hardened_gate_c_metrics() -> None:
    _, metrics, f2 = _run_product_gate_c_suite()
    assert metrics.precision == PRODUCT_HARDENED_EXPECTED["precision"]
    assert metrics.recall >= PRODUCT_HARDENED_EXPECTED["recall"]
    assert metrics.coverage_false_positive_rate == 0.0
    assert metrics.unsafe_finish_enabling_fp_rate == 0.0
    assert f2["f2_fixed"] is True
    assert f2["unsafe_finish_enabled"] is False


def test_f2_product_regression_blocks_unsafe_finish() -> None:
    facts = (
        FactGoal(id="X1", text=F2_FACT_X1, required=True, status=FactStatus.missing),
        FactGoal(id="X2", text=F2_FACT_X2, required=True, status=FactStatus.missing),
    )
    snippet = EvidenceSnippet(evidence_id="unrelated", text=F2_EVIDENCE)
    evidence = EvidenceState(facts=facts)
    match = _product_match(facts, (snippet,), only_uncovered=True)
    if match.ok:
        evidence, match = apply_and_score(evidence, match)
    assert not any("X1" in item.supports for item in match.items)
    assert not any("X2" in item.supports for item in match.items)
    statuses = {g.id: g.status for g in evidence.facts}
    assert statuses["X1"] in (FactStatus.missing, FactStatus.partial)
    assert statuses["X2"] in (FactStatus.missing, FactStatus.partial)
    assert statuses["X1"] != FactStatus.covered
    assert statuses["X2"] != FactStatus.covered
    signal = evaluate_stop(evidence, steps_used=2, max_steps=2)
    assert signal.kind != StopKind.finish or signal.reason_code != "facts_covered"


def test_product_chain_strong_support_allows_finish() -> None:
    fact = FactGoal(
        id="F1",
        text="找到 2028 住宿标准",
        required=True,
        status=FactStatus.missing,
    )
    snippet = EvidenceSnippet(
        evidence_id="strong",
        text="2028 年住宿标准为每人每天 500 元。",
    )
    evidence = EvidenceState(facts=(fact,))
    match = _product_match((fact,), (snippet,))
    assert match.ok is True
    evidence, match = apply_and_score(evidence, match)
    assert evidence.facts[0].status == FactStatus.covered
    signal = evaluate_stop(evidence, steps_used=2, max_steps=2)
    assert signal.kind == StopKind.finish
    assert signal.reason_code == "facts_covered"


def test_exact_support_still_covered() -> None:
    case = CASE_BY_ID["A1"]
    facts = (FactGoal(id="F1", text=case.fact_goal, status=FactStatus.missing),)
    snippets = (EvidenceSnippet(evidence_id="e0", text=case.evidence_texts[0]),)
    match = _product_match(facts, snippets)
    assert match.ok is True
    rel = _best_relation_for_fact(match.items, "F1")
    assert rel == EvidenceRelation.supports


def test_value_support_still_covered() -> None:
    case = CASE_BY_ID["A2"]
    facts = (FactGoal(id="F1", text=case.fact_goal, status=FactStatus.missing),)
    snippets = (EvidenceSnippet(evidence_id="e0", text=case.evidence_texts[0]),)
    match = _product_match(facts, snippets)
    assert match.ok is True
    rel = _best_relation_for_fact(match.items, "F1")
    assert rel == EvidenceRelation.supports


def test_keyword_overlap_downgraded() -> None:
    case = CASE_BY_ID["B1"]
    facts = (FactGoal(id="F1", text=case.fact_goal, status=FactStatus.missing),)
    snippets = (EvidenceSnippet(evidence_id="e0", text=case.evidence_texts[0]),)
    match = _product_match(facts, snippets)
    rel = _best_relation_for_fact(match.items, "F1") if match.ok else None
    assert rel != EvidenceRelation.supports


def test_wrong_value_contradicts() -> None:
    case = CASE_BY_ID["C1"]
    facts = (FactGoal(id="F1", text=case.fact_goal, status=FactStatus.missing),)
    snippets = (EvidenceSnippet(evidence_id="e0", text=case.evidence_texts[0]),)
    match = _product_match(facts, snippets)
    rel = _best_relation_for_fact(match.items, "F1")
    assert rel == EvidenceRelation.contradicts


def test_negation_contradicts() -> None:
    case = CASE_BY_ID["D1"]
    facts = (FactGoal(id="F1", text=case.fact_goal, status=FactStatus.missing),)
    snippets = (EvidenceSnippet(evidence_id="e0", text=case.evidence_texts[0]),)
    match = _product_match(facts, snippets)
    rel = _best_relation_for_fact(match.items, "F1")
    assert rel == EvidenceRelation.contradicts


def test_entity_mismatch_not_support() -> None:
    case = CASE_BY_ID["E1"]
    facts = (FactGoal(id="F1", text=case.fact_goal, status=FactStatus.missing),)
    snippets = (EvidenceSnippet(evidence_id="e0", text=case.evidence_texts[0]),)
    match = _product_match(facts, snippets)
    rel = _best_relation_for_fact(match.items, "F1") if match.ok else None
    assert rel != EvidenceRelation.supports


def test_temporal_mismatch_not_support() -> None:
    case = CASE_BY_ID["F_temp1"]
    facts = (FactGoal(id="F1", text=case.fact_goal, status=FactStatus.missing),)
    snippets = (EvidenceSnippet(evidence_id="e0", text=case.evidence_texts[0]),)
    match = _product_match(facts, snippets)
    rel = _best_relation_for_fact(match.items, "F1") if match.ok else None
    assert rel != EvidenceRelation.supports


def test_i1_paraphrase_known_fn_not_new_regression() -> None:
    case = CASE_BY_ID["I1"]
    facts = (FactGoal(id="F1", text=case.fact_goal, status=FactStatus.missing),)
    snippets = (EvidenceSnippet(evidence_id="e0", text=case.evidence_texts[0]),)
    match = _product_match(facts, snippets)
    rel = _best_relation_for_fact(match.items, "F1") if match.ok else None
    assert rel in (EvidenceRelation.partial, None)
    abc_spec = next(c for c in CANDIDATES if c.candidate_id == "A+B+C")
    abc_results, abc_report = run_candidate(abc_spec)
    product_results, product_metrics, _ = _run_product_gate_c_suite()
    abc_tp = {r.case_id for r in abc_results if r.true_positive}
    product_tp = {r.case_id for r in product_results if r.true_positive}
    new_fn = abc_tp - product_tp - {"I1"}
    assert len(new_fn) == 0, f"new false negatives: {new_fn}"


def test_fixture_path_unchanged() -> None:
    facts = (FactGoal(id="F1", text="任意 fact", status=FactStatus.missing),)
    match = match_from_fixture(
        facts,
        {"E1": {"supports": ["F1"], "text": "explicit fixture support"}},
    )
    assert match.ok is True
    assert match.source == "fixture"
    assert "F1" in match.items[0].supports


def test_no_new_fn_beyond_frozen_abc() -> None:
    abc_spec = next(c for c in CANDIDATES if c.candidate_id == "A+B+C")
    abc_results, _ = run_candidate(abc_spec)
    product_results, _, _ = _run_product_gate_c_suite()
    abc_tp = {r.case_id for r in abc_results if r.true_positive}
    product_tp = {r.case_id for r in product_results if r.true_positive}
    known_fn = {"I1"}
    new_fn = (abc_tp - product_tp) - known_fn
    assert len(new_fn) == 0, f"unexpected new FN: {new_fn}"
