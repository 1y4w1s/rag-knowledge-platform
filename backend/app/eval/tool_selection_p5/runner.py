"""P5 offline characterization runner — eval-only, product diff 0."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from app.eval.tool_selection_p5.candidates import META, score_all
from app.eval.tool_selection_p5.characterize import characterize_s2_failure
from app.eval.tool_selection_p5.corpus import (
    assert_corpus_integrity,
    build_target_samples,
    reconstruct_trials,
)
from app.eval.tool_selection_p5.hard_negatives import build_hard_negatives
from app.eval.tool_selection_p5.models import (
    CANDIDATE_STATUS,
    FORBIDDEN_CANDIDATE_STATUSES,
    MANIFEST_SCHEMA,
    ORIGIN_MASTER_SHA,
    P4_BRANCH,
    P4_TIP_SHA,
    STAGE,
    Verdict,
)


def run_characterization() -> Dict[str, Any]:
    trials = reconstruct_trials()
    assert_corpus_integrity(trials)
    characterization = characterize_s2_failure(trials)
    targets = build_target_samples(trials)
    hard_negatives = build_hard_negatives()
    scores = score_all(targets, hard_negatives)

    primary = next((s for s in scores if s.verdict == Verdict.PRIMARY), None)
    fallback = next((s for s in scores if s.verdict == Verdict.FALLBACK), None)
    rejected = [s.candidate_id for s in scores if s.verdict == Verdict.REJECT]
    diagnostic = [s.candidate_id for s in scores if s.verdict == Verdict.DIAGNOSTIC_ONLY]

    ready = bool(
        primary is not None
        and primary.target_recovered > 0
        and primary.hard_negative_regressions == 0
        and primary.autonomy_impact in {"none", "low"}
        and primary.status == CANDIDATE_STATUS
    )
    if fallback is not None and fallback.status != CANDIDATE_STATUS:
        ready = False

    s3a_freeze = META.get("S3A", {})
    s3b_freeze = META.get("S3B", {})

    return {
        "schema_version": MANIFEST_SCHEMA,
        "stage": STAGE,
        "origin_master_sha": ORIGIN_MASTER_SHA,
        "convergence_round_start_master_sha": ORIGIN_MASTER_SHA,
        "p4_branch": P4_BRANCH,
        "p4_tip_sha": P4_TIP_SHA,
        "product_diff": 0,
        "golden_diff": 0,
        "workflow_diff": 0,
        "lm_studio_used": False,
        "gpu_used": False,
        "characterization": characterization,
        "targets_n": len(targets),
        "hard_negatives_n": len(hard_negatives),
        "hard_negative_classes": sorted({s.intent_class for s in hard_negatives}),
        "candidates": [s.to_dict() for s in scores],
        "s3a_freeze": {
            "candidate": "S3A",
            "status": CANDIDATE_STATUS,
            "forbidden_statuses": list(FORBIDDEN_CANDIDATE_STATUSES),
            "exact_semantics": s3a_freeze.get("exact_semantics"),
            "target_mechanism": s3a_freeze.get("target_mechanism"),
            "why_differs_from_s2": s3a_freeze.get("why_differs_from_s2"),
            "autonomy_impact": s3a_freeze.get("autonomy_impact"),
            "hard_negatives": s3a_freeze.get("hard_negatives"),
            "target_recovery": (
                "%s/%s" % (primary.target_recovered, primary.target_count)
                if primary is not None
                else "0/0"
            ),
            "regressions": (
                "%s/%s" % (primary.hard_negative_regressions, primary.hard_negative_count)
                if primary is not None
                else "n/a"
            ),
        },
        "s3b_freeze": {
            "candidate": "S3B",
            "status": CANDIDATE_STATUS,
            "role": "FALLBACK",
            "forbidden_statuses": list(FORBIDDEN_CANDIDATE_STATUSES),
            "mechanism": s3b_freeze.get("mechanism"),
            "safety_tradeoff": s3b_freeze.get("safety_tradeoff"),
            "autonomy_impact": s3b_freeze.get("autonomy_impact"),
            "why_fallback_only": s3b_freeze.get("why_fallback_only"),
        },
        "recommendation": {
            "primary": None if primary is None else primary.candidate_id,
            "fallback": None if fallback is None else fallback.candidate_id,
            "rejected": rejected,
            "diagnostic_only": diagnostic,
            "ready_for_product_experiment": ready,
            "candidate_status": CANDIDATE_STATUS,
            "never_claim": list(FORBIDDEN_CANDIDATE_STATUSES),
            "note": (
                "At most one primary + one fallback. S3A/S3B are "
                "READY_FOR_PRODUCT_EXPERIMENT only — never FIXED / REAL_VALIDATED / "
                "PRODUCTION_READY. S3E never product-implement in P5. "
                "S3F diagnostic bias control only."
            ),
        },
        "d11": {
            "tool_selection_p5_state": "PASS" if ready else "PARTIAL",
            "root_cause": characterization["root_cause"],
            "frozen_roots": characterization.get("frozen_roots"),
            "s2_failure_explanation": characterization["s2_failure_explanation"],
            "hint_delivery_ne_tool_selection": characterization.get("s2_failure", {}).get(
                "inequality_holds"
            ),
            "best_candidate": None if primary is None else primary.candidate_id,
            "target_recovery": (
                "%s/%s" % (primary.target_recovered, primary.target_count)
                if primary is not None
                else "0/0"
            ),
            "hard_negative_regression": (
                "%s/%s" % (primary.hard_negative_regressions, primary.hard_negative_count)
                if primary is not None
                else "n/a"
            ),
            "autonomy_impact": primary.autonomy_impact if primary is not None else "n/a",
            "fallback": None if fallback is None else fallback.candidate_id,
            "ready_for_product_experiment": "YES" if ready else "NO",
            "runtime_rollout": "NO",
            "product_diff": 0,
            "golden_diff": 0,
            "workflow_diff": 0,
        },
    }


def write_manifest(path: Optional[Path] = None) -> Path:
    report = run_characterization()
    out = path or (
        Path(__file__).resolve().parents[3]
        / "artifacts"
        / "benchmarks"
        / "tmp"
        / "reports"
        / "w8-tool-p5-s2-failure-characterization.json"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    fixture = (
        Path(__file__).resolve().parents[3]
        / "tests"
        / "fixtures"
        / "l4_tool_capability"
        / "l4-tool-p5-offline-characterization.manifest.json"
    )
    compact = {
        "schema_version": report["schema_version"],
        "stage": report["stage"],
        "origin_master_sha": report["origin_master_sha"],
        "convergence_round_start_master_sha": report["convergence_round_start_master_sha"],
        "product_diff": 0,
        "golden_diff": 0,
        "workflow_diff": 0,
        "recommendation": report["recommendation"],
        "d11": report["d11"],
        "s3a_freeze": {
            "status": report["s3a_freeze"]["status"],
            "target_recovery": report["s3a_freeze"]["target_recovery"],
            "regressions": report["s3a_freeze"]["regressions"],
        },
        "s3b_freeze": {
            "status": report["s3b_freeze"]["status"],
            "role": report["s3b_freeze"]["role"],
        },
        "candidate_verdicts": {c["candidate_id"]: c["verdict"] for c in report["candidates"]},
    }
    fixture.write_text(json.dumps(compact, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return out
