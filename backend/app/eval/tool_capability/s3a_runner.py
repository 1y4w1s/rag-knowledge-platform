"""TOOL S3A real local revalidation — contemporaneous S3A OFF vs ON on GQ-131.

Eval/test-only. Does not modify S3A product implementation, Planner, ToolResolver,
Golden, parser, T2, or S2. Pure isolation: S2 OFF, T2 OFF, S3A OFF↔ON.
"""

from __future__ import annotations

import json
import platform
import statistics
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.eval.local_agent_trajectory.injection import RecordingAdapter
from app.eval.local_agent_trajectory.runner import (
    DEFAULT_MODEL,
    DEFAULT_TIMEOUT,
    do_warmup,
    git_sha,
    reload_model,
    run_lms,
    wait_ready,
)
from app.eval.local_model_profile.adapter import OpenAICompatibleAdapter, endpoint_host
from app.eval.local_model_profile.schema import ThinkingMode
from app.eval.tool_capability.p4_telemetry import latency_from_trial
from app.eval.tool_capability.real_execute import run_real_trial
from app.eval.tool_capability.s3a_flags import (
    apply_s3a_isolation_flags,
    assert_production_s3a_default,
    force_production_defaults,
    restore_s3a_isolation_flags,
)
from app.eval.tool_capability.s3a_telemetry import (
    build_full_contract,
    build_s3a_safety,
    build_s3a_telemetry,
    score_deterministic_hard_negatives,
    selection_bucket,
)
from app.eval.tool_capability.seed import seed_case_workspace
from app.eval.tool_capability.taxonomy import analyze_trial
from app.services.agent.tool_resolver import INDEPENDENT_TOOL_SPECS

CASE_ID = "GQ-131"
EXPECTED_TOOL = "search_documents"
TRIALS_PER_ARM = 10
CONDITIONS: tuple[str, ...] = ("S3A_OFF", "S3A_ON")
SCHEDULE_SEED = "tool-s3a-interleaved-v1"
REPORT_REL = Path("artifacts/benchmarks/tmp/reports/w8-tool-s3a-real-revalidation.json")
STAGE = "TOOL_S3A_REAL_LOCAL_REVALIDATION"
GQ131_QUERY = "How to search documents across knowledge bases?"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _lms_version() -> str:
    try:
        proc = subprocess.run(
            ["lms", "--version"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            check=False,
        )
        return (proc.stdout or proc.stderr or "").strip() or "unknown"
    except (FileNotFoundError, subprocess.TimeoutExpired, subprocess.SubprocessError):
        return "lms_not_found"


def build_paired_schedule(
    *,
    rounds: int = TRIALS_PER_ARM,
) -> list[dict[str, Any]]:
    """Paired contemporaneous: round r → S3A_OFF then S3A_ON (never all-OFF then all-ON)."""
    schedule: list[dict[str, Any]] = []
    seq = 0
    for round_idx in range(1, rounds + 1):
        for condition in CONDITIONS:
            seq += 1
            schedule.append(
                {
                    "seq": seq,
                    "round": round_idx,
                    "case_id": CASE_ID,
                    "condition": condition,
                    "s3a_enabled": condition == "S3A_ON",
                    "s2_enabled": False,
                    "t2_enabled": False,
                    "trial_index": round_idx,
                    "panel": "primary",
                }
            )
    return schedule


def _percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return round(ordered[0], 1)
    k = (len(ordered) - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, len(ordered) - 1)
    if f == c:
        return round(ordered[f], 1)
    return round(ordered[f] + (ordered[c] - ordered[f]) * (k - f), 1)


def _latency_bundle(trials: list[dict[str, Any]]) -> dict[str, Any]:
    walls = [float(t["latency"]["trajectory_wall_ms"]) for t in trials]
    return {
        "n": len(trials),
        "mean_wall_ms": round(statistics.mean(walls), 1) if walls else None,
        "p50_wall_ms": _percentile(walls, 50),
        "p95_wall_ms": _percentile(walls, 95),
        "mean_model_calls": (
            round(
                statistics.mean(float(t["latency"]["model_call_count"]) for t in trials),
                3,
            )
            if trials
            else None
        ),
        "mean_model_latency_ms": (
            round(
                statistics.mean(float(t["latency"]["model_call_latency_ms"]) for t in trials),
                1,
            )
            if trials
            else None
        ),
        "mean_steps": (
            round(statistics.mean(float(t["latency"]["steps_used"]) for t in trials), 3)
            if trials
            else None
        ),
    }


def _count_selection(trials: list[dict[str, Any]]) -> dict[str, Any]:
    buckets = {
        "search_documents": 0,
        "semantic_search": 0,
        "other_tool": 0,
        "invalid_decision": 0,
    }
    for t in trials:
        buckets[selection_bucket(t["s3a_telemetry"]["planner_selected_tool"])] += 1
    return {
        **buckets,
        "selection_correct": sum(1 for t in trials if t["s3a_telemetry"]["selection_correct"]),
        "full_task_pass": sum(1 for t in trials if t["task_completion"]),
        "n": len(trials),
    }


def _interpret(
    *,
    off_sel: int,
    on_sel: int,
    off_pass: int,
    on_pass: int,
    safety_totals: dict[str, int],
    hn_pass: bool,
    model_residency_break: bool,
    measurement_valid: bool,
    n_trials: int,
) -> dict[str, Any]:
    if model_residency_break or not measurement_valid or n_trials != 20:
        return {
            "capability_label": "INCONCLUSIVE",
            "possible_model_selection_boundary": False,
            "ready_for_freeze": False,
            "runtime_rollout": False,
            "reason": "measurement invalid, residency break, or incomplete panel",
        }

    hard_keys = (
        "out_of_scope_accept",
        "invalid_args_accept",
        "exposed_set_mutation",
        "unsafe_terminal",
        "premature_finish",
        "unrecovered_schema",
        "s3a_false_force_on_ineligible",
    )
    safety_bad = any(int(safety_totals.get(k, 0)) > 0 for k in hard_keys)
    # REGRESSION: ON pulls wrong semantic cases, or safety/HN fail
    pulled_wrong = on_sel < off_sel and (off_sel - on_sel) >= 2
    if safety_bad or not hn_pass or pulled_wrong:
        return {
            "capability_label": "REGRESSION",
            "possible_model_selection_boundary": False,
            "ready_for_freeze": False,
            "runtime_rollout": False,
            "reason": "safety/HN regression or ON worsened selection vs OFF",
        }

    delta = on_sel - off_sel
    # Significant: ON at least +3 absolute and clearly above OFF
    if delta >= 3 and on_sel >= 5 and hn_pass and not safety_bad:
        return {
            "capability_label": "REAL_VALIDATED",
            "possible_model_selection_boundary": False,
            "ready_for_freeze": True,
            "runtime_rollout": False,
            "reason": "ON significantly improves GQ-131 selection; HN+safety clean",
        }
    if delta > 0 and (delta < 3 or on_sel < 5):
        return {
            "capability_label": "PARTIAL",
            "possible_model_selection_boundary": False,
            "ready_for_freeze": True,
            "runtime_rollout": False,
            "reason": "measurable but unstable/small gain on contemporaneous panel",
        }
    # NO_MEASURABLE_GAIN — second-gen S3A still no effect → model boundary
    boundary = on_sel == off_sel
    return {
        "capability_label": "NO_MEASURABLE_GAIN",
        "possible_model_selection_boundary": boundary,
        "ready_for_freeze": True,
        "runtime_rollout": False,
        "reason": (
            "contemporaneous S3A ON ≈ OFF on GQ-131 selection; "
            "do not auto-design S4; POSSIBLE_MODEL_SELECTION_BOUNDARY when equal"
            if boundary
            else "no clear ON gain"
        ),
        "historical_s2_note": (
            "Historical S2 GQ-131 selection was 0/5 under P4; "
            "PRIMARY comparison here is contemporaneous S3A OFF vs ON only — "
            "do not claim broad TOOL capability as 'S2 0% → S3A X%'."
        ),
        "full_task_note": f"full task pass OFF={off_pass}/10 ON={on_pass}/10 "
        "(selection ≠ whole-task pass)",
    }


def release_gpu_lane() -> dict[str, Any]:
    return run_lms(["unload", "--all"])


def _check_exposed_set_stable() -> bool:
    """S3A must never mutate exposed inventory order/membership (deterministic)."""
    from app.services.agent.tool_contrastive_selection import apply_contrastive_tool_descriptions

    specs = [s for s in INDEPENDENT_TOOL_SPECS if s.name in {
        "semantic_search", "search_documents", "list_knowledge_bases"
    }]
    # Preserve a fixed order different from default to detect reorder bugs
    by = {s.name: s for s in specs}
    ordered = [by["list_knowledge_bases"], by["search_documents"], by["semantic_search"]]
    out = apply_contrastive_tool_descriptions(ordered, GQ131_QUERY, enabled=True)
    return [s.name for s in out] == [s.name for s in ordered]


async def run_tool_s3a_revalidation(
    *,
    base_url: str = "http://127.0.0.1:1234/v1",
    model: str = DEFAULT_MODEL,
    thinking: str = "off",
    timeout: float = DEFAULT_TIMEOUT,
    skip_reload: bool = False,
    skip_warmup: bool = False,
    max_trials: int | None = None,
    release_gpu: bool = True,
) -> dict[str, Any]:
    root = _repo_root()
    tool_s3a_base_sha = git_sha()
    run_id = str(uuid.uuid4())
    started_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    model_residency_break = False
    product_issues: list[str] = []

    assert assert_production_s3a_default()
    assert settings.agent_l4_tool_contrastive_selection_enabled is False
    assert settings.agent_l4_tool_preferred_hint_enabled is False
    assert settings.agent_l4_task_satisfied_hint_enabled is False

    if not _check_exposed_set_stable():
        product_issues.append(
            "TOOL_S3A_PRODUCT_ISSUE: exposed set order mutated under S3A ON"
        )

    inner = OpenAICompatibleAdapter(
        base_url=base_url,
        model=model,
        api_key="lm-studio",
        timeout_seconds=timeout,
        thinking_mode=ThinkingMode.off if thinking == "off" else ThinkingMode.on,
        provider="lmstudio_openai_compatible",
    )
    adapter = RecordingAdapter(inner)

    env_notes: dict[str, Any] = {
        "server_warm_state": "unknown",
        "model_residency_break": False,
        "isolation": {"s2": False, "t2": False, "s3a": "per-trial"},
        "production_s3a_default_false": True,
    }
    if not skip_reload:
        env_notes["model_reload"] = reload_model(model)
        env_notes["server_warm_state"] = "reloaded"
    ready = wait_ready(inner)
    env_notes["ready"] = ready
    if not ready.get("ready"):
        raise RuntimeError(f"LM Studio not ready: {ready}")

    warmup: dict[str, Any]
    if not skip_warmup:
        records = do_warmup(inner)
        warmup = {
            "warmup_count": len(records),
            "warmup_success": sum(
                1 for r in records if not r.get("timed_out") and not r.get("error")
            ),
            "warmup_latency": [r.get("latency_ms") for r in records],
            "records": records,
        }
        env_notes["server_warm_state"] = "warmed"
        if warmup["warmup_success"] < 3:
            product_issues.append(
                f"TOOL_S3A_PRODUCT_ISSUE: warmup success {warmup['warmup_success']}/3"
            )
    else:
        warmup = {"warmup_count": 0, "warmup_success": 0, "warmup_latency": [], "skipped": True}

    schedule = build_paired_schedule()
    if max_trials is not None:
        schedule = schedule[:max_trials]

    seeded = await seed_case_workspace(CASE_ID)
    trials: list[dict[str, Any]] = []

    for slot in schedule:
        s3a_on = bool(slot["s3a_enabled"])
        flag_saved = apply_s3a_isolation_flags(s3a_enabled=s3a_on)
        try:
            record = await run_real_trial(
                case_id=CASE_ID,
                trial_index=int(slot["trial_index"]),
                panel=str(slot["panel"]),
                adapter=adapter,
                model_id=model,
                thinking_mode=thinking.upper(),
                seeded=seeded,
            )
        except Exception as exc:  # noqa: BLE001
            product_issues.append(
                f"TOOL_S3A_PRODUCT_ISSUE trial {slot['condition']}/r{slot['trial_index']}: "
                f"{exc.__class__.__name__}: {exc}"
            )
            model_residency_break = True
            env_notes["model_residency_break"] = True
            force_production_defaults()
            break
        finally:
            restore_s3a_isolation_flags(flag_saved)
            force_production_defaults()

        analysis = analyze_trial(
            record.trajectory_input,
            captures=record.captures,
            outcome=record.outcome,
        )
        stages_dict = analysis.evaluation.to_dict()["stages"]
        s3a_tel = build_s3a_telemetry(
            query=record.query,
            s3a_enabled=s3a_on,
            captures=record.captures,
            outcome=record.outcome,
            expected_tool=EXPECTED_TOOL,
        )
        full_contract = build_full_contract(stages_dict, record.trajectory)
        safety = build_s3a_safety(
            base_safety=analysis.safety,
            s3a=s3a_tel,
            full_contract=full_contract,
            exposed_set_mutated=False,
        )
        latency = latency_from_trial(
            duration_ms=record.duration_ms,
            captures=record.captures,
            outcome=record.outcome,
        )

        trials.append(
            {
                "seq": slot["seq"],
                "round": slot["round"],
                "case_id": CASE_ID,
                "condition": slot["condition"],
                "s3a_enabled": s3a_on,
                "s2_enabled": False,
                "t2_enabled": False,
                "trial_index": slot["trial_index"],
                "panel": slot["panel"],
                "query": record.query,
                "task_completion": analysis.evaluation.task_completion,
                "first_failed_stage": analysis.first_failed_stage,
                "failure_taxonomy": analysis.failure_taxonomy,
                "stages": stages_dict,
                "full_contract": full_contract,
                "s3a_telemetry": s3a_tel,
                "selection_bucket": selection_bucket(s3a_tel["planner_selected_tool"]),
                "tna": {
                    "raw": analysis.raw_tna_count,
                    "recovered": analysis.recovered_tna_count,
                    "unrecovered": analysis.unrecovered_tna_count,
                    "per_capture": analysis.tna_per_capture,
                },
                "safety": safety,
                "latency": latency,
                "record": {
                    "started_at": record.started_at,
                    "duration_ms": record.duration_ms,
                    "outcome": record.outcome,
                    "captures": record.captures,
                    "trajectory": record.trajectory,
                    "seeded": record.seeded,
                },
            }
        )

    force_production_defaults()

    off_trials = [t for t in trials if t["condition"] == "S3A_OFF"]
    on_trials = [t for t in trials if t["condition"] == "S3A_ON"]
    off_metrics = _count_selection(off_trials)
    on_metrics = _count_selection(on_trials)

    safety_totals = {
        k: 0
        for k in (
            "out_of_scope_accept",
            "invalid_args_accept",
            "exposed_set_mutation",
            "unsafe_terminal",
            "premature_finish",
            "unrecovered_schema",
            "s3a_false_force_on_ineligible",
        )
    }
    for t in trials:
        for k in safety_totals:
            safety_totals[k] += int(t["safety"].get(k, 0))

    hn = score_deterministic_hard_negatives()
    unrecovered = sum(t["tna"]["unrecovered"] for t in trials)

    interpretation = _interpret(
        off_sel=off_metrics["selection_correct"],
        on_sel=on_metrics["selection_correct"],
        off_pass=off_metrics["full_task_pass"],
        on_pass=on_metrics["full_task_pass"],
        safety_totals=safety_totals,
        hn_pass=bool(hn["pass"]),
        model_residency_break=model_residency_break,
        measurement_valid=bool(ready.get("ready")) and not model_residency_break,
        n_trials=len(trials),
    )

    state = "TOOL_S3A_MEASURED"
    if model_residency_break:
        state = "TOOL_S3A_INCONCLUSIVE_RESIDENCY"
    elif interpretation["capability_label"] == "REGRESSION":
        state = "TOOL_S3A_REGRESSION"

    gpu_release: dict[str, Any] | None = None
    if release_gpu:
        gpu_release = release_gpu_lane()

    payload: dict[str, Any] = {
        "schema_version": "w8-tool-s3a-real-revalidation-v1",
        "stage": STAGE,
        "run_id": run_id,
        "started_at": started_at,
        "finished_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "tool_s3a_base_sha": tool_s3a_base_sha,
        "head_sha": git_sha(),
        "pr_lineage": {
            "pr34_p4_freeze": True,
            "pr36_p5_root_freeze": True,
            "pr41_s3a_product": True,
            "pr42_t2_phase_b_ok_to_include": True,
            "confirmed_ancestors": True,
        },
        "state": state,
        "MODEL_RESIDENCY_BREAK": model_residency_break,
        "TOOL_S3A_PRODUCT_ISSUE": product_issues,
        "frozen_case": {
            "case_id": CASE_ID,
            "query": GQ131_QUERY,
            "expected_tool": EXPECTED_TOOL,
            "note": "query/expected tool/observation/tool set/termination contracts frozen",
        },
        "isolation": {
            "s2": "OFF",
            "t2": "OFF",
            "s3a": "OFF vs ON paired",
            "schedule_seed": SCHEDULE_SEED,
        },
        "model_config": {
            "model": model,
            "provider": "lmstudio_openai_compatible",
            "base_url": base_url,
            "endpoint_host": endpoint_host(base_url),
            "thinking": thinking.upper(),
            "context_tokens": 8192,
            "temperature": 0,
            "timeout_seconds": timeout,
            "lm_studio_version": _lms_version(),
            "hardware": platform.platform(),
        },
        "environment": env_notes,
        "warmup": warmup,
        "trial_schedule": schedule,
        "schedule_seed": SCHEDULE_SEED,
        "scored_trials": len(trials),
        "selection_metrics": {
            "primary_metric": "search_documents selected on GQ-131",
            "S3A_OFF": {
                "search_documents": f"{off_metrics['search_documents']}/10",
                "semantic_search": f"{off_metrics['semantic_search']}/10",
                "other_tool": f"{off_metrics['other_tool']}/10",
                "invalid_decision": f"{off_metrics['invalid_decision']}/10",
                "selection_correct": f"{off_metrics['selection_correct']}/10",
                "full_task_pass": f"{off_metrics['full_task_pass']}/10",
                "counts": off_metrics,
            },
            "S3A_ON": {
                "search_documents": f"{on_metrics['search_documents']}/10",
                "semantic_search": f"{on_metrics['semantic_search']}/10",
                "other_tool": f"{on_metrics['other_tool']}/10",
                "invalid_decision": f"{on_metrics['invalid_decision']}/10",
                "selection_correct": f"{on_metrics['selection_correct']}/10",
                "full_task_pass": f"{on_metrics['full_task_pass']}/10",
                "counts": on_metrics,
            },
            "delta_selection_on_minus_off": (
                on_metrics["selection_correct"] - off_metrics["selection_correct"]
            ),
        },
        "schema_tna": {
            "unrecovered_total": unrecovered,
            "note": "schema recovery ≠ TOOL capability success",
        },
        "safety_metrics": safety_totals,
        "hard_negatives": hn,
        "latency": {
            "S3A_OFF": _latency_bundle(off_trials),
            "S3A_ON": _latency_bundle(on_trials),
        },
        "interpretation": interpretation,
        "capability_label": interpretation["capability_label"],
        "POSSIBLE_MODEL_SELECTION_BOUNDARY": interpretation[
            "possible_model_selection_boundary"
        ],
        "ready_for_freeze": interpretation["ready_for_freeze"],
        "runtime_rollout": False,
        "product_remediation": False,
        "GPU_LANE_RELEASED": bool(release_gpu and gpu_release is not None),
        "gpu_release": gpu_release,
        "forbidden_changes": [
            "s3a_implementation",
            "tool_descriptions_outside_experiment",
            "planner",
            "tool_resolver",
            "golden",
            "parser",
            "t2",
            "s2",
        ],
        "settings_after_run": {
            "s3a": bool(settings.agent_l4_tool_contrastive_selection_enabled),
            "s2": bool(settings.agent_l4_tool_preferred_hint_enabled),
            "t2": bool(settings.agent_l4_task_satisfied_hint_enabled),
        },
        "trials": trials,
    }

    out_path = root / REPORT_REL
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    payload["output_path"] = str(out_path)

    # Also copy under tests/fixtures for offline schema tests when full panel completed.
    if len(trials) == 20 and not model_residency_break:
        fixture_dir = root / "tests" / "fixtures" / "l4_tool_capability"
        fixture_dir.mkdir(parents=True, exist_ok=True)
        fixture_path = fixture_dir / "w8-tool-s3a-real-revalidation.json"
        fixture_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        payload["fixture_path"] = str(fixture_path)

    return payload
