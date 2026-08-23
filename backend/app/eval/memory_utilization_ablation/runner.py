"""Offline ablation matrix runner + primary/fallback selection."""

from __future__ import annotations

from typing import Any

from app.eval.memory_utilization_ablation.candidates import (
    has_instruction_conflict,
    render_candidate,
)
from app.eval.memory_utilization_ablation.corpus import (
    assert_corpus_integrity,
    reconstruct_trials,
)
from app.eval.memory_utilization_ablation.evaluator_audit import (
    audit_l4_semantics,
    build_hard_negatives,
    score_hard_negative,
)
from app.eval.memory_utilization_ablation.models import (
    STAGE,
    AblationReport,
    BlindSpot,
    CandidateId,
    CandidateScore,
    FrozenTrial,
    Verdict,
)
from app.eval.memory_utilization_ablation.proxy import proxy_matrix_row
from app.eval.memory_utilization_ablation.root_cause import (
    aggregate_root_causes,
    reconstruct_info_flow,
)


_META: dict[CandidateId, dict[str, Any]] = {
    CandidateId.C0_BASELINE: {
        "prompt_invasiveness": "none",
        "autonomy_impact": "none",
        "privacy_impact": "none",
        "implementation_complexity": "none",
        "removes_instruction_conflict": False,
        "improves_task_binding": False,
        "bypasses_planner_autonomy": False,
    },
    CandidateId.C1_CONTRASTIVE_LABEL: {
        "prompt_invasiveness": "low",
        "autonomy_impact": "low_advisory",
        "privacy_impact": "none_extra",
        "implementation_complexity": "low",
        "removes_instruction_conflict": True,
        "improves_task_binding": True,
        "bypasses_planner_autonomy": False,
    },
    CandidateId.C2_STRUCTURED_BLOCK: {
        "prompt_invasiveness": "low",
        "autonomy_impact": "low_advisory",
        "privacy_impact": "none_extra",
        "implementation_complexity": "low",
        "removes_instruction_conflict": True,
        "improves_task_binding": True,
        "bypasses_planner_autonomy": False,
    },
    CandidateId.C3_TASK_BINDING: {
        "prompt_invasiveness": "medium",
        "autonomy_impact": "medium_advisory_subgoal",
        "privacy_impact": "none_extra",
        "implementation_complexity": "medium",
        "removes_instruction_conflict": True,
        "improves_task_binding": True,
        "bypasses_planner_autonomy": False,
    },
    CandidateId.C4_PLACEMENT: {
        "prompt_invasiveness": "medium",
        "autonomy_impact": "none",
        "privacy_impact": "none_extra",
        "implementation_complexity": "medium",
        "removes_instruction_conflict": True,
        "improves_task_binding": False,
        "bypasses_planner_autonomy": False,
    },
    CandidateId.C5_DECISION_FIELD: {
        "prompt_invasiveness": "medium",
        "autonomy_impact": "medium_structured_decision",
        "privacy_impact": "none_extra",
        "implementation_complexity": "medium",
        "removes_instruction_conflict": True,
        "improves_task_binding": True,
        "bypasses_planner_autonomy": False,
    },
    CandidateId.C6_RELEVANCE_FILTER: {
        "prompt_invasiveness": "high_filter",
        "autonomy_impact": "high_prefilter",
        "privacy_impact": "filter_may_drop_props",
        "implementation_complexity": "medium",
        "removes_instruction_conflict": True,
        "improves_task_binding": True,
        "bypasses_planner_autonomy": True,
    },
}


def _hard_neg_false_rate() -> float:
    samples = build_hard_negatives()
    if not samples:
        return 0.0
    return sum(1 for s in samples if score_hard_negative(s)) / len(samples)


def _score_candidate(
    candidate_id: CandidateId, trials: tuple[FrozenTrial, ...]
) -> CandidateScore:
    row = proxy_matrix_row(candidate_id, trials)
    meta = _META[candidate_id]
    forces = bool(row["forces_answer"])
    hn_rate = _hard_neg_false_rate()
    apparent = float(row["apparent_rate"])
    eval_valid = float(row["evaluator_valid_rate"])

    ready = (
        apparent > 0
        and eval_valid == 1.0
        and hn_rate == 0.0
        and not forces
        and not meta["bypasses_planner_autonomy"]
        and meta["removes_instruction_conflict"]
        and candidate_id
        not in {
            CandidateId.C0_BASELINE,
            CandidateId.C4_PLACEMENT,
            CandidateId.C6_RELEVANCE_FILTER,
        }
    )

    if candidate_id == CandidateId.C0_BASELINE:
        verdict = Verdict.REJECT
        rationale = "Frozen baseline: double disclaimer conflict; L4 proxy readiness 0."
    elif candidate_id == CandidateId.C4_PLACEMENT:
        verdict = Verdict.DIAGNOSTIC_ONLY
        rationale = "Placement ablation only; does not fix task-binding alone."
    elif candidate_id == CandidateId.C6_RELEVANCE_FILTER:
        verdict = Verdict.DIAGNOSTIC_ONLY
        rationale = (
            "Deterministic relevance filter bypasses planner autonomy — diagnostic only."
        )
    elif ready:
        verdict = Verdict.READY_FOR_PRODUCT_EXPERIMENT
        rationale = (
            "Removes instruction conflict, adds task binding, keeps autonomy, "
            "hard-neg false util=0, does not force answer content."
        )
    elif apparent > 0 and not meta["bypasses_planner_autonomy"] and not forces:
        verdict = Verdict.DIAGNOSTIC_ONLY
        rationale = "Partial offline readiness; needs product A/B before claiming L4 lift."
    else:
        verdict = Verdict.REJECT
        rationale = "Fails offline gates (autonomy/force/conflict/hard-neg)."

    sample = next(t for t in trials if t.condition == "WITH_MEMORY" and t.seeds)
    rendered = render_candidate(candidate_id, sample.seeds, sample.query)
    details = [
        f"apparent_ready={row['apparent_ready']}/{row['n']}",
        f"evaluator_valid={row['evaluator_valid']}/{row['n']}",
        f"hard_neg_false_rate={hn_rate}",
        f"conflict_in_render={has_instruction_conflict(rendered)}",
    ]
    return CandidateScore(
        candidate_id=candidate_id.value,
        apparent_utilization_recovery=apparent,
        evaluator_valid_recovery=eval_valid,
        false_utilization_on_hard_negatives=hn_rate,
        prompt_invasiveness=str(meta["prompt_invasiveness"]),
        autonomy_impact=str(meta["autonomy_impact"]),
        privacy_impact=str(meta["privacy_impact"]),
        implementation_complexity=str(meta["implementation_complexity"]),
        removes_instruction_conflict=bool(meta["removes_instruction_conflict"]),
        improves_task_binding=bool(meta["improves_task_binding"]),
        forces_answer_content=forces,
        bypasses_planner_autonomy=bool(meta["bypasses_planner_autonomy"]),
        verdict=verdict,
        rationale=rationale,
        details=details,
    )


def _pick_primary_fallback(
    scores: list[CandidateScore],
) -> tuple[str | None, str | None, str]:
    ready = [s for s in scores if s.verdict == Verdict.READY_FOR_PRODUCT_EXPERIMENT]
    preference = [
        CandidateId.C1_CONTRASTIVE_LABEL.value,
        CandidateId.C2_STRUCTURED_BLOCK.value,
        CandidateId.C3_TASK_BINDING.value,
        CandidateId.C5_DECISION_FIELD.value,
    ]
    ready_sorted = sorted(
        ready,
        key=lambda s: (
            preference.index(s.candidate_id) if s.candidate_id in preference else 99,
            -s.apparent_utilization_recovery,
        ),
    )
    primary = ready_sorted[0].candidate_id if ready_sorted else None
    fallback = ready_sorted[1].candidate_id if len(ready_sorted) > 1 else None
    if primary is None:
        return (
            None,
            CandidateId.C2_STRUCTURED_BLOCK.value,
            "No candidate cleared READY_FOR_PRODUCT_EXPERIMENT; "
            "structured-block remains research fallback only.",
        )
    return (
        primary,
        fallback,
        f"Primary {primary}: conflict removed + binding + autonomy preserved + "
        f"hard-neg regression 0. Fallback {fallback}.",
    )


def run_ablation() -> AblationReport:
    trials = reconstruct_trials()
    assert_corpus_integrity(trials)
    flows = [
        reconstruct_info_flow(t) for t in trials if t.condition == "WITH_MEMORY"
    ]
    dominant, supporting = aggregate_root_causes(flows)
    audit = audit_l4_semantics()
    scores = [_score_candidate(cid, trials) for cid in CandidateId]
    primary, fallback, why = _pick_primary_fallback(scores)
    return AblationReport(
        stage=STAGE,
        corpus_trials=len(trials),
        dominant_root_cause=dominant,
        supporting_root_causes=supporting,
        evaluator_blind_spot=BlindSpot(str(audit["blind_spot"])),
        evaluator_audit_notes=list(audit["notes"]),  # type: ignore[arg-type]
        info_flows=flows,
        scores=scores,
        primary=primary,
        fallback=fallback,
        ready_for_product_experiment=primary is not None,
        l5_fixed=False,
        product_diff=0,
        selection_rationale=why,
    )


def build_ablation_manifest(report: AblationReport | None = None) -> dict[str, Any]:
    report = report or run_ablation()
    return {
        "schema_version": "l4-memory-p4-ablation-manifest-v1",
        "stage": report.stage,
        "corpus_trials": report.corpus_trials,
        "dominant_root_cause": report.dominant_root_cause.value,
        "supporting_root_causes": [x.value for x in report.supporting_root_causes],
        "evaluator_blind_spot": report.evaluator_blind_spot.value,
        "evaluator_audit_notes": report.evaluator_audit_notes,
        "matrix": [
            {
                "candidate_id": s.candidate_id,
                "apparent_utilization_recovery": s.apparent_utilization_recovery,
                "evaluator_valid_recovery": s.evaluator_valid_recovery,
                "false_utilization_on_hard_negatives": (
                    s.false_utilization_on_hard_negatives
                ),
                "prompt_invasiveness": s.prompt_invasiveness,
                "autonomy_impact": s.autonomy_impact,
                "privacy_impact": s.privacy_impact,
                "implementation_complexity": s.implementation_complexity,
                "removes_instruction_conflict": s.removes_instruction_conflict,
                "improves_task_binding": s.improves_task_binding,
                "forces_answer_content": s.forces_answer_content,
                "bypasses_planner_autonomy": s.bypasses_planner_autonomy,
                "verdict": s.verdict.value,
                "rationale": s.rationale,
                "details": s.details,
            }
            for s in report.scores
        ],
        "primary": report.primary,
        "fallback": report.fallback,
        "ready_for_product_experiment": report.ready_for_product_experiment,
        "l5_fixed": False,
        "product_diff": 0,
        "selection_rationale": report.selection_rationale,
        "info_flow_sample": [
            {
                "case_id": f.case_id,
                "trial_index": f.trial_index,
                "seeded_proposition": f.seeded_proposition,
                "prompt_placement": f.prompt_placement,
                "planner_instruction_conflict": f.planner_instruction_conflict,
                "final_behavior": f.final_behavior,
                "utilization_verdict": f.utilization_verdict,
                "dominant_taxonomy": f.dominant_taxonomy.value,
                "supporting_taxonomy": [x.value for x in f.supporting_taxonomy],
            }
            for f in report.info_flows[:4]
        ],
    }
