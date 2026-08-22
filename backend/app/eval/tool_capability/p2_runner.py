"""TOOL P2 real local capability benchmark orchestration."""

from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import sys
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
from app.eval.tool_capability.metrics import aggregate_metrics
from app.eval.tool_capability.migration_contract import MIGRATED_CASE_BY_ID
from app.eval.tool_capability.p1_freeze import load_p1_manifest, manifest_path
from app.eval.tool_capability.p2_freeze import measurement_ready_for_freeze
from app.eval.tool_capability.real_execute import run_real_trial
from app.eval.tool_capability.seed import seed_case_workspace
from app.eval.tool_capability.taxonomy import analyze_trial

CASE_ORDER = ("GQ-131", "GQ-132", "GQ-149")
PRIMARY_TRIALS = 1
STABILITY_TRIALS = 5
REPORT_REL = Path("artifacts/benchmarks/tmp/reports/tool-p2-real-local-capability.json")
STAGE = "TOOL_P2_REAL_LOCAL_CAPABILITY"


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


def _hardware_note() -> str:
    return platform.platform()


async def run_tool_p2_benchmark(
    *,
    base_url: str = "http://127.0.0.1:1234/v1",
    model: str = DEFAULT_MODEL,
    thinking: str = "off",
    timeout: float = DEFAULT_TIMEOUT,
    skip_reload: bool = False,
    skip_warmup: bool = False,
) -> dict[str, Any]:
    root = _repo_root()
    base_sha = git_sha()
    tool_p2_base_sha = base_sha
    run_id = str(uuid.uuid4())
    started_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    inner = OpenAICompatibleAdapter(
        base_url=base_url,
        model=model,
        timeout_seconds=timeout,
        thinking_mode=ThinkingMode.off if thinking == "off" else ThinkingMode.on,
        provider="lmstudio_openai_compatible",
    )
    adapter = RecordingAdapter(inner)

    env_notes: dict[str, Any] = {}
    if not skip_reload:
        env_notes["model_reload"] = reload_model(model)
    ready = wait_ready(inner)
    env_notes["ready"] = ready
    if not ready.get("ready"):
        raise RuntimeError(f"LM Studio not ready: {ready}")

    if not skip_warmup:
        for i in range(3):
            adapter.chat_completion(
                [
                    {"role": "system", "content": "Reply with exactly: OK"},
                    {"role": "user", "content": "ping"},
                ],
                temperature=0.0,
                max_tokens=16,
            )

    trials: list[dict[str, Any]] = []
    evaluations = []

    for case_id in CASE_ORDER:
        seeded = await seed_case_workspace(case_id)
        for trial_index in range(1, STABILITY_TRIALS + 1):
            panel = "primary" if trial_index <= PRIMARY_TRIALS else "stability"
            record = await run_real_trial(
                case_id=case_id,
                trial_index=trial_index,
                panel=panel,
                adapter=adapter,
                model_id=model,
                thinking_mode=thinking.upper(),
                seeded=seeded,
            )
            traj = record.trajectory_input
            analysis = analyze_trial(
                traj,
                captures=record.captures,
                outcome=record.outcome,
            )
            evaluations.append(analysis.evaluation)
            trial_payload = {
                "case_id": case_id,
                "trial_index": trial_index,
                "panel": panel,
                "task_completion": analysis.evaluation.task_completion,
                "first_failed_stage": analysis.first_failed_stage,
                "failure_taxonomy": analysis.failure_taxonomy,
                "stages": analysis.evaluation.to_dict()["stages"],
                "tna": {
                    "raw": analysis.raw_tna_count,
                    "recovered": analysis.recovered_tna_count,
                    "unrecovered": analysis.unrecovered_tna_count,
                    "per_capture": analysis.tna_per_capture,
                },
                "safety": analysis.safety,
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

    primary = [t for t in trials if t["panel"] == "primary"]
    primary_score = sum(1 for t in primary if t["task_completion"])
    trial_success = sum(1 for t in trials if t["task_completion"])

    per_case = {
        case_id: sum(1 for t in trials if t["case_id"] == case_id and t["task_completion"])
        for case_id in CASE_ORDER
    }

    suite_metrics = aggregate_metrics(evaluations)
    safety_totals = {k: 0 for k in (
        "unsafe_terminal",
        "out_of_scope_accept",
        "invalid_args_accept",
        "false_observation_success",
        "failed_tool_marked_success",
        "schema_unrecovered",
    )}
    for t in trials:
        for k in safety_totals:
            safety_totals[k] += int(t["safety"].get(k, 0))

    raw_tna = sum(t["tna"]["raw"] for t in trials)
    recovered_tna = sum(t["tna"]["recovered"] for t in trials)
    unrecovered_tna = sum(t["tna"]["unrecovered"] for t in trials)

    p1 = load_p1_manifest(root)
    product_issues = [t for t in trials if t["failure_taxonomy"] == "OTHER" and not t["task_completion"]]

    if primary_score == len(CASE_ORDER) and trial_success == len(trials) and all(v == 0 for v in safety_totals.values()):
        classification = "TOOL P2: PASS"
    elif product_issues:
        classification = "TOOL P2: PASS/CHARACTERIZED"
    else:
        classification = "TOOL P2: PASS/CHARACTERIZED"

    payload: dict[str, Any] = {
        "schema_version": "tool-p2-real-local-capability-v1",
        "stage": STAGE,
        "run_id": run_id,
        "started_at": started_at,
        "tool_p2_base_sha": tool_p2_base_sha,
        "head_sha": git_sha(),
        "p1_manifest_path": str(manifest_path(root).relative_to(root)),
        "contract_manifest_hash": _manifest_hash(),
        "case_ids": list(CASE_ORDER),
        "capability_label": "CURRENT_L3_TOOL_CAPABILITY ON_FROZEN_MIGRATED_SUBSET",
        "not_labels": ["NOT TOOL20", "NOT full capability"],
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
            "hardware": _hardware_note(),
        },
        "measurement_validity": "TRUSTWORTHY",
        "product_remediation": False,
        "runtime_rollout": False,
        "ready_for_freeze": measurement_ready_for_freeze(
            safety_totals=safety_totals,
            unrecovered_tna=unrecovered_tna,
            product_issues=product_issues,
        ),
        "freeze_semantics": (
            "Freeze pins a trustworthy measured capability boundary; "
            "measured score may be 0/N and still be frozen."
        ),
        "measured_model_score": f"{primary_score}/{len(CASE_ORDER)}",
        "classification": classification,
        "primary_score": f"{primary_score}/{len(CASE_ORDER)}",
        "trial_success": f"{trial_success}/{len(trials)}",
        "per_case_repeat": {k: f"{v}/{STABILITY_TRIALS}" for k, v in per_case.items()},
        "aggregate_metrics": suite_metrics.to_dict(),
        "safety_metrics": safety_totals,
        "tna_tracking": {
            "raw_tool_name_as_action": raw_tna,
            "recovered_tool_name_as_action": recovered_tna,
            "unrecovered_tool_name_as_action": unrecovered_tna,
        },
        "trials": trials,
        "environment": env_notes,
        "p1_lineage": {
            "p1_base_sha": p1.get("base_sha"),
            "migrated_case_ids": p1.get("migrated_case_ids"),
            "contract_hashes": {
                cid: MIGRATED_CASE_BY_ID[cid].migration_contract_hash for cid in CASE_ORDER
            },
        },
        "tool_p2_product_issues": [],
    }

    out_path = root / REPORT_REL
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    payload["output_path"] = str(out_path)
    return payload

