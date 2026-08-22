"""W8 P0 suite runner: warmup + real run_react_loop cases.

Does not change product defaults. Real LM Studio runs are opt-in CLI.
"""

from __future__ import annotations

import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from uuid import UUID

from app.eval.local_agent_trajectory.cases import CASE_BY_ID, TrajectoryCase, w8_p0_cases
from app.eval.local_agent_trajectory.execute import run_one_case
from app.eval.local_agent_trajectory.injection import RecordingAdapter
from app.eval.local_agent_trajectory.report import default_output_dir, write_json
from app.eval.local_agent_trajectory.schema import (
    SCHEMA_VERSION,
    SuiteSummary,
    TrajectoryResult,
    new_run_id,
    utc_now_iso,
)
from app.eval.local_agent_trajectory.scoring import aggregate_summary
from app.eval.local_model_profile.adapter import OpenAICompatibleAdapter, endpoint_host
from app.eval.local_model_profile.schema import ThinkingMode

WARMUP_N = 3
WARMUP_MESSAGES = [
    {"role": "system", "content": "Reply with exactly: OK"},
    {"role": "user", "content": "ping"},
]
DEFAULT_MODEL = "zai-org/glm-4.6v-flash"
DEFAULT_TIMEOUT = 90.0
ON_SEED_CASES = ("B1", "C1", "D1")


def git_sha() -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=Path(__file__).resolve().parents[4],
            text=True,
            timeout=10,
        )
        return out.strip()
    except (subprocess.SubprocessError, OSError):
        return "unknown"


def run_lms(args: list[str], *, timeout: float = 120.0) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        proc = subprocess.run(
            ["lms", *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
        return {
            "args": args,
            "returncode": proc.returncode,
            "stdout": (proc.stdout or "")[-2000:],
            "stderr": (proc.stderr or "")[-1000:],
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 1),
        }
    except FileNotFoundError:
        return {"args": args, "error": "lms_not_found", "returncode": -1}
    except subprocess.TimeoutExpired:
        return {"args": args, "error": "lms_timeout", "returncode": -1}


def reload_model(model_id: str) -> dict[str, Any]:
    unload = run_lms(["unload", "--all"])
    time.sleep(2.0)
    load = run_lms(["load", model_id, "-y", "-c", "8192"], timeout=600.0)
    return {"unload": unload, "load": load, "at": utc_now_iso()}


def wait_ready(adapter: OpenAICompatibleAdapter, *, max_wait_s: float = 120.0) -> dict[str, Any]:
    import httpx

    url = f"{adapter.base_url}/models"
    started = time.perf_counter()
    last: dict[str, Any] = {}
    while (time.perf_counter() - started) < max_wait_s:
        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.get(url)
            data = resp.json() if resp.status_code == 200 else {}
            ids = [m.get("id") for m in (data.get("data") or []) if isinstance(m, dict)]
            last = {"http_status": resp.status_code, "model_ids": ids}
            if adapter.model in ids:
                return {
                    "ready": True,
                    "wait_ms": round((time.perf_counter() - started) * 1000, 1),
                    **last,
                }
        except Exception as exc:  # noqa: BLE001
            last = {"error": exc.__class__.__name__}
        time.sleep(1.0)
    return {"ready": False, "wait_ms": round((time.perf_counter() - started) * 1000, 1), **last}


def do_warmup(adapter: OpenAICompatibleAdapter) -> list[dict[str, Any]]:
    records = []
    for i in range(1, WARMUP_N + 1):
        result = adapter.chat_completion(WARMUP_MESSAGES, temperature=0.0, max_tokens=32)
        records.append(
            {
                "index": i,
                "timed_out": result.timed_out,
                "latency_ms": round(result.latency_ms, 1),
                "error": result.error,
                "excerpt": (result.content or "")[:40],
            }
        )
    return records


def make_recording_adapter(
    *,
    base_url: str,
    model: str,
    thinking: str,
    timeout: float,
    provider: str,
) -> RecordingAdapter:
    inner = OpenAICompatibleAdapter(
        base_url=base_url,
        model=model,
        api_key="lm-studio",
        timeout_seconds=timeout,
        thinking_mode=ThinkingMode(thinking),
        provider=provider,
    )
    return RecordingAdapter(inner)


def environment_payload(
    *,
    base_url: str,
    model: str,
    provider: str,
    thinking: str,
    timeout: float,
    warmup: list[dict[str, Any]] | None,
    reload_info: dict[str, Any] | None,
    case_count: int,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": utc_now_iso(),
        "git_sha": git_sha(),
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
        "provider": provider,
        "endpoint_host": endpoint_host(base_url),
        "model_id": model,
        "thinking_mode": thinking,
        "timeout_seconds": timeout,
        "warmup_protocol": {
            "n": WARMUP_N,
            "reload": "lms unload --all → lms load -y -c 8192",
            "warmup_applied": warmup is not None,
        },
        "reload": reload_info,
        "warmup": warmup,
        "case_count": case_count,
        "notes": "Research benchmark; product defaults unchanged.",
    }


def pick_on_cases(off_results: list[TrajectoryResult], *, limit: int = 4) -> list[str]:
    ids = list(ON_SEED_CASES)
    fail = next((r.case_id for r in off_results if not r.end_to_end_success), None)
    if fail and fail not in ids:
        ids.append(fail)
    return ids[:limit]


def failure_analysis(results: list[TrajectoryResult]) -> dict[str, Any]:
    counts: dict[str, int] = {}
    examples: dict[str, list[str]] = {}
    for r in results:
        for e in r.failure_class:
            counts[e] = counts.get(e, 0) + 1
            examples.setdefault(e, [])
            if r.case_id not in examples[e]:
                examples[e].append(r.case_id)
    return {"counts": counts, "case_ids_by_class": examples}


def system_vs_model(results: list[TrajectoryResult], summary: SuiteSummary) -> dict[str, Any]:
    return {
        "model_decision_success_rate": round(
            sum(1 for r in results if r.model_decision_success) / len(results), 4
        )
        if results
        else 0.0,
        "system_safety_success_rate": summary.safe_termination_rate,
        "end_to_end_success_rate": summary.end_to_end_success_rate,
        "system_saved_rate": summary.system_saved_rate,
        "unrecovered_model_failure_rate": summary.unrecovered_model_failure_rate,
        "boundary": (
            "SYSTEM absorbs premature finish / invalid decision via StopPolicy "
            "and fail-closed refuse; unrecovered schema/timeout remains the local "
            "rollout blocker."
        ),
    }


async def run_case_set(
    cases: list[TrajectoryCase],
    adapter: RecordingAdapter,
    *,
    model_id: str,
    thinking_mode: str,
    user_id: UUID | None = None,
    timeout_seconds: float = 90.0,
) -> list[TrajectoryResult]:
    results: list[TrajectoryResult] = []
    run_timeout = max(120.0, timeout_seconds * (max(c.max_steps for c in cases) + 2))
    for case in cases:
        print(f"  case {case.case_id} {case.category} …", flush=True)
        result = await run_one_case(
            case,
            adapter,
            model_id=model_id,
            thinking_mode=thinking_mode,
            user_id=user_id,
            run_timeout_seconds=run_timeout,
        )
        print(
            f"    e2e={result.end_to_end_success} safe={result.safe_termination} "
            f"saved={result.system_saved} terminal={result.terminal_action}/"
            f"{result.terminal_reason} steps={result.steps_used}",
            flush=True,
        )
        results.append(result)
    return results


async def run_benchmark(
    *,
    base_url: str,
    model: str,
    thinking: str = "off",
    timeout: float = DEFAULT_TIMEOUT,
    provider: str = "lmstudio_openai_compatible",
    output_dir: str | Path | None = None,
    skip_warmup: bool = False,
    skip_reload: bool = False,
    with_on_diagnostic: bool = True,
    user_id: UUID | None = None,
) -> dict[str, Any]:
    out = Path(output_dir) if output_dir else default_output_dir()
    cases = list(w8_p0_cases())
    run_id = new_run_id()
    reload_info = None
    warmup = None
    if not skip_reload:
        print("reload model …", flush=True)
        reload_info = reload_model(model)
    adapter = make_recording_adapter(
        base_url=base_url,
        model=model,
        thinking=thinking,
        timeout=timeout,
        provider=provider,
    )
    if not skip_warmup:
        ready = wait_ready(adapter.inner)
        print(f"endpoint ready={ready.get('ready')}", flush=True)
        print(f"warmup x{WARMUP_N} thinking={thinking}", flush=True)
        warmup = do_warmup(adapter.inner)

    env = environment_payload(
        base_url=base_url,
        model=model,
        provider=provider,
        thinking=thinking,
        timeout=timeout,
        warmup=warmup,
        reload_info=reload_info,
        case_count=len(cases),
    )
    write_json(out / "w8-p0-environment.json", env)
    write_json(out / "w8-p0-case-set.json", {"run_id": run_id, "cases": [c.to_dict() for c in cases]})

    print(f"=== PRIMARY thinking={thinking} cases={len(cases)} ===", flush=True)
    off_results = await run_case_set(
        cases,
        adapter,
        model_id=model,
        thinking_mode=thinking,
        user_id=user_id,
        timeout_seconds=timeout,
    )
    off_summary = aggregate_summary(off_results)
    write_json(
        out / "w8-p0-thinking-off-trajectories.json",
        {"run_id": run_id, "thinking_mode": thinking, "trajectories": [r.to_dict() for r in off_results]},
    )
    write_json(out / "w8-p0-thinking-off-summary.json", off_summary.to_dict())
    write_json(out / "w8-p0-failure-analysis.json", failure_analysis(off_results))
    write_json(out / "w8-p0-system-vs-model.json", system_vs_model(off_results, off_summary))

    on_payload: dict[str, Any] | None = None
    if with_on_diagnostic and thinking == "off":
        on_ids = pick_on_cases(off_results)
        on_cases = [CASE_BY_ID[i] for i in on_ids if i in CASE_BY_ID]
        print(f"=== ON diagnostic reload + warmup cases={on_ids} ===", flush=True)
        on_reload = None if skip_reload else reload_model(model)
        on_adapter = make_recording_adapter(
            base_url=base_url,
            model=model,
            thinking="on",
            timeout=timeout,
            provider=provider,
        )
        on_warmup = None
        if not skip_warmup:
            wait_ready(on_adapter.inner)
            on_warmup = do_warmup(on_adapter.inner)
        on_results = await run_case_set(
            on_cases,
            on_adapter,
            model_id=model,
            thinking_mode="on",
            user_id=user_id,
            timeout_seconds=timeout,
        )
        on_payload = {
            "run_id": run_id,
            "case_ids": on_ids,
            "reload": on_reload,
            "warmup": on_warmup,
            "trajectories": [r.to_dict() for r in on_results],
            "comparison": _compare_off_on(off_results, on_results),
        }
        write_json(out / "w8-p0-thinking-on-diagnostic.json", on_payload)

    return {
        "run_id": run_id,
        "output_dir": str(out),
        "off_summary": off_summary.to_dict(),
        "on_diagnostic": on_payload,
    }


def _compare_off_on(
    off: list[TrajectoryResult], on: list[TrajectoryResult]
) -> dict[str, Any]:
    off_by = {r.case_id: r for r in off}
    rows = []
    for r in on:
        o = off_by.get(r.case_id)
        if o is None:
            continue
        rows.append(
            {
                "case_id": r.case_id,
                "off_e2e": o.end_to_end_success,
                "on_e2e": r.end_to_end_success,
                "off_valid_rate": _step_valid(o),
                "on_valid_rate": _step_valid(r),
                "off_schema_fail": _has(o, "MODEL_SCHEMA_FAILURE")
                or _has(o, "MODEL_MALFORMED_JSON"),
                "on_schema_fail": _has(r, "MODEL_SCHEMA_FAILURE")
                or _has(r, "MODEL_MALFORMED_JSON"),
                "off_steps": o.steps_used,
                "on_steps": r.steps_used,
                "off_duration_ms": o.duration_ms,
                "on_duration_ms": r.duration_ms,
            }
        )
    e2e_gain = sum(1 for x in rows if x["on_e2e"] and not x["off_e2e"])
    e2e_loss = sum(1 for x in rows if x["off_e2e"] and not x["on_e2e"])
    if e2e_gain > e2e_loss and e2e_gain >= 2:
        label = "ON_HELPFUL"
    elif e2e_loss > e2e_gain and e2e_loss >= 2:
        label = "ON_NOT_HELPFUL"
    else:
        label = "INCONCLUSIVE"
    return {"label": label, "rows": rows}


def _step_valid(r: TrajectoryResult) -> float:
    if not r.steps:
        return 0.0
    return round(sum(1 for s in r.steps if s.decision_valid) / len(r.steps), 4)


def _has(r: TrajectoryResult, name: str) -> bool:
    return name in r.failure_class
