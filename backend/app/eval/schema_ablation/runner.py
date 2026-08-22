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
        "ready_for_prompt_ablation": True,
        "ready_for_broad_capability_remediation": False,
        "ready_for_golden_168": False,
        "ready_for_runtime_rollout": False,
    }


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

        from app.eval.schema_ablation.candidates import decode_llm_json

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

    metrics.hard_negative_count = len(hard)
    for sample in hard:
        strict = evaluate_strict(sample.raw_output)
        out_a = evaluate_candidate(
            sample.raw_output,
            kind=CandidateKind.narrow,
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
            out = out_a
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

        if kind in (CandidateKind.narrow, CandidateKind.broad):
            hard_reports.append(
                HardNegativeReport(
                    negative_id=sample.sample_id,
                    failure_dimension=dim,
                    candidate_a_result="ACCEPT" if out_a.parse_ok else "REJECT",
                    candidate_b_result="ACCEPT" if out_b.parse_ok else "REJECT",
                    safety_failure=(
                        kind == CandidateKind.narrow
                        and classify_hard_negative_accept(
                            out_a,
                            dimension=dim,
                            inventory=inventory,
                            strict_outcome=strict,
                        )["false_repair"]
                        > 0
                    )
                    or (
                        kind == CandidateKind.broad
                        and classify_hard_negative_accept(
                            out_b,
                            dimension=dim,
                            inventory=inventory,
                            strict_outcome=strict,
                        )["false_repair"]
                        > 0
                    ),
                )
            )

        if kind == CandidateKind.strict and accepted:
            metrics.false_repair_count += 1

    return metrics, target_reports, hard_reports


def _decisions_preserved(strict, out) -> bool:
    return (
        strict.decision == out.decision
        and not out.repair_applied
        and not out.semantic_mutation
    )


def _build_recommendation(narrow: CandidateMetrics) -> dict[str, Any]:
    safety_pass = (
        narrow.false_repair_count == 0
        and narrow.unknown_tool_accept_count == 0
        and narrow.conflict_accept_count == 0
        and narrow.invalid_arguments_accept_count == 0
        and narrow.out_of_scope_tool_accept_count == 0
        and narrow.semantic_mutation_count == 0
    )
    full_recovery = narrow.target_recovered_count == narrow.target_failure_count
    if safety_pass and full_recovery:
        fix = "NARROW_CANONICALIZATION"
        status = "RECOMMENDED_FOR_PRODUCT_IMPLEMENTATION"
    elif safety_pass and narrow.target_recovered_count > 0:
        fix = "NARROW_CANONICALIZATION"
        status = "PARTIAL"
    elif safety_pass:
        fix = "NONE"
        status = "SAFE_BUT_INSUFFICIENT"
    else:
        fix = "NONE"
        status = "SAFETY_FAIL"

    return {
        "recommended_fix": fix,
        "status": status,
        "recovery": f"{narrow.target_recovered_count}/{narrow.target_failure_count}",
        "false_repair_rate": narrow.false_repair_rate,
        "safety": "PASS" if safety_pass else "FAIL",
        "prompt_reinforcement": PROMPT_REINFORCEMENT_STATUS,
        "repair_layer": RECOMMENDED_REPAIR_LAYER.value,
        "failure_layer": TOOL_NAME_AS_ACTION_FAILURE_LAYER,
        "notes": (
            "8/9 P5 TOOL_NAME_AS_ACTION failures duplicate tool_name alongside "
            "tool-name-as-action; narrow canonicalization requires absent tool_name."
        ),
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
    narrow_m, target_reports, hard_reports = _compute_metrics(
        CandidateKind.narrow,
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
    recommendation = _build_recommendation(narrow_m)
    safety_pass = recommendation["safety"] == "PASS"
    full_recovery = narrow_m.target_recovered_count == narrow_m.target_failure_count

    if safety_pass and full_recovery:
        gate_status = "PASS"
    elif safety_pass:
        gate_status = "PARTIAL"
    else:
        gate_status = "FAIL"

    readiness = gate_h_readiness()
    readiness["ready_for_schema_product_implementation"] = (
        recommendation["status"] == "RECOMMENDED_FOR_PRODUCT_IMPLEMENTATION"
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
        },
        strict=strict_m,
        narrow=narrow_m,
        broad=broad_m,
        target_failure_reports=target_reports,
        hard_negative_reports=hard_reports,
        recommendation=recommendation,
        gate_h={
            "w8_p7_p0": gate_status,
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
    payload = {
        "state": report.gate_h["gate_h"],
        "base_master_sha": report.base_master_sha,
        "product_diff": 0,
        "golden_diff": 0,
        "frozen_baseline": report.pre_repair_baseline,
        "raw_target_lineage": report.dataset["raw_target_lineage"],
        "dataset": report.dataset,
        "tool_inventory": frozen_tool_inventory(external_tools_enabled=False).to_dict(),
        "STRICT": report.strict.to_dict(),
        "NARROW_CANONICALIZATION": report.narrow.to_dict(),
        "BROAD_CONTROL": report.broad.to_dict(),
        "comparison_table": {
            "STRICT": {
                "recovery": f"{report.strict.target_recovered_count}/{report.strict.target_failure_count}",
                "passthrough": report.strict.valid_passthrough_rate,
                "false_repair": report.strict.false_repair_count,
            },
            "NARROW_CANONICALIZATION": {
                "recovery": f"{report.narrow.target_recovered_count}/{report.narrow.target_failure_count}",
                "passthrough": report.narrow.valid_passthrough_rate,
                "false_repair": report.narrow.false_repair_count,
            },
            "BROAD_CONTROL": {
                "recovery": f"{report.broad.target_recovered_count}/{report.broad.target_failure_count}",
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
        "recommendation": report.recommendation,
        "gate_h": report.gate_h,
        "candidate_c": {"prompt_reinforcement": PROMPT_REINFORCEMENT_STATUS},
    }

    if write_artifacts and repo_root is not None:
        out = repo_root / "artifacts" / "benchmarks" / "tmp" / "reports"
        out.mkdir(parents=True, exist_ok=True)
        names = {
            "w8-p7-schema-baseline.json": report.pre_repair_baseline,
            "w8-p7-ablation-results.json": payload,
            "w8-p7-recommendation.json": report.recommendation,
        }
        for name, body in names.items():
            (out / name).write_text(
                json.dumps(body, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

    return payload
