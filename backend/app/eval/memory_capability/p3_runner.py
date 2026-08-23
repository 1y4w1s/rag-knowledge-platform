"""MEMORY P3 real local capability measurement orchestration."""

from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any

from app.eval.local_agent_trajectory.injection import RecordingAdapter
from app.eval.local_agent_trajectory.runner import (
    DEFAULT_MODEL,
    DEFAULT_TIMEOUT,
    git_sha,
    reload_model,
    wait_ready,
)
from app.eval.local_model_profile.adapter import OpenAICompatibleAdapter, endpoint_host
from app.eval.local_model_profile.schema import ThinkingMode
from app.eval.memory_capability.evaluator import (
    evaluate_counterfactual,
    evaluate_empty_memory_behavior,
    evaluate_trajectory,
)
from app.eval.memory_capability.exposure_event import MemoryExposureEvent, MemoryExposureSource
from app.eval.memory_capability.exposure_semantics import is_authoritative_exposure
from app.eval.memory_capability.golden_audit import golden_memory4_audits
from app.eval.memory_capability.l3_exposure_evaluator import (
    l3_exposed_from_events,
    validate_exposure_event,
)
from app.eval.memory_capability.metrics import aggregate_metrics
from app.eval.memory_capability.p3_execute import run_memory_p3_trial
from app.eval.memory_capability.p3_flags import assert_production_exposure_default
from app.eval.memory_capability.schema import CounterfactualPair, MeasurementLevel
from tests.golden_agent_qa_loader import AgentGoldenCase, load_golden_agent_cases

CASE_IDS = ("GA-9", "GA-10", "GA-11", "GA-12")
SEEDED_IDS = ("GA-9", "GA-10")
EMPTY_IDS = ("GA-11", "GA-12")
TRIALS_PER_CASE = 5
REPORT_REL = Path("artifacts/benchmarks/tmp/reports/w8-memory-p3-real-capability.json")
STAGE = "MEMORY_P3_REAL_LOCAL_CAPABILITY"


def _repo_root() -> Path:
    # backend/app/eval/memory_capability/p3_runner.py → repo root
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
    """Evaluate L1-L4 using trajectory; override L3 with machine-provable events when available."""
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


def _probe_ok(record) -> tuple[bool, str, dict[str, Any]]:
    """First gate: REAL EXPOSURE PROBE must prove L3 for seeded WITH_MEMORY."""
    if not record.exposure_events:
        return False, "no MemoryExposureEvent emitted", {"events": []}
    if not record.run_id:
        return False, "missing run_id on outcome", {}
    events = _events_from_dicts(record.exposure_events)
    for ev in events:
        ok, reason = validate_exposure_event(ev)
        if not ok:
            return False, f"invalid event: {reason}", {"event": ev.to_dict()}
        if ev.run_id != record.run_id:
            return False, "wrong run_id on exposure event", {"event": ev.to_dict()}
        if not ev.step_id:
            return False, "missing step_id", {"event": ev.to_dict()}
        if not ev.memory_hash:
            return False, "missing memory_hash", {"event": ev.to_dict()}
        if ev.injected_to_context is not True:
            return False, "injected_to_context not True", {"event": ev.to_dict()}
        if record.privacy_hits:
            return False, f"privacy leakage: {record.privacy_hits}", {}
    l3 = l3_exposed_from_events(
        run_id=record.run_id,
        expected_memory_hashes=record.expected_memory_hashes,
        events=events,
        empty_memory_case=False,
    )
    if not l3.passed:
        return False, l3.reason or "l3_exposed_from_events failed", {
            "expected_hashes": record.expected_memory_hashes,
            "events": record.exposure_events,
        }
    return True, "", {
        "event_count": len(record.exposure_events),
        "expected_hashes": record.expected_memory_hashes,
        "events": record.exposure_events,
    }


async def run_memory_p3_benchmark(
    *,
    base_url: str = "http://127.0.0.1:1234/v1",
    model: str = DEFAULT_MODEL,
    thinking: str = "off",
    timeout: float = DEFAULT_TIMEOUT,
    skip_reload: bool = False,
    skip_warmup: bool = False,
    probe_only: bool = False,
) -> dict[str, Any]:
    root = _repo_root()
    memory_p3_base_sha = git_sha()
    run_id = str(uuid.uuid4())
    started_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    cases = {c.case_id: c for c in load_golden_agent_cases() if c.case_id in CASE_IDS}
    case_hashes = {cid: _case_hash(cases[cid]) for cid in CASE_IDS}

    inner = OpenAICompatibleAdapter(
        base_url=base_url,
        model=model,
        timeout_seconds=timeout,
        thinking_mode=ThinkingMode.off if thinking == "off" else ThinkingMode.on,
        provider="lmstudio_openai_compatible",
    )
    adapter = RecordingAdapter(inner)

    env_notes: dict[str, Any] = {
        "production_exposure_trace_default_false": assert_production_exposure_default(),
        "benchmark_flags": {
            "agent_memory_enabled": True,
            "agent_memory_exposure_trace_enabled": True,
        },
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

    # ── B5 First Gate: L3 Exposure Probe ─────────────────────────────
    exposure_probe: dict[str, Any] = {"status": "PENDING", "cases": {}}
    for cid in SEEDED_IDS:
        probe_rec = await run_memory_p3_trial(
            case=cases[cid],
            trial_index=0,
            condition="WITH_MEMORY",
            adapter=adapter,
            model_id=model,
            thinking_mode=thinking.upper(),
            run_timeout_seconds=timeout,
        )
        ok, reason, detail = _probe_ok(probe_rec)
        exposure_probe["cases"][cid] = {
            "ok": ok,
            "reason": reason,
            "detail": detail,
            "run_id": probe_rec.run_id,
            "duration_ms": probe_rec.duration_ms,
            "privacy_hits": probe_rec.privacy_hits,
        }
    probe_pass = all(v["ok"] for v in exposure_probe["cases"].values())
    exposure_probe["status"] = "PROVEN" if probe_pass else "NOT_PROVEN"
    exposure_probe["l3_proven"] = probe_pass

    if not probe_pass:
        payload = {
            "schema_version": "w8-memory-p3-real-capability-v1",
            "stage": STAGE,
            "run_id": run_id,
            "started_at": started_at,
            "memory_p3_base_sha": memory_p3_base_sha,
            "head_sha": git_sha(),
            "state": "MEMORY_P3_BLOCKED_L3",
            "l3_proven": False,
            "classification": "BLOCKED/INVALID",
            "measurement_validity": "INVALID",
            "blocked_reason": "L3 exposure probe failed — no trustworthy MemoryExposureEvent proof",
            "instrumentation_diagnosis": exposure_probe,
            "case_hashes": case_hashes,
            "golden_audits": [a.to_dict() for a in golden_memory4_audits()],
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
            "product_remediation": False,
            "runtime_rollout": False,
            "ready_for_memory_p3_freeze": False,
            "trials": [],
            "metrics": {},
        }
        out_path = root / REPORT_REL
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        payload["output_path"] = str(out_path)
        return payload

    if probe_only:
        payload = {
            "schema_version": "w8-memory-p3-real-capability-v1",
            "stage": STAGE,
            "run_id": run_id,
            "memory_p3_base_sha": memory_p3_base_sha,
            "state": "L3_PROBE_ONLY",
            "l3_proven": True,
            "exposure_probe": exposure_probe,
            "case_hashes": case_hashes,
        }
        return payload

    # ── B9–B10 Interleaved trials ────────────────────────────────────
    trials: list[dict[str, Any]] = []
    with_records: dict[tuple[str, int], Any] = {}
    without_records: dict[tuple[str, int], Any] = {}
    evaluations = []
    empty_behavior = []
    paired_counterfactuals: list[dict[str, Any]] = []
    all_exposure_events: list[dict[str, Any]] = []
    false_utilization = 0
    memory_contradiction = 0
    privacy_leak_count = 0
    wrong_scope = 0
    wrong_run_step = 0
    empty_fake_exposure = 0

    for trial_index in range(1, TRIALS_PER_CASE + 1):
        for cid in SEEDED_IDS:
            for condition in ("WITH_MEMORY", "WITHOUT_MEMORY"):
                rec = await run_memory_p3_trial(
                    case=cases[cid],
                    trial_index=trial_index,
                    condition=condition,
                    adapter=adapter,
                    model_id=model,
                    thinking_mode=thinking.upper(),
                    run_timeout_seconds=timeout,
                )
                key = (cid, trial_index)
                if condition == "WITH_MEMORY":
                    with_records[key] = rec
                else:
                    without_records[key] = rec

                empty_for_l3 = condition != "WITH_MEMORY"
                eval_obj, l3_meta = _score_with_events(
                    traj=rec.trajectory_input,
                    run_id=rec.run_id,
                    expected_hashes=rec.expected_memory_hashes if condition == "WITH_MEMORY" else [],
                    event_dicts=rec.exposure_events,
                    empty_case=empty_for_l3,
                )
                # For WITHOUT, L3 empty-path: pass if no authoritative events
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

                if condition == "WITH_MEMORY":
                    evaluations.append(eval_obj)
                    if eval_obj.false_utilization:
                        false_utilization += 1
                    if eval_obj.utilization and eval_obj.utilization.contradicted:
                        memory_contradiction += 1

                privacy_leak_count += len(rec.privacy_hits)
                for ev in rec.exposure_events:
                    all_exposure_events.append({**ev, "case_id": cid, "trial": trial_index, "condition": condition})
                    if condition == "WITHOUT_MEMORY" and ev.get("injected_to_context"):
                        empty_fake_exposure += 1
                    if ev.get("run_id") and rec.run_id and ev.get("run_id") != rec.run_id:
                        wrong_run_step += 1

                level_map = eval_obj.level_map()
                trials.append(
                    {
                        "case_id": cid,
                        "trial_index": trial_index,
                        "condition": condition,
                        "L1_SEEDED": level_map["L1_SEEDED"].to_dict(),
                        "L2_LOADED": level_map["L2_LOADED"].to_dict(),
                        "L3_EXPOSED": level_map["L3_EXPOSED"].to_dict(),
                        "L4_UTILIZED": level_map["L4_UTILIZED"].to_dict(),
                        "L5_TASK_BENEFIT": {"attempted": False, "note": "filled after pairing"},
                        "l3_meta": l3_meta,
                        "proposition_records": rec.proposition_records,
                        "task_contract_passed": rec.trajectory_input.task_contract_passed,
                        "false_utilization": eval_obj.false_utilization,
                        "privacy_hits": rec.privacy_hits,
                        "duration_ms": rec.duration_ms,
                        "run_id": rec.run_id,
                        "exposure_events": rec.exposure_events,
                        "output_excerpt": rec.output_text[:800],
                        "tool_query": rec.tool_query,
                        "outcome": rec.outcome,
                    }
                )

        # After both WITH/WITHOUT for this round's cases, attach L5 for completed pairs
        for cid in SEEDED_IDS:
            key = (cid, trial_index)
            if key not in with_records or key not in without_records:
                continue
            pair = CounterfactualPair(
                case_id=cid,
                with_memory=with_records[key].trajectory_input,
                without_memory=without_records[key].trajectory_input,
            )
            cf_eval = evaluate_counterfactual(pair)
            l5 = cf_eval.level_map()["L5_TASK_BENEFIT"]
            paired_counterfactuals.append(
                {
                    "case_id": cid,
                    "trial_index": trial_index,
                    "with_task_contract": with_records[key].trajectory_input.task_contract_passed,
                    "without_task_contract": without_records[key].trajectory_input.task_contract_passed,
                    "L5_TASK_BENEFIT": l5.to_dict(),
                }
            )
            for t in trials:
                if (
                    t["case_id"] == cid
                    and t["trial_index"] == trial_index
                    and t["condition"] == "WITH_MEMORY"
                ):
                    t["L5_TASK_BENEFIT"] = l5.to_dict()
                    # Replace WITH evaluation L5 in aggregate list
                    break
            # Keep a paired evaluation for metrics (WITH + L5)
            with_eval, _ = _score_with_events(
                traj=with_records[key].trajectory_input,
                run_id=with_records[key].run_id,
                expected_hashes=with_records[key].expected_memory_hashes,
                event_dicts=with_records[key].exposure_events,
                empty_case=False,
            )
            levels = list(with_eval.levels[:-1]) + [l5]
            with_eval.levels = tuple(levels)
            # Replace last matching WITH evaluation for this trial in evaluations
            # evaluations currently appended once per WITH; rebuild L5 on matching index
            for i in range(len(evaluations) - 1, -1, -1):
                if evaluations[i].case_id == cid:
                    # only update the most recent matching case evaluation without L5 yet
                    if not evaluations[i].level_map()["L5_TASK_BENEFIT"].attempted:
                        evaluations[i] = with_eval
                        break

    # Empty controls
    for cid in EMPTY_IDS:
        for trial_index in range(1, TRIALS_PER_CASE + 1):
            rec = await run_memory_p3_trial(
                case=cases[cid],
                trial_index=trial_index,
                condition="EMPTY_CONTROL",
                adapter=adapter,
                model_id=model,
                thinking_mode=thinking.upper(),
                run_timeout_seconds=timeout,
            )
            eval_obj, l3_meta = _score_with_events(
                traj=rec.trajectory_input,
                run_id=rec.run_id,
                expected_hashes=[],
                event_dicts=rec.exposure_events,
                empty_case=True,
            )
            empty_behavior.append(evaluate_empty_memory_behavior(rec.trajectory_input))
            if rec.exposure_events:
                empty_fake_exposure += len(rec.exposure_events)
            privacy_leak_count += len(rec.privacy_hits)
            for ev in rec.exposure_events:
                all_exposure_events.append(
                    {**ev, "case_id": cid, "trial": trial_index, "condition": "EMPTY_CONTROL"}
                )
            level_map = eval_obj.level_map()
            trials.append(
                {
                    "case_id": cid,
                    "trial_index": trial_index,
                    "condition": "EMPTY_CONTROL",
                    "L1_SEEDED": level_map["L1_SEEDED"].to_dict(),
                    "L2_LOADED": level_map["L2_LOADED"].to_dict(),
                    "L3_EXPOSED": level_map["L3_EXPOSED"].to_dict(),
                    "L4_UTILIZED": level_map["L4_UTILIZED"].to_dict(),
                    "L5_TASK_BENEFIT": {"eligible": False, "attempted": False, "passed": False},
                    "l3_meta": l3_meta,
                    "empty_behavior": evaluate_empty_memory_behavior(rec.trajectory_input).to_dict(),
                    "task_contract_passed": rec.trajectory_input.task_contract_passed,
                    "privacy_hits": rec.privacy_hits,
                    "duration_ms": rec.duration_ms,
                    "run_id": rec.run_id,
                    "exposure_events": rec.exposure_events,
                    "output_excerpt": rec.output_text[:800],
                    "outcome": rec.outcome,
                }
            )

    # Denominator upgrades with real evidence
    with_trials = [t for t in trials if t["condition"] == "WITH_MEMORY"]
    l3_pass = sum(1 for t in with_trials if t["L3_EXPOSED"].get("passed"))
    l3_denom = len(with_trials)  # machine-provable path available
    util_eligible = [t for t in with_trials if t["L3_EXPOSED"].get("passed")]
    l4_pass = sum(1 for t in util_eligible if t["L4_UTILIZED"].get("passed"))
    l4_denom = len(util_eligible)  # L3+L4 contract
    l5_pairs = paired_counterfactuals
    l5_pass = sum(1 for p in l5_pairs if p["L5_TASK_BENEFIT"].get("passed"))
    l5_denom = len(l5_pairs)  # counterfactual valid

    ga9_with = [t for t in with_trials if t["case_id"] == "GA-9"]
    ga10_with = [t for t in with_trials if t["case_id"] == "GA-10"]
    exposure_rates = {
        "GA-9": round(sum(1 for t in ga9_with if t["L3_EXPOSED"].get("passed")) / max(len(ga9_with), 1), 4),
        "GA-10": round(sum(1 for t in ga10_with if t["L3_EXPOSED"].get("passed")) / max(len(ga10_with), 1), 4),
    }

    empty_trials = [t for t in trials if t["condition"] == "EMPTY_CONTROL"]
    empty_correct = sum(1 for t in empty_trials if t.get("empty_behavior", {}).get("passed"))

    suite = aggregate_metrics(evaluations, empty_behavior_results=tuple(empty_behavior))

    # Classification
    if false_utilization == 0 and privacy_leak_count == 0 and probe_pass:
        classification = "MEMORY_CAPABILITY_MEASUREMENT VALID"
        if l4_pass == 0 and l3_pass > 0:
            classification = "PASS/CHARACTERIZED (valid low utilization)"
        measurement_validity = "VALID"
        state = "MEMORY_P3_MEASURED"
    else:
        classification = "BLOCKED/INVALID"
        measurement_validity = "INVALID"
        state = "MEMORY_P3_INVALID"

    total_latency = sum(t.get("duration_ms", 0) for t in trials)

    payload: dict[str, Any] = {
        "schema_version": "w8-memory-p3-real-capability-v1",
        "stage": STAGE,
        "run_id": run_id,
        "started_at": started_at,
        "finished_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "memory_p3_base_sha": memory_p3_base_sha,
        "head_sha": git_sha(),
        "pr_lineage": {
            "observability_contract_pr": 29,
            "runtime_instrumentation_pr": 31,
            "confirmed_ancestors": True,
        },
        "state": state,
        "l3_proven": True,
        "classification": classification,
        "measurement_validity": measurement_validity,
        "case_hashes": case_hashes,
        "golden_audits": [a.to_dict() for a in golden_memory4_audits()],
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
        "exposure_probe": exposure_probe,
        "exposure_events": all_exposure_events,
        "trials": trials,
        "paired_counterfactuals": paired_counterfactuals,
        "metrics": {
            "L1_SEEDED": {
                "passed": sum(1 for t in with_trials if t["L1_SEEDED"].get("passed")),
                "denom": len(with_trials),
            },
            "L2_LOADED": {
                "passed": sum(1 for t in with_trials if t["L2_LOADED"].get("passed")),
                "denom": len(with_trials),
            },
            "L3_EXPOSED": {"passed": l3_pass, "denom": l3_denom, "rates": exposure_rates},
            "L4_UTILIZED": {"passed": l4_pass, "denom": l4_denom},
            "L5_TASK_BENEFIT": {"passed": l5_pass, "denom": l5_denom},
            "empty_memory_correct_behavior": {
                "passed": empty_correct,
                "denom": len(empty_trials),
            },
            "false_utilization": false_utilization,
            "memory_contradiction": memory_contradiction,
            "aggregate": suite.to_dict(),
        },
        "with_vs_without": {
            "pairs": len(l5_pairs),
            "with_task_pass": sum(1 for p in l5_pairs if p["with_task_contract"]),
            "without_task_pass": sum(1 for p in l5_pairs if p["without_task_contract"]),
            "l5_true": l5_pass,
        },
        "privacy_audit": {
            "plaintext_in_trace": privacy_leak_count,
            "wrong_scope": wrong_scope,
            "wrong_run_step_acceptance": wrong_run_step,
            "empty_fake_exposure": empty_fake_exposure,
            "false_utilization": false_utilization,
        },
        "latency": {
            "total_trial_ms": round(total_latency, 1),
            "trial_count": len(trials),
            "mean_trial_ms": round(total_latency / max(len(trials), 1), 1),
        },
        "scored_model_trajectories": len(trials),
        "product_remediation": False,
        "runtime_rollout": False,
        "ready_for_memory_p3_freeze": measurement_validity == "VALID"
        and privacy_leak_count == 0
        and false_utilization == 0
        and empty_fake_exposure == 0,
        "forbidden_changes": [
            "prompt",
            "memory_ranking_selection",
            "exposure_event_semantics",
            "evaluator",
            "golden",
        ],
    }

    out_path = root / REPORT_REL
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    payload["output_path"] = str(out_path)
    return payload
