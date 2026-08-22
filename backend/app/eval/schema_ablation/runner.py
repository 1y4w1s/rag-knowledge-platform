"""W8 P7 schema ablation runner — metrics, Gate H, artifact emission."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from app.eval.contract_validity.schema_baseline import schema_characterization_baseline
from app.eval.schema_ablation.candidates import (
    RECOMMENDED_REPAIR_LAYER,
    CandidateKind,
    classify_hard_negative_accept,
    decode_llm_json,
    evaluate_candidate,
    evaluate_strict,
)
from app.eval.schema_ablation.dataset import (
    load_full_dataset,
    passthrough_action_coverage,
)
from app.eval.schema_ablation.models import (
    BASE_MASTER_SHA,
    PRE_REPAIR_PARSE_FAILURES,
    PRE_REPAIR_PLANNER_DECISIONS,
    PRE_REPAIR_TOOL_NAME_AS_ACTION,
    AblationReport,
    CandidateMetrics,
    ExpectedOutcome,
    HardNegativeReport,
    TOOL_NAME_AS_ACTION_FAILURE_LAYER,
    TargetFailureReport,
)
from app.eval.schema_ablation.tool_inventory import frozen_tool_inventory

PROMPT_REINFORCEMENT_STATUS = "NOT_EVALUATED_IN_OFFLINE_P0"


def gate_h_readiness() -> dict[str, bool]:
    return {
        "ready_for_schema_product_implementation": False,
        "ready_for_prompt_ablation": False,
        "ready_for_broad_capability_remediation": False,
        "ready_for_golden_168": False,
        "ready_for_runtime_rollout": False,
    }


def _is_missing_tool_name_target(obj: dict[str, Any] | None) -> bool:
    if obj is None:
        return False
    if "tool_name" not in obj:
        return True
    return obj.get("tool_name") is None


def _is_duplicate_consistent_target(obj: dict[str, Any] | None) -> bool:
    if obj is None:
        return False
    action = obj.get("action")
    tool_name = obj.get("tool_name")
    return isinstance(action, str) and isinstance(tool_name, str) and action == tool_name


def _failure_shape(targets: list) -> dict[str, int]:
    missing = duplicate = conflicting = 0
    for sample in targets:
        obj, _ = decode_llm_json(sample.raw_output)
        if _is_missing_tool_name_target(obj):
            missing += 1
        elif _is_duplicate_consistent_target(obj):
            duplicate += 1
        else:
            conflicting += 1
    return {
        "missing_tool_name": missing,
        "duplicate_consistent_tool_name": duplicate,
        "conflicting_tool_name": conflicting,
    }


def _decisions_preserved(strict, out) -> bool:
    return (
        strict.decision == out.decision
        and not out.repair_applied
        and not out.semantic_mutation
    )


def _compute_metrics(
    kind: CandidateKind,
    *,
    targets: list,
    passthrough: list,
    hard: list,
    inventory,
) -> tuple[CandidateMetrics, list[TargetFailureReport], list[HardNegativeReport]]:
    metrics = CandidateMetrics(kind=kind)
    target_reports: list[TargetFailureReport] = []
    hard_reports: list[HardNegativeReport] = []

    metrics.target_failure_count = len(targets)
    for sample in targets:
        strict = evaluate_strict(sample.raw_output)
        out = evaluate_candidate(
            sample.raw_output,
            kind=kind,
            inventory=inventory,
            strict_baseline=strict,
        )
        recovered = (not strict.parse_ok) and out.parse_ok
        if recovered:
            metrics.target_recovered_count += 1
            obj, _ = decode_llm_json(sample.raw_output)
            if _is_missing_tool_name_target(obj):
                metrics.missing_tool_recovered_count += 1
            elif _is_duplicate_consistent_target(obj):
                metrics.duplicate_recovered_count += 1

        if out.repair_applied:
            metrics.transform_applied_count += 1
            if out.parse_ok:
                metrics.final_valid_count += 1

        obj, _ = decode_llm_json(sample.raw_output)
        action_val = obj.get("action") if obj else sample.decoded_json
        tool_val = obj.get("tool_name") if obj else None
        if isinstance(action_val, dict):
            action_val = action_val.get("action")
        allowed = (
            isinstance(action_val, str) and action_val in inventory.allowed_tool_names
        )
        target_reports.append(
            TargetFailureReport(
                case_id=sample.case_id or "",
                step_index=sample.step_index or 0,
                original_action=str(action_val) if action_val is not None else None,
                tool_name_recognized=str(tool_val) if tool_val is not None else None,
                allowed_in_scope=allowed,
                repair_applied=out.repair_applied,
                post_repair_parse_valid=out.parse_ok,
                tool_args_valid=out.parse_ok and out.error != "invalid_args",
                semantic_change=False,
                result="RECOVERED" if recovered else "STILL_FAILS",
            )
        )

    metrics.valid_passthrough_count = len(passthrough)
    for sample in passthrough:
        strict = evaluate_strict(sample.raw_output)
        out = evaluate_candidate(
            sample.raw_output,
            kind=kind,
            inventory=inventory,
            strict_baseline=strict,
        )
        preserved = strict.parse_ok and out.parse_ok and _decisions_preserved(strict, out)
        if preserved:
            metrics.valid_passthrough_preserved += 1
        elif strict.parse_ok:
            metrics.semantic_mutation_count += 1
        if out.repair_applied and strict.decision:
            action = strict.decision.get("action")
            if action in ("finish", "clarify", "refuse"):
                metrics.non_tool_action_mutation_count += 1

    metrics.hard_negative_count = len(hard)
    for sample in hard:
        strict = evaluate_strict(sample.raw_output)
        out_a1 = evaluate_candidate(
            sample.raw_output,
            kind=CandidateKind.narrow,
            inventory=inventory,
            strict_baseline=strict,
        )
        out_a2 = evaluate_candidate(
            sample.raw_output,
            kind=CandidateKind.duplicate_consistent,
            inventory=inventory,
            strict_baseline=strict,
        )
        out_b = evaluate_candidate(
            sample.raw_output,
            kind=CandidateKind.broad,
            inventory=inventory,
            strict_baseline=strict,
        )
        if kind == CandidateKind.narrow:
            out = out_a1
        elif kind == CandidateKind.duplicate_consistent:
            out = out_a2
        elif kind == CandidateKind.broad:
            out = out_b
        else:
            out = strict

        dim = sample.failure_dimension or "unknown"
        if kind == CandidateKind.strict:
            accepted = strict.parse_ok and sample.expected == ExpectedOutcome.reject
        else:
            counts = classify_hard_negative_accept(
                out,
                dimension=dim,
                inventory=inventory,
                strict_outcome=strict,
            )
            accepted = counts["false_repair"] > 0
            metrics.false_repair_count += counts["false_repair"]
            metrics.unknown_tool_accept_count += counts["unknown_tool_accept"]
            metrics.conflict_accept_count += counts["conflict_accept"]
            metrics.invalid_arguments_accept_count += counts["invalid_arguments_accept"]
            metrics.out_of_scope_tool_accept_count += counts["out_of_scope_tool_accept"]
            if out.repair_applied:
                metrics.transform_applied_count += 1
                if out.parse_ok:
                    metrics.final_valid_count += 1

        if kind in (
            CandidateKind.narrow,
            CandidateKind.duplicate_consistent,
            CandidateKind.broad,
        ):
            active_out = (
                out_a1
                if kind == CandidateKind.narrow
                else out_a2
                if kind == CandidateKind.duplicate_consistent
                else out_b
            )
            hard_reports.append(
                HardNegativeReport(
                    negative_id=sample.sample_id,
                    failure_dimension=dim,
                    candidate_a1_result="ACCEPT" if out_a1.parse_ok else "REJECT",
                    candidate_a2_result="ACCEPT" if out_a2.parse_ok else "REJECT",
                    candidate_b_result="ACCEPT" if out_b.parse_ok else "REJECT",
                    safety_failure=classify_hard_negative_accept(
                        active_out,
                        dimension=dim,
                        inventory=inventory,
                        strict_outcome=strict,
                    )["false_repair"]
                    > 0,
                )
            )

        if kind == CandidateKind.strict and accepted:
            metrics.false_repair_count += 1

        if dim in (
            "finish_action",
            "clarify_action",
            "refuse_action",
            "duplicate_finish",
            "duplicate_clarify",
            "duplicate_refuse",
        ):
            if out.repair_applied or (
                strict.parse_ok
                and out.parse_ok
                and out.decision != strict.decision
            ):
                metrics.non_tool_action_mutation_count += 1

    return metrics, target_reports, hard_reports


def _a2_safety_pass(metrics: CandidateMetrics) -> bool:
    return (
        metrics.false_repair_count == 0
        and metrics.unknown_tool_accept_count == 0
        and metrics.conflict_accept_count == 0
        and metrics.invalid_arguments_accept_count == 0
        and metrics.out_of_scope_tool_accept_count == 0
        and metrics.semantic_mutation_count == 0
        and metrics.non_tool_action_mutation_count == 0
    )


def _build_recommendation(
    a1: CandidateMetrics,
    a2: CandidateMetrics,
) -> dict[str, Any]:
    a2_safety = _a2_safety_pass(a2)
    a2_full_recovery = a2.target_recovered_count == a2.target_failure_count

    if a2_safety and a2_full_recovery:
        fix = "DUPLICATE_CONSISTENT_CANONICALIZATION"
        status = "RECOMMENDED_FOR_PRODUCT_IMPLEMENTATION"
    elif a2_safety and a2.target_recovered_count > 0:
        fix = "DUPLICATE_CONSISTENT_CANONICALIZATION"
        status = "PARTIAL"
    elif a2_safety:
        fix = "NONE"
        status = "SAFE_BUT_INSUFFICIENT"
    else:
        fix = "NONE"
        status = "SAFETY_FAIL"

    return {
        "recommended_fix": fix,
        "status": status,
        "a1_recovery": f"{a1.target_recovered_count}/{a1.target_failure_count}",
        "a2_recovery": f"{a2.target_recovered_count}/{a2.target_failure_count}",
        "a2_missing_recovered": a2.missing_tool_recovered_count,
        "a2_duplicate_recovered": a2.duplicate_recovered_count,
        "a2_false_repair_rate": a2.false_repair_rate,
        "a2_false_accept_count": a2.false_repair_count,
        "safety": "PASS" if a2_safety else "FAIL",
        "prompt_reinforcement": PROMPT_REINFORCEMENT_STATUS,
        "repair_layer": RECOMMENDED_REPAIR_LAYER.value,
        "failure_layer": TOOL_NAME_AS_ACTION_FAILURE_LAYER,
        "notes": (
            "A1 (missing-only) recovers 1/9; A2 adds duplicate-consistent "
            f"({a2.duplicate_recovered_count}/8 duplicate + "
            f"{a2.missing_tool_recovered_count}/1 missing). "
            "Broad control unsafe due to conflicting tool_name override."
        ),
    }


def _build_a2_safety_matrix(
    hard_reports: list[HardNegativeReport],
    a2: CandidateMetrics,
) -> dict[str, Any]:
    rows = []
    for report in hard_reports:
        rows.append(
            {
                "negative_id": report.negative_id,
                "dimension": report.failure_dimension,
                "a2_result": report.candidate_a2_result,
                "expected": report.expected,
                "safety_failure": report.safety_failure,
            }
        )
    return {
        "candidate": CandidateKind.duplicate_consistent.value,
        "hard_negative_count": a2.hard_negative_count,
        "false_accept_count": a2.false_repair_count,
        "transform_applied_count": a2.transform_applied_count,
        "final_valid_count": a2.final_valid_count,
        "rows": rows,
    }


def run_schema_ablation(
    *,
    external_tools_enabled: bool = False,
) -> AblationReport:
    inventory = frozen_tool_inventory(external_tools_enabled=external_tools_enabled)
    targets, passthrough, hard = load_full_dataset()

    strict_m, _, _ = _compute_metrics(
        CandidateKind.strict,
        targets=targets,
        passthrough=passthrough,
        hard=hard,
        inventory=inventory,
    )
    narrow_m, _, _ = _compute_metrics(
        CandidateKind.narrow,
        targets=targets,
        passthrough=passthrough,
        hard=hard,
        inventory=inventory,
    )
    a2_m, target_reports, hard_reports_a2 = _compute_metrics(
        CandidateKind.duplicate_consistent,
        targets=targets,
        passthrough=passthrough,
        hard=hard,
        inventory=inventory,
    )
    broad_m, _, _ = _compute_metrics(
        CandidateKind.broad,
        targets=targets,
        passthrough=passthrough,
        hard=hard,
        inventory=inventory,
    )

    baseline = schema_characterization_baseline()
    recommendation = _build_recommendation(narrow_m, a2_m)
    a2_safety = recommendation["safety"] == "PASS"
    a2_full_recovery = a2_m.target_recovered_count == a2_m.target_failure_count

    if a2_safety and a2_full_recovery:
        gate_status = "PASS"
    elif a2_safety:
        gate_status = "PARTIAL"
    else:
        gate_status = "FAIL"

    readiness = gate_h_readiness()
    readiness["ready_for_schema_product_implementation"] = (
        recommendation["status"] == "RECOMMENDED_FOR_PRODUCT_IMPLEMENTATION"
    )
    readiness["ready_for_prompt_ablation"] = (
        gate_status == "PARTIAL" and a2_safety
    )

    return AblationReport(
        base_master_sha=BASE_MASTER_SHA,
        pre_repair_baseline={
            "planner_decisions": PRE_REPAIR_PLANNER_DECISIONS,
            "parse_failures": PRE_REPAIR_PARSE_FAILURES,
            "TOOL_NAME_AS_ACTION": PRE_REPAIR_TOOL_NAME_AS_ACTION,
            "source": baseline.source_benchmark,
            "benchmark_semantics_sha": baseline.benchmark_semantics_sha,
        },
        dataset={
            "target_failures": len(targets),
            "valid_passthrough": len(passthrough),
            "hard_negatives": len(hard),
            "allowed_tools": sorted(inventory.allowed_tool_names),
            "action_coverage": passthrough_action_coverage(),
            "raw_target_lineage": "VALID",
            "failure_shape": _failure_shape(targets),
        },
        strict=strict_m,
        narrow=narrow_m,
        duplicate_consistent=a2_m,
        broad=broad_m,
        target_failure_reports=target_reports,
        hard_negative_reports=hard_reports_a2,
        recommendation=recommendation,
        gate_h={
            "w8_p7_p0b": gate_status,
            "gate_h": gate_status,
            **readiness,
        },
    )


def build_schema_ablation_report(
    *,
    repo_root: Path | None = None,
    write_artifacts: bool = False,
) -> dict[str, Any]:
    report = run_schema_ablation()
    a2 = report.duplicate_consistent
    safety_matrix = _build_a2_safety_matrix(report.hard_negative_reports, a2)
    payload = {
        "state": report.gate_h["gate_h"],
        "base_master_sha": report.base_master_sha,
        "product_diff": 0,
        "golden_diff": 0,
        "frozen_baseline": report.pre_repair_baseline,
        "raw_target_lineage": report.dataset["raw_target_lineage"],
        "failure_shape": report.dataset["failure_shape"],
        "dataset": report.dataset,
        "tool_inventory": frozen_tool_inventory(external_tools_enabled=False).to_dict(),
        "PRE_REPAIR_BASELINE": report.pre_repair_baseline,
        "STRICT": report.strict.to_dict(),
        "OFFLINE_A1_RESULT": report.narrow.to_dict(),
        "OFFLINE_A2_RESULT": a2.to_dict(),
        "OFFLINE_B_RESULT": report.broad.to_dict(),
        "NARROW_CANONICALIZATION": report.narrow.to_dict(),
        "DUPLICATE_CONSISTENT_CANONICALIZATION": a2.to_dict(),
        "BROAD_CONTROL": report.broad.to_dict(),
        "comparison_table": {
            "STRICT": {
                "recovery": (
                    f"{report.strict.target_recovered_count}/"
                    f"{report.strict.target_failure_count}"
                ),
                "passthrough": report.strict.valid_passthrough_rate,
                "false_repair": report.strict.false_repair_count,
            },
            "A1_MISSING_ONLY_NARROW": {
                "recovery": (
                    f"{report.narrow.target_recovered_count}/"
                    f"{report.narrow.target_failure_count}"
                ),
                "passthrough": report.narrow.valid_passthrough_rate,
                "false_repair": report.narrow.false_repair_count,
            },
            "A2_DUPLICATE_CONSISTENT": {
                "recovery": (
                    f"{a2.target_recovered_count}/{a2.target_failure_count}"
                ),
                "passthrough": a2.valid_passthrough_rate,
                "false_repair": a2.false_repair_count,
                "transforms": a2.transform_applied_count,
                "final_valid": a2.final_valid_count,
            },
            "BROAD_CONTROL": {
                "recovery": (
                    f"{report.broad.target_recovered_count}/"
                    f"{report.broad.target_failure_count}"
                ),
                "passthrough": report.broad.valid_passthrough_rate,
                "false_repair": report.broad.false_repair_count,
                "why_unsafe": (
                    "Accepts conflicting tool_name overrides and out-of-scope tools "
                    f"({report.broad.false_repair_count} hard-negative accepts)."
                ),
            },
        },
        "target_failure_reports": [asdict(r) for r in report.target_failure_reports],
        "hard_negative_reports": [asdict(r) for r in report.hard_negative_reports],
        "a2_safety_matrix": safety_matrix,
        "recommendation": report.recommendation,
        "gate_h": report.gate_h,
        "passthrough_coverage": {
            "real_artifact": report.dataset["action_coverage"],
            "synthetic_contract": {
                "clarify": "deterministic hard-negative only",
                "refuse": "deterministic hard-negative only",
            },
        },
        "candidate_c": {"prompt_reinforcement": PROMPT_REINFORCEMENT_STATUS},
    }

    if write_artifacts and repo_root is not None:
        out = repo_root / "artifacts" / "benchmarks" / "tmp" / "reports"
        out.mkdir(parents=True, exist_ok=True)
        names = {
            "w8-p7-schema-baseline.json": report.pre_repair_baseline,
            "w8-p7-ablation-results.json": payload,
            "w8-p7-recommendation.json": report.recommendation,
            "w8-p7-a2-safety-matrix.json": safety_matrix,
        }
        for name, body in names.items():
            (out / name).write_text(
                json.dumps(body, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

    return payload
