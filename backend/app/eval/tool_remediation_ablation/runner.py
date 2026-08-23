"""Offline ablation matrix runner — Family S × Family T × hard negatives."""

from __future__ import annotations

from typing import Any

from app.eval.tool_remediation_ablation.audit_s import audit_family_s
from app.eval.tool_remediation_ablation.audit_t import audit_family_t
from app.eval.tool_remediation_ablation.corpus import assert_corpus_integrity, reconstruct_trials
from app.eval.tool_remediation_ablation.family_s import S_CANDIDATES, score_selection_candidate
from app.eval.tool_remediation_ablation.family_t import T_CANDIDATES, score_termination_candidate
from app.eval.tool_remediation_ablation.hard_negatives import (
    build_s_hard_negatives,
    build_s_targets,
    build_t_hard_negatives,
    build_t_targets,
)
from app.eval.tool_remediation_ablation.models import (
    P2_FREEZE_HEAD,
    P2_LINEAGE_SHA,
    STAGE,
    AblationReport,
    CandidateScore,
    Verdict,
)


def _to_score(row: dict[str, Any]) -> CandidateScore:
    return CandidateScore(
        candidate_id=row["candidate_id"],
        family=row["family"],
        target_count=row["target_count"],
        target_recovered=row["target_recovered"],
        hard_negative_count=row["hard_negative_count"],
        hard_negative_regressions=row["hard_negative_regressions"],
        new_false_behavior=row["new_false_behavior"],
        safety_risk=row["safety_risk"],
        scope_expansion=row["scope_expansion"],
        deterministic=row["deterministic"],
        complexity=row["complexity"],
        verdict=row["verdict"] if isinstance(row["verdict"], Verdict) else Verdict(row["verdict"]),
        rationale=row["rationale"],
        details=list(row.get("details") or []),
    )


def _pick_best(scores: list[CandidateScore]) -> str | None:
    accepted = [s for s in scores if s.verdict == Verdict.ACCEPT]
    if not accepted:
        return None
    # Prefer higher recovery, zero regressions, no scope expansion, lower complexity.
    complexity_rank = {"none": 0, "low": 1, "medium": 2, "high": 3}

    def key(s: CandidateScore) -> tuple:
        return (
            s.target_recovery_rate,
            -s.hard_negative_regression_rate,
            -int(s.scope_expansion),
            -complexity_rank.get(s.complexity, 2),
        )

    accepted.sort(key=key, reverse=True)
    return accepted[0].candidate_id


def _ready(score: CandidateScore | None) -> bool:
    if score is None:
        return False
    return (
        score.verdict == Verdict.ACCEPT
        and score.target_recovered > 0
        and score.hard_negative_regressions == 0
        and score.scope_expansion is False
    )


def run_ablation() -> AblationReport:
    trials = reconstruct_trials()
    assert_corpus_integrity(trials)
    s_audit = audit_family_s(trials)
    t_audit = audit_family_t(trials)

    s_targets = build_s_targets()
    s_hns = build_s_hard_negatives()
    t_targets = build_t_targets()
    t_hns = build_t_hard_negatives()

    s_scores = [
        _to_score(score_selection_candidate(cid, s_targets, s_hns))
        for cid in S_CANDIDATES
    ]
    t_scores = [
        _to_score(score_termination_candidate(cid, t_targets, t_hns))
        for cid in T_CANDIDATES
    ]

    best_s = _pick_best(s_scores)
    best_t = _pick_best(t_scores)
    best_s_score = next((s for s in s_scores if s.candidate_id == best_s), None)
    best_t_score = next((s for s in t_scores if s.candidate_id == best_t), None)

    ready_s = _ready(best_s_score)
    ready_t = _ready(best_t_score)

    experiments: list[str] = []
    if ready_s and best_s:
        experiments.append(
            f"Product prompt/description experiment for {best_s} only "
            "(no ToolResolver semantic change; measure GQ-131 first-action)."
        )
    else:
        experiments.append(
            "Continue Family S research: prefer description disambiguation + intent hint "
            "A/B offline before any product selection guard."
        )
    if ready_t and best_t:
        experiments.append(
            f"Product post-obs experiment for {best_t} only "
            "(obs-complete / repeat-success; no StopPolicy product patch yet)."
        )
    else:
        experiments.append(
            "Continue Family T research: separate termination-reasoning fix from "
            "evidence-gate; avoid StopPolicy coupling until hard negatives stay clean."
        )

    return AblationReport(
        stage=STAGE,
        corpus_trials=len(trials),
        family_s_root=s_audit["root_cause"],
        family_t_root=t_audit["root_cause"],
        family_t_subtypes=dict(t_audit["subtype_counts"]),
        s_scores=s_scores,
        t_scores=t_scores,
        best_s=best_s,
        best_t=best_t,
        ready_for_product_selection_fix=ready_s,
        ready_for_product_termination_fix=ready_t,
        recommended_next_product_experiments=experiments,
        product_diff=0,
    )


def build_ablation_manifest(report: AblationReport | None = None) -> dict[str, Any]:
    report = report or run_ablation()
    best_s = next((s for s in report.s_scores if s.candidate_id == report.best_s), None)
    best_t = next((s for s in report.t_scores if s.candidate_id == report.best_t), None)
    s0 = next((s for s in report.s_scores if s.candidate_id == "S0"), None)
    s2 = next((s for s in report.s_scores if s.candidate_id == "S2"), None)
    t0 = next((s for s in report.t_scores if s.candidate_id == "T0"), None)
    t2 = next((s for s in report.t_scores if s.candidate_id == "T2"), None)
    payload = report.to_dict()

    def _pair(score: CandidateScore | None) -> dict[str, Any]:
        if score is None:
            return {}
        return {
            "candidate_id": score.candidate_id,
            "target_recovery": f"{score.target_recovered}/{score.target_count}",
            "hard_negative_regressions": (
                f"{score.hard_negative_regressions}/{score.hard_negative_count}"
            ),
            "new_false_behavior": score.new_false_behavior,
            "verdict": score.verdict.value if hasattr(score.verdict, "value") else score.verdict,
        }

    s2_fp = int(s2.new_false_behavior) if s2 else 0
    t2_fp = int(t2.new_false_behavior) if t2 else 0
    ready = (
        report.ready_for_product_selection_fix
        and report.ready_for_product_termination_fix
        and report.product_diff == 0
        and s2_fp == 0
        and t2_fp == 0
    )
    freeze_status = (
        "READY_FOR_PRODUCT_EXPERIMENT" if ready else "PARTIAL"
    )
    payload.update(
        {
            "schema_version": "l4-tool-p3-offline-ablation-v1",
            "p2_lineage_sha": P2_LINEAGE_SHA,
            "p2_freeze_head": P2_FREEZE_HEAD,
            "p2_primary_score": "0/3",
            "p2_stability_score": "0/15",
            "measurement_validity": "TRUSTWORTHY",
            "product_remediation": False,
            "runtime_rollout": False,
            "lm_studio_rerun": False,
            "production_fix_proven": False,
            "freeze_status": freeze_status,
            "not_labels": ["NOT PRODUCTION_FIX_PROVEN", "NOT RUNTIME_ROLLOUT"],
            "families": {
                "S": {
                    "name": "TOOL_SELECTION_FAILURE",
                    "cases": ["GQ-131"],
                    "trials": 5,
                    "taxonomy": "PLANNER_WRONG_TOOL",
                    "best_candidate": report.best_s,
                    "baseline": _pair(s0),
                    "recommended": _pair(s2),
                    "target_recovery": (
                        f"{s2.target_recovered}/{s2.target_count}" if s2 else "0/0"
                    ),
                    "hard_negative_regression": (
                        f"{s2.hard_negative_regressions}/{s2.hard_negative_count}"
                        if s2
                        else "n/a"
                    ),
                    "false_positive_hint": s2_fp,
                    "freeze_semantics": {
                        "mode": "advisory_preferred_tool_hint",
                        "deterministic_override": False,
                        "ambiguous": "NO_HINT",
                    },
                    "status": (
                        "READY_FOR_PRODUCT_EXPERIMENT"
                        if report.ready_for_product_selection_fix and s2_fp == 0
                        else "PARTIAL"
                    ),
                },
                "T": {
                    "name": "POST_OBSERVATION_TERMINATION_FAILURE",
                    "cases": ["GQ-132", "GQ-149"],
                    "trials": 10,
                    "taxonomy": "BUDGET_EXHAUSTION",
                    "best_candidate": report.best_t,
                    "baseline": _pair(t0),
                    "recommended": _pair(t2),
                    "target_recovery": (
                        f"{t2.target_recovered}/{t2.target_count}" if t2 else "0/0"
                    ),
                    "hard_negative_regression": (
                        f"{t2.hard_negative_regressions}/{t2.hard_negative_count}"
                        if t2
                        else "n/a"
                    ),
                    "false_positive_hint": t2_fp,
                    "freeze_semantics": {
                        "mode": "advisory_task_contract_satisfied_hint",
                        "force_finish": False,
                        "requires": "tool_native_contract_predicate",
                    },
                    "status": (
                        "READY_FOR_PRODUCT_EXPERIMENT"
                        if report.ready_for_product_termination_fix and t2_fp == 0
                        else "PARTIAL"
                    ),
                },
            },
            "recommended_candidates": [report.best_s, report.best_t],
            "s_target_recovery": (
                f"{best_s.target_recovered}/{best_s.target_count}" if best_s else "0/0"
            ),
            "s_hard_negative_regression": (
                f"{best_s.hard_negative_regressions}/{best_s.hard_negative_count}"
                if best_s
                else "n/a"
            ),
            "t_target_recovery": (
                f"{best_t.target_recovered}/{best_t.target_count}" if best_t else "0/0"
            ),
            "t_hard_negative_regression": (
                f"{best_t.hard_negative_regressions}/{best_t.hard_negative_count}"
                if best_t
                else "n/a"
            ),
            "ready_for_product_ablation": ready,
            "state": "PASS" if ready else "PARTIAL",
        }
    )
    return payload
