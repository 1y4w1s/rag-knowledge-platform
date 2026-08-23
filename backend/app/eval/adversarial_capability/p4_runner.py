"""ADVERSARIAL P4 real local agent capability measurement."""

from __future__ import annotations

from app.eval.adversarial_capability import p4_local_env  # noqa: F401


import asyncio
import json
import tempfile
from pathlib import Path
from typing import Any

from app.eval.adversarial_capability.capability_cases import CAPABILITY_CASE_BY_ID
from app.eval.adversarial_capability.p2_design import (
    MODEL_CONFIG,
    PRIMARY_CAPABILITY_CASE_IDS,
)

from app.eval.adversarial_capability.p4_execute import _ensure_user, run_adv_p4_trial
from app.eval.local_agent_trajectory.injection import RecordingAdapter
from app.eval.local_agent_trajectory.runner import (
    WARMUP_MESSAGES,
    git_sha,
    reload_model,
    wait_ready,
)
from app.eval.local_model_profile.adapter import OpenAICompatibleAdapter
from app.eval.local_model_profile.schema import ThinkingMode

STAGE = "ADVERSARIAL_P4_REAL_LOCAL_CAPABILITY"
SCHEMA_VERSION = "w8-adversarial-p4-real-local-v1"
REPORT_REL = Path(
    "tests/fixtures/l4_adversarial_capability/w8-adversarial-p4-real-local.json"
)
TRIALS_PER_CASE = 5


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _interleaved_schedule() -> list[tuple[str, int]]:
    out: list[tuple[str, int]] = []
    for trial in range(TRIALS_PER_CASE):
        for cid in PRIMARY_CAPABILITY_CASE_IDS:
            out.append((cid, trial))
    return out


def _warmup(adapter: RecordingAdapter, n: int) -> None:
    for _ in range(n):
        adapter.chat_completion(messages=WARMUP_MESSAGES, temperature=0, max_tokens=8)


def _aggregate(trajectories: list[dict[str, Any]]) -> dict[str, Any]:
    primary: dict[str, bool] = {cid: False for cid in PRIMARY_CAPABILITY_CASE_IDS}
    per_case_trials: dict[str, list[bool]] = {
        cid: [] for cid in PRIMARY_CAPABILITY_CASE_IDS
    }
    stage_fails: dict[str, int] = {}
    for row in trajectories:
        cid = row["case_id"]
        per_case_trials[cid].append(row["passed"])
        if row["passed"]:
            primary[cid] = True
        ff = row.get("first_failed_stage")
        if ff:
            stage_fails[ff] = stage_fails.get(ff, 0) + 1
    passed_primary = sum(1 for v in primary.values() if v)
    passed_trials = sum(1 for t in trajectories if t["passed"])
    return {
        "CAPABILITY_VALID_DENOMINATOR": 4,
        "primary_pass": f"{passed_primary}/4",
        "trial_pass": f"{passed_trials}/{len(trajectories)}",
        "per_case_any_pass": {cid: primary[cid] for cid in PRIMARY_CAPABILITY_CASE_IDS},
        "per_case_trial_pass": {
            cid: f"{sum(per_case_trials[cid])}/{len(per_case_trials[cid])}"
            for cid in PRIMARY_CAPABILITY_CASE_IDS
        },
        "first_failed_stage_counts": stage_fails,
    }


async def run_adversarial_p4_benchmark(
    *,
    base_url: str = "http://127.0.0.1:1234/v1",
    adv_p4_base_sha: str | None = None,
    skip_reload: bool = False,
    skip_warmup: bool = False,
    probe_only: bool = False,
) -> dict[str, Any]:
    model = MODEL_CONFIG["model"]
    timeout = float(MODEL_CONFIG["timeout_seconds"])
    warmups = int(MODEL_CONFIG["warmup_trials"])
    inner = OpenAICompatibleAdapter(
        base_url=base_url,
        model=model,
        thinking_mode=ThinkingMode.off,
        timeout_seconds=timeout,
    )
    reload_info = {} if skip_reload else reload_model(model)
    ready = wait_ready(inner, max_wait_s=120.0)
    adapter = RecordingAdapter(inner)
    if not skip_warmup:
        _warmup(adapter, warmups)
    user_id = await _ensure_user()
    upload_dir = Path(tempfile.mkdtemp(prefix="adv-p4-"))
    schedule = _interleaved_schedule()
    if probe_only:
        schedule = schedule[:4]
    trajectories: list[dict[str, Any]] = []
    errors: list[str] = []
    for cid, trial in schedule:
        case = CAPABILITY_CASE_BY_ID[cid]
        try:
            trajectories.append(
                await run_adv_p4_trial(
                    case,
                    adapter,
                    user_id=user_id,
                    upload_dir=upload_dir,
                    trial_index=trial,
                    timeout=timeout,
                )
            )
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{cid}#{trial}: {exc}")
    metrics = _aggregate(trajectories) if trajectories else {}
    p3_path = (
        _repo_root()
        / "backend/tests/fixtures/l4_adversarial_capability/w8-adversarial-p3-real-retrieval.json"
    )
    p3_ready = False
    if p3_path.is_file():
        p3_ready = (
            json.loads(p3_path.read_text(encoding="utf-8")).get("ready_for_p4") is True
        )
    valid = p3_ready and len(trajectories) == len(schedule) and not errors
    ready_for_p5 = valid and len(schedule) >= 20
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "stage": STAGE,
        "adv_p4_base_sha": adv_p4_base_sha or git_sha(),
        "model_config": MODEL_CONFIG,
        "lms_reload": reload_info,
        "lms_ready": ready,
        "p3_retrieval_config_reused": True,
        "schedule": [{"case_id": c, "trial_index": t} for c, t in schedule],
        "trajectories": trajectories,
        "metrics_c17": metrics,
        "errors": errors,
        "measurement_validity": "VALID"
        if valid
        else ("PARTIAL" if trajectories else "INVALID"),
        "ready_for_p5": ready_for_p5,
        "probe_only": probe_only,
        "product_remediation": False,
    }
    out = _repo_root() / "backend" / REPORT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    payload["output_path"] = str(out)
    return payload


def main() -> int:
    payload = asyncio.run(run_adversarial_p4_benchmark())
    print(
        f"validity={payload['measurement_validity']} ready_for_p5={payload['ready_for_p5']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
