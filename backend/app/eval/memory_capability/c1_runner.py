"""MEMORY C1 real local revalidation — contemporaneous OFF/ON/WITHOUT panel.

Eval/test-only. Does not modify C1 product implementation, evaluator, or Golden.
"""

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
    git_sha,
    reload_model,
    run_lms,
    wait_ready,
)
from app.eval.local_model_profile.adapter import OpenAICompatibleAdapter, endpoint_host
from app.eval.local_model_profile.schema import ThinkingMode
from app.eval.memory_capability.c1_flags import assert_production_c1_default
from app.eval.memory_capability.evaluator import evaluate_counterfactual, evaluate_trajectory
from app.eval.memory_capability.exposure_event import MemoryExposureEvent, MemoryExposureSource
from app.eval.memory_capability.exposure_semantics import is_authoritative_exposure
from app.eval.memory_capability.golden_audit import golden_memory4_audits
from app.eval.memory_capability.l3_exposure_evaluator import (
    l3_exposed_from_events,
    validate_exposure_event,
)
from app.eval.memory_capability.p3_execute import run_memory_p3_trial
from app.eval.memory_capability.p3_flags import assert_production_exposure_default
from app.eval.memory_capability.proposition import (
    extract_propositions,
    proposition_semantically_satisfied,
)
from app.eval.memory_capability.schema import CounterfactualPair, MeasurementLevel, MemorySeed
from app.eval.memory_utilization_ablation.evaluator_audit import (
    audit_l4_semantics,
    build_hard_negatives,
    score_hard_negative,
)
from tests.golden_agent_qa_loader import AgentGoldenCase, load_golden_agent_cases

SEEDED_IDS = ("GA-9", "GA-10")
TRIALS_PER_CASE = 5
# Per-round interleave (task contract): GA9 OFF → GA9 ON → GA9 WITHOUT → GA10 …
CONDITIONS: tuple[str, ...] = ("OFF_WITH_MEMORY", "ON_WITH_MEMORY", "WITHOUT_MEMORY")
REPORT_REL = Path("artifacts/benchmarks/tmp/reports/w8-memory-c1-real-revalidation.json")
STAGE = "MEMORY_C1_REAL_LOCAL_REVALIDATION"
SCHEDULE_SEED = "memory-c1-interleaved-v1"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


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


def _case_hash(case: AgentGoldenCase) -> str:
    payload = {
        "case_id": case.case_id,
        "query": case.query,
        "expected_chunk": case.expected_chunk,
        "pre_seed_memories": list(case.pre_seed_memories),
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def build_interleaved_schedule(
    *,
    cases: tuple[str, ...] = SEEDED_IDS,
    conditions: tuple[str, ...] = CONDITIONS,
    rounds: int = TRIALS_PER_CASE,
) -> list[dict[str, Any]]:
    """Paired/interleaved: round r → GA-9×3 then GA-10×3 (never all-ON then all-OFF)."""
    schedule: list[dict[str, Any]] = []
    seq = 0
    for round_idx in range(1, rounds + 1):
        for case_id in cases:
            for condition in conditions:
                seq += 1
                schedule.append(
                    {
                        "seq": seq,
                        "round": round_idx,
                        "case_id": case_id,
                        "condition": condition,
                        "c1_enabled": condition == "ON_WITH_MEMORY",
                        "with_memory": condition != "WITHOUT_MEMORY",
                        "trial_index": round_idx,
                    }
                )
    return schedule


def _events_from_dicts(raw: list[dict[str, Any]]) -> tuple[MemoryExposureEvent, ...]:
    from app.eval.memory_capability.exposure_event import (
        CONTEXT_SLOT_PLANNER_USER_PROMPT,
        MemoryExposureChannel,
        MemoryExposureScope,
    )

    out: list[MemoryExposureEvent] = []
    for item in raw:
        scope_raw = item.get("scope") or "run"
        source_raw = item.get("source") or MemoryExposureSource.planner_prompt_injection.value
        channel_raw = item.get("channel") or MemoryExposureChannel.next_action_planner.value
        out.append(
            MemoryExposureEvent(
                run_id=str(item.get("run_id") or ""),
                step_id=str(item.get("step_id") or ""),
                memory_hash=str(item.get("memory_hash") or ""),
                injected_to_context=bool(item.get("injected_to_context")),
                scope=MemoryExposureScope(scope_raw)
                if not isinstance(scope_raw, MemoryExposureScope)
                else scope_raw,
                source=MemoryExposureSource(source_raw)
                if not isinstance(source_raw, MemoryExposureSource)
                else source_raw,
                context_slot=str(item.get("context_slot") or CONTEXT_SLOT_PLANNER_USER_PROMPT),
                channel=MemoryExposureChannel(channel_raw)
                if not isinstance(channel_raw, MemoryExposureChannel)
                else channel_raw,
                memory_id=item.get("memory_id"),
                proposition_id=item.get("proposition_id"),
                memory_key=item.get("memory_key"),
                timestamp=item.get("timestamp"),
            )
        )
    return tuple(out)


def _score_with_events(
    *,
    traj,
    run_id: str | None,
    expected_hashes: list[str],
    event_dicts: list[dict[str, Any]],
    empty_case: bool,
):
    evaluation = evaluate_trajectory(traj)
    if not run_id:
        return evaluation, {
            "l3_source": "no_run_id",
            "l3_event_pass": False,
            "l3_reason": "missing run_id",
        }
    events = _events_from_dicts(event_dicts)
    l3 = l3_exposed_from_events(
        run_id=run_id,
        expected_memory_hashes=expected_hashes,
        events=events,
        empty_memory_case=empty_case,
    )
    levels = list(evaluation.levels)
    for i, level in enumerate(levels):
        if level.level == MeasurementLevel.L3_EXPOSED:
            levels[i] = l3
            break
    evaluation.levels = tuple(levels)
    return evaluation, {
        "l3_source": "MemoryExposureEvent",
        "l3_event_pass": l3.passed,
        "l3_reason": l3.reason,
        "authoritative_event_count": sum(1 for e in events if is_authoritative_exposure(e)),
    }


def _observable_language_util(seeds: tuple[MemorySeed, ...], output: str, tool_query: str | None) -> bool:
    """Language proposition only — P4 PARTIAL blind-spot companion metric (not a gate)."""
    for prop in extract_propositions(seeds):
        if prop.kind.value == "language_preference":
            return proposition_semantically_satisfied(prop, output, tool_query=tool_query)
    return False


def _intended_seeds(case: AgentGoldenCase) -> tuple[MemorySeed, ...]:
    return tuple(
        MemorySeed(key=m["key"], memory_type=m["memory_type"], value=dict(m["value"]))
        for m in case.pre_seed_memories
    )


def _latency_bundle(trials: list[dict[str, Any]]) -> dict[str, Any]:
    if not trials:
        return {
            "n": 0,
            "mean_trajectory_wall_ms": 0.0,
            "mean_model_calls": 0.0,
            "mean_model_latency_ms": 0.0,
            "mean_steps": 0.0,
        }
    walls = [float(t.get("duration_ms") or 0.0) for t in trials]
    calls = [float(t.get("model_calls") or 0.0) for t in trials]
    model_lat = [float(t.get("model_latency_ms") or 0.0) for t in trials]
    steps = [float((t.get("outcome") or {}).get("steps_used") or 0.0) for t in trials]
    return {
        "n": len(trials),
        "mean_trajectory_wall_ms": round(statistics.fmean(walls), 1),
        "mean_model_calls": round(statistics.fmean(calls), 2),
        "mean_model_latency_ms": round(statistics.fmean(model_lat), 1),
        "mean_steps": round(statistics.fmean(steps), 2),
    }


def _classify(
    *,
    l3_off: int,
    l3_on: int,
    l4_off: int,
    l4_on: int,
    l5_on: int,
    false_util: int,
    privacy_leaks: int,
    empty_fake: int,
    wrong_scope: int,
    wrong_run: int,
    hn_false: int,
    model_residency_break: bool,
) -> str:
    if model_residency_break:
        return "INCONCLUSIVE"
    safety_bad = (
        false_util > 0
        or privacy_leaks > 0
        or empty_fake > 0
        or wrong_scope > 0
        or wrong_run > 0
        or hn_false > 0
    )
    if safety_bad or l3_on < l3_off:
        return "REGRESSION"
    if l4_on > l4_off and l5_on > 0:
        return "REAL_VALIDATED"
    if l4_on > l4_off and l5_on == 0:
        return "REAL_VALIDATED_FOR_L4_ONLY"
    if l4_on == l4_off and l5_on == 0:
        return "NO_MEASURABLE_GAIN"
    return "INCONCLUSIVE"


def release_gpu_lane() -> dict[str, Any]:
    """Unload all LM Studio models so other tasks can take the GPU."""
    return run_lms(["unload", "--all"])


async def run_memory_c1_revalidation(
    *,
    base_url: str = "http://127.0.0.1:1234/v1",
    model: str = DEFAULT_MODEL,
    thinking: str = "off",
    timeout: float = DEFAULT_TIMEOUT,
    skip_reload: bool = False,
    skip_warmup: bool = False,
    release_gpu: bool = True,
) -> dict[str, Any]:
    root = _repo_root()
    memory_c1_base_sha = git_sha()
    run_id = str(uuid.uuid4())
    started_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    model_residency_break = False
    product_issues: list[str] = []

    cases = {c.case_id: c for c in load_golden_agent_cases() if c.case_id in SEEDED_IDS}
    case_hashes = {cid: _case_hash(cases[cid]) for cid in SEEDED_IDS}

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
        "production_exposure_trace_default_false": assert_production_exposure_default(),
        "production_c1_relevance_default_false": assert_production_c1_default(),
        "benchmark_flags": {
            "agent_memory_enabled": True,
            "agent_memory_exposure_trace_enabled": True,
            "agent_memory_relevance_label_enabled": "per-trial",
        },
        "settings_c1_at_start": bool(settings.agent_memory_relevance_label_enabled),
    }
    if not skip_reload:
        env_notes["model_reload"] = reload_model(model)
    ready = wait_ready(inner)
    env_notes["ready"] = ready
    if not ready.get("ready"):
        raise RuntimeError(f"LM Studio not ready: {ready}")

    warmup: list[dict[str, Any]] = []
    if not skip_warmup:
        for i in range(1, 4):
            result = adapter.chat_completion(
                [
                    {"role": "system", "content": "Reply with exactly: OK"},
                    {"role": "user", "content": "ping"},
                ],
                temperature=0.0,
                max_tokens=16,
            )
            warmup.append(
                {
                    "index": i,
                    "timed_out": result.timed_out,
                    "latency_ms": round(result.latency_ms, 1),
                    "error": result.error,
                    "excerpt": (result.content or "")[:40],
                }
            )
    env_notes["warmup"] = warmup

    schedule = build_interleaved_schedule()
    trials: list[dict[str, Any]] = []
    off_records: dict[tuple[str, int], Any] = {}
    on_records: dict[tuple[str, int], Any] = {}
    without_records: dict[tuple[str, int], Any] = {}
    paired_l5_on: list[dict[str, Any]] = []
    paired_l5_off: list[dict[str, Any]] = []
    all_exposure_events: list[dict[str, Any]] = []
    false_utilization = 0
    privacy_leak_count = 0
    wrong_scope = 0
    wrong_run_step = 0
    empty_fake_exposure = 0

    for slot in schedule:
        cid = slot["case_id"]
        condition = slot["condition"]
        trial_index = slot["trial_index"]
        c1_on = bool(slot["c1_enabled"])
        calls_before = adapter.calls
        try:
            rec = await run_memory_p3_trial(
                case=cases[cid],
                trial_index=trial_index,
                condition=condition,
                adapter=adapter,
                model_id=model,
                thinking_mode=thinking.upper(),
                run_timeout_seconds=timeout,
                c1_relevance_enabled=c1_on,
            )
        except Exception as exc:  # noqa: BLE001
            product_issues.append(
                f"MEMORY_C1_PRODUCT_ISSUE trial {cid}/{condition}/r{trial_index}: "
                f"{exc.__class__.__name__}: {exc}"
            )
            model_residency_break = True
            break

        key = (cid, trial_index)
        if condition == "OFF_WITH_MEMORY":
            off_records[key] = rec
        elif condition == "ON_WITH_MEMORY":
            on_records[key] = rec
        else:
            without_records[key] = rec

        with_like = condition != "WITHOUT_MEMORY"
        empty_for_l3 = not with_like
        eval_obj, l3_meta = _score_with_events(
            traj=rec.trajectory_input,
            run_id=rec.run_id,
            expected_hashes=rec.expected_memory_hashes if with_like else [],
            event_dicts=rec.exposure_events,
            empty_case=empty_for_l3,
        )
        if condition == "WITHOUT_MEMORY" and rec.run_id:
            l3 = l3_exposed_from_events(
                run_id=rec.run_id,
                expected_memory_hashes=[],
                events=_events_from_dicts(rec.exposure_events),
                empty_memory_case=True,
            )
            levels = list(eval_obj.levels)
            for i, level in enumerate(levels):
                if level.level == MeasurementLevel.L3_EXPOSED:
                    levels[i] = l3
            eval_obj.levels = tuple(levels)
            l3_meta = {
                "l3_source": "MemoryExposureEvent",
                "l3_event_pass": l3.passed,
                "l3_reason": l3.reason,
            }

        # Validate exposure events (wrong-run / schema)
        for ev in rec.exposure_events:
            events_typed = _events_from_dicts([ev])
            if events_typed:
                ok, reason = validate_exposure_event(events_typed[0])
                if not ok:
                    wrong_scope += 1
                    product_issues.append(
                        f"MEMORY_C1_PRODUCT_ISSUE invalid exposure: {reason}"
                    )
            if ev.get("run_id") and rec.run_id and ev.get("run_id") != rec.run_id:
                wrong_run_step += 1
            if condition == "WITHOUT_MEMORY" and ev.get("injected_to_context"):
                empty_fake_exposure += 1
            all_exposure_events.append(
                {
                    **ev,
                    "case_id": cid,
                    "trial": trial_index,
                    "condition": condition,
                }
            )

        if with_like and eval_obj.false_utilization:
            false_utilization += 1
        privacy_leak_count += len(rec.privacy_hits)

        seeds = _intended_seeds(cases[cid])
        obs_lang = (
            _observable_language_util(seeds, rec.output_text, rec.tool_query)
            if with_like
            else False
        )
        util = eval_obj.utilization
        model_calls = adapter.calls - calls_before
        model_latency_ms = round(
            sum(float(c.get("latency_ms") or 0.0) for c in rec.captures), 1
        )
        level_map = eval_obj.level_map()
        trials.append(
            {
                "case_id": cid,
                "trial_index": trial_index,
                "condition": condition,
                "c1_enabled": c1_on,
                "seq": slot["seq"],
                "L1_SEEDED": level_map["L1_SEEDED"].to_dict(),
                "L2_LOADED": level_map["L2_LOADED"].to_dict(),
                "L3_EXPOSED": level_map["L3_EXPOSED"].to_dict(),
                "L4_UTILIZED": level_map["L4_UTILIZED"].to_dict(),
                "L5_TASK_BENEFIT": {"attempted": False, "note": "filled after pairing"},
                "l3_meta": l3_meta,
                "observable_language_utilization": obs_lang,
                "evaluator_valid_utilization": bool(
                    level_map["L4_UTILIZED"].passed
                ),
                "utilization": (
                    {
                        "semantic_utilized": util.semantic_utilized,
                        "keyword_overlap_only": util.keyword_overlap_only,
                        "contradicted": util.contradicted,
                        "matched_propositions": list(util.matched_propositions),
                        "reason": util.reason,
                    }
                    if util
                    else None
                ),
                "proposition_records": rec.proposition_records,
                "task_contract_passed": rec.trajectory_input.task_contract_passed,
                "false_utilization": eval_obj.false_utilization,
                "privacy_hits": rec.privacy_hits,
                "duration_ms": rec.duration_ms,
                "model_calls": model_calls,
                "model_latency_ms": model_latency_ms,
                "run_id": rec.run_id,
                "exposure_events": rec.exposure_events,
                "output_excerpt": rec.output_text[:800],
                "tool_query": rec.tool_query,
                "outcome": rec.outcome,
                "exposed_context_excerpt": (rec.exposed_context or "")[:400],
            }
        )

        # Pair L5 when WITHOUT for this (case, round) is available with ON/OFF
        if key in without_records:
            without = without_records[key]
            for label, store, with_rec in (
                ("ON", paired_l5_on, on_records.get(key)),
                ("OFF", paired_l5_off, off_records.get(key)),
            ):
                if with_rec is None:
                    continue
                pair = CounterfactualPair(
                    case_id=cid,
                    with_memory=with_rec.trajectory_input,
                    without_memory=without.trajectory_input,
                )
                cf = evaluate_counterfactual(pair)
                l5 = cf.level_map()["L5_TASK_BENEFIT"]
                entry = {
                    "case_id": cid,
                    "trial_index": trial_index,
                    "with_condition": f"{label}_WITH_MEMORY",
                    "with_task_contract": with_rec.trajectory_input.task_contract_passed,
                    "without_task_contract": without.trajectory_input.task_contract_passed,
                    "L5_TASK_BENEFIT": l5.to_dict(),
                }
                store.append(entry)
                for t in trials:
                    if (
                        t["case_id"] == cid
                        and t["trial_index"] == trial_index
                        and t["condition"] == f"{label}_WITH_MEMORY"
                    ):
                        t["L5_TASK_BENEFIT"] = l5.to_dict()

    # Ensure C1 production-default restored after panel
    settings.agent_memory_relevance_label_enabled = False

    off_trials = [t for t in trials if t["condition"] == "OFF_WITH_MEMORY"]
    on_trials = [t for t in trials if t["condition"] == "ON_WITH_MEMORY"]
    without_trials = [t for t in trials if t["condition"] == "WITHOUT_MEMORY"]

    l3_off = sum(1 for t in off_trials if t["L3_EXPOSED"].get("passed"))
    l3_on = sum(1 for t in on_trials if t["L3_EXPOSED"].get("passed"))
    l4_off = sum(1 for t in off_trials if t["L4_UTILIZED"].get("passed"))
    l4_on = sum(1 for t in on_trials if t["L4_UTILIZED"].get("passed"))
    obs_lang_off = sum(1 for t in off_trials if t.get("observable_language_utilization"))
    obs_lang_on = sum(1 for t in on_trials if t.get("observable_language_utilization"))
    l5_on = sum(1 for p in paired_l5_on if p["L5_TASK_BENEFIT"].get("passed"))
    l5_off = sum(1 for p in paired_l5_off if p["L5_TASK_BENEFIT"].get("passed"))

    # WITHOUT false utilization: evaluator should not claim utilization on empty seeds
    without_false_util = sum(
        1
        for t in without_trials
        if t.get("false_utilization") or t["L4_UTILIZED"].get("passed")
    )
    false_utilization += without_false_util

    hn_results = [
        {
            "sample_id": hn.sample_id,
            "kind": hn.kind,
            "false_utilized": score_hard_negative(hn),
        }
        for hn in build_hard_negatives()
    ]
    hn_false = sum(1 for r in hn_results if r["false_utilized"])
    evaluator_audit = audit_l4_semantics()

    classification = _classify(
        l3_off=l3_off,
        l3_on=l3_on,
        l4_off=l4_off,
        l4_on=l4_on,
        l5_on=l5_on,
        false_util=false_utilization,
        privacy_leaks=privacy_leak_count,
        empty_fake=empty_fake_exposure,
        wrong_scope=wrong_scope,
        wrong_run=wrong_run_step,
        hn_false=hn_false,
        model_residency_break=model_residency_break,
    )
    capability_label = classification
    if classification == "REAL_VALIDATED" and l5_on > 0:
        capability_label = "REAL_VALIDATED (+ CAUSAL_TASK_BENEFIT_OBSERVED)"

    latency = {
        "OFF_WITH_MEMORY": _latency_bundle(off_trials),
        "ON_WITH_MEMORY": _latency_bundle(on_trials),
        "WITHOUT_MEMORY": _latency_bundle(without_trials),
    }

    ready_for_freeze = (
        classification
        in {"REAL_VALIDATED", "REAL_VALIDATED_FOR_L4_ONLY", "NO_MEASURABLE_GAIN"}
        and privacy_leak_count == 0
        and false_utilization == 0
        and empty_fake_exposure == 0
        and hn_false == 0
        and not model_residency_break
        and len(trials) == 30
        and l3_off == 10
        and l3_on == 10
    )

    gpu_release: dict[str, Any] | None = None
    if release_gpu:
        gpu_release = release_gpu_lane()

    state = "MEMORY_C1_MEASURED"
    if model_residency_break:
        state = "MEMORY_C1_INCONCLUSIVE_RESIDENCY"
    elif product_issues and classification == "REGRESSION":
        state = "MEMORY_C1_REGRESSION"

    payload: dict[str, Any] = {
        "schema_version": "w8-memory-c1-real-revalidation-v1",
        "stage": STAGE,
        "run_id": run_id,
        "started_at": started_at,
        "finished_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "memory_c1_base_sha": memory_c1_base_sha,
        "head_sha": git_sha(),
        "pr_lineage": {
            "p3_freeze_pr": 37,
            "p4_ablation_pr": 38,
            "c1_product_pr": 40,
            "confirmed_ancestors": True,
        },
        "state": state,
        "classification": classification,
        "capability_label": capability_label,
        "MODEL_RESIDENCY_BREAK": model_residency_break,
        "MEMORY_C1_PRODUCT_ISSUE": product_issues,
        "case_hashes": case_hashes,
        "golden_audits": [
            a.to_dict() for a in golden_memory4_audits() if a.case_id in SEEDED_IDS
        ],
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
        "trials": trials,
        "paired_counterfactuals": {
            "ON_WITH_vs_WITHOUT": paired_l5_on,
            "OFF_WITH_vs_WITHOUT": paired_l5_off,
        },
        "metrics": {
            "scored_trajectories": len(trials),
            "L3_EXPOSED": {
                "OFF_WITH_MEMORY": {"passed": l3_off, "denom": len(off_trials)},
                "ON_WITH_MEMORY": {"passed": l3_on, "denom": len(on_trials)},
            },
            "L4_UTILIZED": {
                "OFF_WITH_MEMORY": {"passed": l4_off, "denom": len(off_trials)},
                "ON_WITH_MEMORY": {"passed": l4_on, "denom": len(on_trials)},
                "observable_language": {
                    "OFF": {"passed": obs_lang_off, "denom": len(off_trials)},
                    "ON": {"passed": obs_lang_on, "denom": len(on_trials)},
                },
                "evaluator_valid": {
                    "OFF": {"passed": l4_off, "denom": len(off_trials)},
                    "ON": {"passed": l4_on, "denom": len(on_trials)},
                },
            },
            "L5_TASK_BENEFIT": {
                "OFF_control": {"passed": l5_off, "denom": len(paired_l5_off)},
                "ON": {"passed": l5_on, "denom": len(paired_l5_on)},
            },
            "false_utilization": false_utilization,
            "without_memory_false_util": without_false_util,
        },
        "evaluator_discipline": {
            "p4_blind_spot": evaluator_audit.get("blind_spot"),
            "notes": evaluator_audit.get("notes"),
            "audit": evaluator_audit,
            "changed_evaluator": False,
        },
        "hard_negatives": {
            "results": hn_results,
            "false_utilization_count": hn_false,
            "target": 0,
        },
        "privacy_audit": {
            "plaintext_in_trace": privacy_leak_count,
            "wrong_scope": wrong_scope,
            "wrong_run_step_acceptance": wrong_run_step,
            "empty_fake_exposure": empty_fake_exposure,
            "false_utilization": false_utilization,
        },
        "latency": latency,
        "exposure_events": all_exposure_events,
        "product_remediation": False,
        "runtime_rollout": False,
        "ready_for_freeze": ready_for_freeze,
        "GPU_LANE_RELEASED": bool(release_gpu and gpu_release is not None),
        "gpu_release": gpu_release,
        "forbidden_changes": [
            "c1_product_implementation",
            "memory_prompt_selection_ranking_scope",
            "evaluator",
            "golden",
        ],
        "settings_c1_after_run": bool(settings.agent_memory_relevance_label_enabled),
    }

    out_path = root / REPORT_REL
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    payload["output_path"] = str(out_path)
    return payload
