"""TOOL P4 real local product ablation — S2/T2 flag matrix on frozen subset."""

from __future__ import annotations

import hashlib
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
    wait_ready,
)
from app.eval.local_model_profile.adapter import OpenAICompatibleAdapter, endpoint_host
from app.eval.local_model_profile.schema import ThinkingMode
from app.eval.tool_capability.migration_contract import MIGRATED_CASE_BY_ID
from app.eval.tool_capability.p1_freeze import load_p1_manifest, manifest_path
from app.eval.tool_capability.p4_telemetry import (
    build_p4_safety,
    build_s2_telemetry,
    build_t2_telemetry,
    latency_from_trial,
)
from app.eval.tool_capability.real_execute import run_real_trial
from app.eval.tool_capability.seed import seed_case_workspace
from app.eval.tool_capability.taxonomy import analyze_trial
from app.services.agent import tool_guidance_hints as hints_mod

CASE_ORDER = ("GQ-131", "GQ-132", "GQ-149")
CONDITIONS: tuple[tuple[str, bool, bool], ...] = (
    ("00", False, False),
    ("10", True, False),
    ("01", False, True),
    ("11", True, True),
)
STABILITY_TRIALS = 5
SCHEDULE_SEED = "tool-p4-interleaved-v1"
REPORT_REL = Path("artifacts/benchmarks/tmp/reports/w8-tool-p4-real-local-ablation.json")
STAGE = "TOOL_P4_REAL_LOCAL_PRODUCT_REVALIDATION"
HINT_FLAG_NAMES = (
    "agent_l4_tool_preferred_hint_enabled",
    "agent_l4_task_satisfied_hint_enabled",
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _manifest_hash() -> str:
    raw = manifest_path(_repo_root()).read_bytes()
    return hashlib.sha256(raw).hexdigest()


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
        out = (proc.stdout or proc.stderr or "").strip()
        return out or "unknown"
    except (FileNotFoundError, subprocess.SubprocessError):
        return "lms_not_found"


def build_interleaved_schedule(
    *,
    cases: tuple[str, ...] = CASE_ORDER,
    conditions: tuple[tuple[str, bool, bool], ...] = CONDITIONS,
    rounds: int = STABILITY_TRIALS,
) -> list[dict[str, Any]]:
    """Paired/interleaved: round r → each case × each condition."""
    schedule: list[dict[str, Any]] = []
    seq = 0
    for round_idx in range(1, rounds + 1):
        for case_id in cases:
            for cond_id, s2, t2 in conditions:
                seq += 1
                schedule.append(
                    {
                        "seq": seq,
                        "round": round_idx,
                        "case_id": case_id,
                        "condition": cond_id,
                        "s2_enabled": s2,
                        "t2_enabled": t2,
                        "panel": "primary" if round_idx == 1 else "stability",
                        "trial_index": round_idx,
                    }
                )
    return schedule


def _apply_hint_flags(*, s2: bool, t2: bool) -> dict[str, Any]:
    saved = {name: getattr(settings, name) for name in HINT_FLAG_NAMES}
    settings.agent_l4_tool_preferred_hint_enabled = s2
    settings.agent_l4_task_satisfied_hint_enabled = t2
    return saved


def _restore_hint_flags(saved: dict[str, Any]) -> None:
    for name, value in saved.items():
        setattr(settings, name, value)


def _install_hint_probe(emissions: list[dict[str, Any]]):
    original = hints_mod.apply_tool_guidance_hints

    def _wrapped(summary, state, exposed_tools, **kwargs):  # noqa: ANN001
        out = original(summary, state, exposed_tools, **kwargs)
        emissions.append(
            {
                "preferred_tool_hint": out.preferred_tool_hint,
                "preferred_tool_intent": out.preferred_tool_intent,
                "preferred_tool_reason": out.preferred_tool_reason,
                "task_contract_satisfied": bool(out.task_contract_satisfied),
                "steps_before": len(state.steps),
            }
        )
        return out

    hints_mod.apply_tool_guidance_hints = _wrapped  # type: ignore[method-assign]
    return original


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


def _aggregate_latency(trials: list[dict[str, Any]]) -> dict[str, Any]:
    walls = [float(t["latency"]["trajectory_wall_ms"]) for t in trials]
    steps = [float(t["latency"]["steps_used"]) for t in trials]
    return {
        "n": len(trials),
        "mean_wall_ms": round(statistics.mean(walls), 1) if walls else None,
        "p50_wall_ms": _percentile(walls, 50),
        "p95_wall_ms": _percentile(walls, 95),
        "mean_steps": round(statistics.mean(steps), 3) if steps else None,
        "mean_model_calls": (
            round(statistics.mean(float(t["latency"]["model_call_count"]) for t in trials), 3)
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
        "mean_tool_latency_ms": (
            round(
                statistics.mean(float(t["latency"]["tool_execution_latency_ms"]) for t in trials),
                1,
            )
            if trials
            else None
        ),
        "mean_non_model_ms": (
            round(statistics.mean(float(t["latency"]["non_model_time_ms"]) for t in trials), 1)
            if trials
            else None
        ),
    }


def _score_condition(trials: list[dict[str, Any]], *, condition: str) -> dict[str, Any]:
    subset = [t for t in trials if t["condition"] == condition]
    primary = [t for t in subset if t["panel"] == "primary"]
    primary_pass = sum(1 for t in primary if t["task_completion"])
    stability_pass = sum(1 for t in subset if t["task_completion"])
    per_case = {
        case_id: sum(
            1 for t in subset if t["case_id"] == case_id and t["task_completion"]
        )
        for case_id in CASE_ORDER
    }
    return {
        "condition": condition,
        "primary": f"{primary_pass}/{len(CASE_ORDER)}",
        "primary_pass": primary_pass,
        "stability": f"{stability_pass}/{len(CASE_ORDER) * STABILITY_TRIALS}",
        "stability_pass": stability_pass,
        "per_case": {k: f"{v}/{STABILITY_TRIALS}" for k, v in per_case.items()},
        "per_case_pass": per_case,
    }


def _interpret(
    *,
    by_condition: dict[str, dict[str, Any]],
    safety_totals: dict[str, int],
    unrecovered_tna: int,
    measurement_valid: bool,
) -> dict[str, Any]:
    if not measurement_valid or unrecovered_tna > 0:
        return {
            "case": "Case5",
            "label": "INCONCLUSIVE/INVALID",
            "real_validation": "INVALID",
            "ready_for_p4_freeze": False,
            "ready_for_runtime_rollout": False,
            "reason": "measurement invalid or schema unrecovered",
        }

    hard = (
        "unsafe_terminal",
        "premature_finish",
        "false_task_satisfied_hint",
        "wrong_preferred_tool_hint",
        "out_of_scope_tool_accept",
        "invalid_args_accept",
        "failed_tool_marked_success",
        "matcher_false_positive",
        "failed_tool_coverage_pollution",
        "schema_unrecovered",
    )
    if any(int(safety_totals.get(k, 0)) > 0 for k in hard):
        return {
            "case": "Case4",
            "label": "REGRESSION",
            "real_validation": "REGRESSION",
            "ready_for_p4_freeze": False,
            "ready_for_runtime_rollout": False,
            "reason": "A13 safety hard gate > 0",
        }

    b00 = by_condition["00"]["stability_pass"]
    b10 = by_condition["10"]["stability_pass"]
    b01 = by_condition["01"]["stability_pass"]
    b11 = by_condition["11"]["stability_pass"]

    # 2×2 factorial effects on stability (vs contemporaneous 00).
    # interaction_term = b11 - b00 - (b10-b00) - (b01-b00) = b11 - b10 - b01 + b00
    s2_effect = b10 - b00
    t2_effect = b01 - b00
    s2_x_t2_interaction = b11 - b10 - b01 + b00
    s2_gain = s2_effect > 0
    t2_gain = t2_effect > 0
    any_gain = s2_gain or t2_gain or b11 > b00

    # Do NOT call 11≈01 with S2≈0 "additive" — that is T2-dominant, interaction≈0.
    if s2_x_t2_interaction < 0 and (s2_gain or t2_gain):
        condition_11 = "INTERFERING"
    elif s2_effect == 0 and t2_effect > 0 and b11 == b01:
        condition_11 = "NO_INTERACTION/T2-DOMINANT"
    elif t2_effect == 0 and s2_effect > 0 and b11 == b10:
        condition_11 = "NO_INTERACTION/S2-DOMINANT"
    elif s2_effect > 0 and t2_effect > 0 and s2_x_t2_interaction == 0:
        condition_11 = "ADDITIVE"
    elif s2_effect > 0 and t2_effect > 0 and s2_x_t2_interaction > 0:
        condition_11 = "SUPER_ADDITIVE"
    elif not any_gain:
        condition_11 = "NEUTRAL"
    else:
        condition_11 = "MIXED"

    # Family hypotheses (not hard gates)
    s2_fixes_s = by_condition["10"]["per_case_pass"].get("GQ-131", 0) > by_condition["00"][
        "per_case_pass"
    ].get("GQ-131", 0)
    t2_fixes_t = (
        by_condition["01"]["per_case_pass"].get("GQ-132", 0)
        + by_condition["01"]["per_case_pass"].get("GQ-149", 0)
    ) > (
        by_condition["00"]["per_case_pass"].get("GQ-132", 0)
        + by_condition["00"]["per_case_pass"].get("GQ-149", 0)
    )

    interaction = {
        "s2_only_fixes_family_s": s2_fixes_s,
        "t2_only_fixes_family_t": t2_fixes_t,
        "cross_effects_observed": bool(
            (s2_gain and not s2_fixes_s) or (t2_gain and not t2_fixes_t)
        ),
        "condition_11": condition_11,
        "s2_effect": s2_effect,
        "t2_effect": t2_effect,
        "s2_x_t2_interaction": s2_x_t2_interaction,
        "stability_deltas_vs_00": {
            "10": s2_effect,
            "01": t2_effect,
            "11": b11 - b00,
        },
        "causal_note": (
            "Gain attributed to single factor when the other effect is 0 and "
            "11 matches the effective single-factor cell (interaction≈0)."
        ),
    }

    # Factor-level labels (discipline): never mark S2 REAL_VALIDATED when effect≈0.
    s2_validation = (
        "REAL_VALIDATED_ON_FROZEN_SUBSET"
        if s2_gain and s2_fixes_s
        else "NO_MEASURABLE_GAIN"
    )
    t2_validation = (
        "REAL_VALIDATED_ON_FROZEN_SUBSET"
        if t2_gain and t2_fixes_t
        else "NO_MEASURABLE_GAIN"
    )

    if any_gain and (s2_fixes_s or t2_fixes_t) and b11 >= b00:
        return {
            "case": "Case1",
            "label": "PASS + REAL_VALIDATED_ON_FROZEN_SUBSET",
            # Overall panel label reflects measurable frozen-subset gain (here T2-driven).
            # Factor labels below are authoritative for S2 vs T2 claims.
            "real_validation": "REAL_VALIDATED_ON_FROZEN_SUBSET",
            "s2_validation": s2_validation,
            "t2_validation": t2_validation,
            "ready_for_p4_freeze": True,
            "ready_for_runtime_rollout": False,
            "defaults_remain_off": True,
            "interaction": interaction,
            "reason": "measurable gain on frozen subset with safety clean; rollout still NO",
        }

    if any_gain:
        return {
            "case": "Case2",
            "label": "PASS/CONDITIONAL",
            "real_validation": "CONDITIONAL",
            "s2_validation": s2_validation,
            "t2_validation": t2_validation,
            "ready_for_p4_freeze": True,
            "ready_for_runtime_rollout": False,
            "defaults_remain_off": True,
            "interaction": interaction,
            "reason": "some gain but causal pattern incomplete or mixed",
        }

    return {
        "case": "Case3",
        "label": "PASS/NO_MEASURABLE_GAIN",
        "real_validation": "NO_MEASURABLE_GAIN",
        "s2_validation": s2_validation,
        "t2_validation": t2_validation,
        "ready_for_p4_freeze": True,
        "ready_for_runtime_rollout": False,
        "defaults_remain_off": True,
        "interaction": interaction,
        "reason": "contemporaneous panel shows no stability gain vs 00; still characterized",
    }


async def run_tool_p4_ablation(
    *,
    base_url: str = "http://127.0.0.1:1234/v1",
    model: str = DEFAULT_MODEL,
    thinking: str = "off",
    timeout: float = DEFAULT_TIMEOUT,
    skip_reload: bool = False,
    skip_warmup: bool = False,
    max_trials: int | None = None,
) -> dict[str, Any]:
    root = _repo_root()
    round_start_master_sha = git_sha()
    tool_p4_base_sha = round_start_master_sha
    run_id = str(uuid.uuid4())
    started_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    # Defaults must remain OFF outside measured conditions.
    assert settings.agent_l4_tool_preferred_hint_enabled is False
    assert settings.agent_l4_task_satisfied_hint_enabled is False

    inner = OpenAICompatibleAdapter(
        base_url=base_url,
        model=model,
        timeout_seconds=timeout,
        thinking_mode=ThinkingMode.off if thinking == "off" else ThinkingMode.on,
        provider="lmstudio_openai_compatible",
    )
    adapter = RecordingAdapter(inner)

    env_notes: dict[str, Any] = {
        "server_warm_state": "unknown",
        "model_residency_break": False,
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
            "warmup_success": sum(1 for r in records if not r.get("timed_out") and not r.get("error")),
            "warmup_latency": [r.get("latency_ms") for r in records],
            "records": records,
        }
        env_notes["server_warm_state"] = "warmed"
    else:
        warmup = {"warmup_count": 0, "warmup_success": 0, "warmup_latency": [], "skipped": True}

    schedule = build_interleaved_schedule()
    if max_trials is not None:
        schedule = schedule[:max_trials]

    seeded_by_case: dict[str, Any] = {}
    for case_id in CASE_ORDER:
        seeded_by_case[case_id] = await seed_case_workspace(case_id)

    trials: list[dict[str, Any]] = []
    product_issues: list[dict[str, Any]] = []

    for slot in schedule:
        case_id = slot["case_id"]
        cond = slot["condition"]
        s2 = bool(slot["s2_enabled"])
        t2 = bool(slot["t2_enabled"])
        emissions: list[dict[str, Any]] = []
        orig_hints = _install_hint_probe(emissions)
        flag_saved = _apply_hint_flags(s2=s2, t2=t2)
        try:
            record = await run_real_trial(
                case_id=case_id,
                trial_index=int(slot["trial_index"]),
                panel=str(slot["panel"]),
                adapter=adapter,
                model_id=model,
                thinking_mode=thinking.upper(),
                seeded=seeded_by_case[case_id],
            )
        finally:
            hints_mod.apply_tool_guidance_hints = orig_hints  # type: ignore[method-assign]
            _restore_hint_flags(flag_saved)

        # Ensure process defaults stay OFF between trials.
        settings.agent_l4_tool_preferred_hint_enabled = False
        settings.agent_l4_task_satisfied_hint_enabled = False

        traj = record.trajectory_input
        analysis = analyze_trial(
            traj,
            captures=record.captures,
            outcome=record.outcome,
        )
        s2_tel = build_s2_telemetry(
            case_id=case_id,
            s2_enabled=s2,
            captures=record.captures,
            outcome=record.outcome,
            hint_emissions=emissions,
        )
        t2_tel = build_t2_telemetry(
            case_id=case_id,
            t2_enabled=t2,
            captures=record.captures,
            outcome=record.outcome,
            trajectory=record.trajectory,
            hint_emissions=emissions,
        )
        safety = build_p4_safety(
            base_safety=analysis.safety,
            s2=s2_tel,
            t2=t2_tel,
            task_completion=analysis.evaluation.task_completion,
            trajectory=record.trajectory,
        )
        latency = latency_from_trial(
            duration_ms=record.duration_ms,
            captures=record.captures,
            outcome=record.outcome,
        )

        if analysis.failure_taxonomy == "OTHER" and not analysis.evaluation.task_completion:
            product_issues.append(
                {
                    "seq": slot["seq"],
                    "case_id": case_id,
                    "condition": cond,
                    "note": "TOOL_P4_PRODUCT_ISSUE",
                }
            )

        trial_payload = {
            "seq": slot["seq"],
            "round": slot["round"],
            "case_id": case_id,
            "condition": cond,
            "s2_enabled": s2,
            "t2_enabled": t2,
            "trial_index": slot["trial_index"],
            "panel": slot["panel"],
            "task_completion": analysis.evaluation.task_completion,
            "first_failed_stage": analysis.first_failed_stage,
            "failure_taxonomy": analysis.failure_taxonomy,
            "stages": analysis.evaluation.to_dict()["stages"],
            "s2_telemetry": s2_tel,
            "t2_telemetry": t2_tel,
            "hint_emissions": emissions,
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
        trials.append(trial_payload)

    by_condition = {
        cond: _score_condition(trials, condition=cond) for cond, _, _ in CONDITIONS
    }

    safety_totals = {
        k: 0
        for k in (
            "unsafe_terminal",
            "premature_finish",
            "false_task_satisfied_hint",
            "wrong_preferred_tool_hint",
            "out_of_scope_tool_accept",
            "invalid_args_accept",
            "failed_tool_marked_success",
            "matcher_false_positive",
            "failed_tool_coverage_pollution",
            "schema_unrecovered",
        )
    }
    for t in trials:
        for k in safety_totals:
            safety_totals[k] += int(t["safety"].get(k, 0))

    raw_tna = sum(t["tna"]["raw"] for t in trials)
    recovered_tna = sum(t["tna"]["recovered"] for t in trials)
    unrecovered_tna = sum(t["tna"]["unrecovered"] for t in trials)

    taxonomy: dict[str, int] = {}
    for t in trials:
        key = t["failure_taxonomy"] or "NONE"
        taxonomy[key] = taxonomy.get(key, 0) + 1

    latency_by_condition = {
        cond: _aggregate_latency([t for t in trials if t["condition"] == cond])
        for cond, _, _ in CONDITIONS
    }

    # S2 selection improvement summary (GQ-131)
    def _sel_rate(cond: str) -> dict[str, Any]:
        rows = [
            t
            for t in trials
            if t["condition"] == cond and t["case_id"] == "GQ-131"
        ]
        improved = sum(1 for t in rows if t["s2_telemetry"]["gq131_selection_improved"])
        return {"improved": f"{improved}/{len(rows)}", "n": len(rows), "pass": improved}

    s2_summary = {
        "core_question": (
            "Does S2 ON improve search_documents selection vs historical semantic_search?"
        ),
        "by_condition": {cond: _sel_rate(cond) for cond, _, _ in CONDITIONS},
        "hint_emitted_alone_is_not_success": True,
    }

    def _term_rate(cond: str) -> dict[str, Any]:
        rows = [
            t
            for t in trials
            if t["condition"] == cond and t["case_id"] in {"GQ-132", "GQ-149"}
        ]
        improved = sum(1 for t in rows if t["t2_telemetry"]["termination_improved"])
        return {"improved": f"{improved}/{len(rows)}", "n": len(rows), "pass": improved}

    t2_summary = {
        "core_question": (
            "After successful observation, does T2 stop tool loop and reach legal safe terminal?"
        ),
        "by_condition": {cond: _term_rate(cond) for cond, _, _ in CONDITIONS},
    }

    measurement_valid = bool(ready.get("ready")) and not env_notes.get("model_residency_break")
    interpretation = _interpret(
        by_condition=by_condition,
        safety_totals=safety_totals,
        unrecovered_tna=unrecovered_tna,
        measurement_valid=measurement_valid,
    )

    p1 = load_p1_manifest(root)
    payload: dict[str, Any] = {
        "schema_version": "w8-tool-p4-real-local-ablation-v1",
        "stage": STAGE,
        "run_id": run_id,
        "started_at": started_at,
        "round_start_master_sha": round_start_master_sha,
        "tool_p4_base_sha": tool_p4_base_sha,
        "head_sha": git_sha(),
        "master_advanced_beyond_known": False,
        "known_reference_sha": "4c81c6340f1789a641ef0d6cbaf42c1efdaa2bc2",
        "pr_lineage": {
            "pr30_tool_p3_offline_ablation": True,
            "pr32_s2_t2_product_experiment": True,
        },
        "contract_manifest_hash": _manifest_hash(),
        "capability_label": "CURRENT_L3_TOOL_CAPABILITY ON_FROZEN_MIGRATED_SUBSET",
        "not_labels": [
            "NOT TOOL20",
            "NOT full capability",
            "NOT broad capability from 0% to X%",
        ],
        "frozen_subset": list(CASE_ORDER),
        "denominator": 3,
        "feature_flag_matrix": {
            "defaults": {
                "agent_l4_tool_preferred_hint_enabled": False,
                "agent_l4_task_satisfied_hint_enabled": False,
            },
            "conditions": {
                cond: {"s2": s2, "t2": t2} for cond, s2, t2 in CONDITIONS
            },
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
        "warmup": warmup,
        "schedule_seed": SCHEDULE_SEED,
        "trial_schedule": schedule,
        "scored_trials": len(trials),
        "primary": {cond: by_condition[cond]["primary"] for cond, _, _ in CONDITIONS},
        "stability": {cond: by_condition[cond]["stability"] for cond, _, _ in CONDITIONS},
        "per_case": {
            case_id: {
                cond: by_condition[cond]["per_case"][case_id] for cond, _, _ in CONDITIONS
            }
            for case_id in CASE_ORDER
        },
        "condition_metrics": by_condition,
        "s2_selection_summary": s2_summary,
        "t2_termination_summary": t2_summary,
        "failure_taxonomy": taxonomy,
        "safety_metrics": safety_totals,
        "tna_tracking": {
            "raw_tool_name_as_action": raw_tna,
            "recovered_tool_name_as_action": recovered_tna,
            "unrecovered_tool_name_as_action": unrecovered_tna,
            "note": "schema recovery ≠ TOOL capability success; prove P7 no regression",
        },
        "latency_by_condition": latency_by_condition,
        "interpretation": interpretation,
        "p2_historical_reference": {
            "model": "zai-org/glm-4.6v-flash",
            "primary": "0/3",
            "stability": "0/15",
            "taxonomy": {"PLANNER_WRONG_TOOL": 5, "BUDGET_EXHAUSTION": 10},
            "raw_tna_recovered": "10/10",
            "note": "NOT substitute for contemporaneous 00",
        },
        "environment": env_notes,
        "product_issues": product_issues,
        "p1_lineage": {
            "p1_base_sha": p1.get("base_sha"),
            "migrated_case_ids": p1.get("migrated_case_ids"),
            "contract_hashes": {
                cid: MIGRATED_CASE_BY_ID[cid].migration_contract_hash for cid in CASE_ORDER
            },
        },
        "trials": trials,
        "recommended_next": (
            "Freeze P4 characterization on frozen subset; keep defaults OFF; "
            "do not start MEMORY P3; do not runtime rollout."
            if interpretation.get("ready_for_p4_freeze")
            else "Investigate measurement validity / safety before freeze."
        ),
    }

    out_path = root / REPORT_REL
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    payload["output_path"] = str(out_path)
    return payload
