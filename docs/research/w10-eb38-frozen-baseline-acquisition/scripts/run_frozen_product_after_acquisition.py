"""E-B38 — Frozen-baseline Product After acquisition driver (orchestration only).

Reuses E-B15 harness `capture_frozen_case_product_after` from the frozen worktree
code tree. Does not modify production/test implementation. Writes acquisition
records to an external artifact directory on the authorization workspace.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import platform
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

# ---------------------------------------------------------------------------
# Frozen authorization constants (must match Owner Stamp / E-B35b)
# ---------------------------------------------------------------------------

FROZEN_BASE_SHA = "3ce0e75f06d35aecaaccd245dd3a234b1c6f79a6"
SOURCE_IDENTITY = "suoyin_local_research_product_after_v1"
AFTER_SOURCE_ID = "suoyin_local_research_product_after_v1"
CAPTURE_MODE = "product_stream"  # freeze enum parent of E-B15 stream submodes
MODEL_BACKEND_IDENTITY = "none_no_llm"
RUNTIME_IDENTITY = "suoyin_backend_venv_cpython_3.11.9_win10_amd64"
RUN_IDENTITY_PATTERN = re.compile(r"^w10_showcase_narrow_.+$")
SUITE_ID = "w9_critic_frozen_12"
BINDING_POLICY = "observed_after"
CAPTURE_PATH_IDENTITY = "eb15_harness_product_after_capture_path_a"
AUTHORIZATION_RECORD_COMMIT = "bd23448f561a541ba6bed7fa1308c3f7de3f6236"
C12_CASE_ID = "C12-out-of-scope-provenance"
SYNTHETIC_MARKERS = ("eb6-synthetic", "compatibility_materialization_author_owned")


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _canonical_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _sha256_hex_content(content: str) -> str:
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def _observe_runtime_identity() -> tuple[str, dict[str, Any]]:
    ver = sys.version_info
    plat = platform.system().lower()
    mach = platform.machine().lower()
    observed = {
        "python_version": f"{ver.major}.{ver.minor}.{ver.micro}",
        "platform_system": platform.system(),
        "platform_machine": platform.machine(),
        "executable": sys.executable,
        "implementation": platform.python_implementation().lower(),
    }
    # Match frozen token: suoyin_backend_venv_cpython_3.11.9_win10_amd64
    win_ok = plat.startswith("win") and ("amd64" in mach or "x86_64" in mach)
    py_ok = (ver.major, ver.minor, ver.micro) == (3, 11, 9)
    venv_ok = ".venv" in Path(sys.executable).as_posix().lower()
    cpy_ok = "cpython" in observed["implementation"]
    identity = (
        "suoyin_backend_venv_cpython_3.11.9_win10_amd64"
        if (win_ok and py_ok and venv_ok and cpy_ok)
        else f"MISMATCH_{observed['python_version']}_{plat}_{mach}"
    )
    return identity, observed


def _short_case_id(case_id: str) -> str:
    return case_id.split("-", 1)[0]


def _clear_provider_env() -> dict[str, str | None]:
    keys = [
        "DEEPSEEK_API_KEY",
        "TONGYI_API_KEY",
        "DASHSCOPE_API_KEY",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "LM_STUDIO_API_KEY",
        "LMSTUDIO_API_KEY",
    ]
    prior: dict[str, str | None] = {}
    for key in keys:
        prior[key] = os.environ.get(key)
        os.environ[key] = ""
    return prior


def _restore_provider_env(prior: dict[str, str | None]) -> None:
    for key, value in prior.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


async def _capture_suite(
    *,
    run_identity: str,
    output_dir: Path,
) -> dict[str, Any]:
    from tests.w10_ea2_scope_eligibility import load_frozen_suite
    from tests.w10_eb15_product_after_capture import capture_frozen_case_product_after
    from tests.w10_eb6_generation_observation_executor import SYNTHETIC_BODY_PREFIX

    started_at = _utc_now()
    runtime_identity, runtime_observed = _observe_runtime_identity()
    if runtime_identity != RUNTIME_IDENTITY:
        return {
            "ok": False,
            "blocker": "RUNTIME_IDENTITY_MATCH = NO",
            "runtime_identity_observed": runtime_identity,
            "runtime_observed": runtime_observed,
            "ACQUISITION_EXECUTED": "NO",
            "PRODUCT_AFTER_CAPTURED": "NO",
            "ACQUISITION_VALID": "NO",
        }

    suite = load_frozen_suite()
    cases_by_id = {str(c["case_id"]): c for c in suite.cases}
    # Keep suite order C01..C11; C12 excluded before execution
    eligible_ids = [
        str(c["case_id"]) for c in suite.cases if str(c["case_id"]) != C12_CASE_ID
    ]

    records_dir = output_dir / "records"
    records_dir.mkdir(parents=True, exist_ok=True)

    per_case: list[dict[str, Any]] = []
    captured = 0
    failed = 0
    contamination_hits: list[str] = []

    with pytest.MonkeyPatch.context() as mp:
        for case_id in eligible_ids:
            case = cases_by_id[case_id]
            short = _short_case_id(case_id)
            ts = _utc_now()
            status = "FAILED"
            error: str | None = None
            record: dict[str, Any] | None = None
            try:
                snap = await capture_frozen_case_product_after(mp, case)
                if not snap.eligibility or snap.after_content is None:
                    raise RuntimeError(
                        "eligible case produced no Product After "
                        f"(eligibility={snap.eligibility}, mode={snap.capture_mode})"
                    )
                if snap.llm_called:
                    raise RuntimeError("llm_called_observed=true violates none_no_llm")
                content = snap.after_content
                if content.startswith(SYNTHETIC_BODY_PREFIX) or "[eb6-synthetic:" in content:
                    contamination_hits.append(case_id)
                    raise RuntimeError("synthetic body contamination")
                for marker in SYNTHETIC_MARKERS:
                    if marker in content:
                        contamination_hits.append(case_id)
                        raise RuntimeError(f"contamination marker {marker}")
                fixture_answer = case.get("answer")
                if isinstance(fixture_answer, str) and fixture_answer and content == fixture_answer:
                    contamination_hits.append(case_id)
                    raise RuntimeError("fixture answer used as After")

                # BP-A content-string codec (UTF-8 sha256 of observed body)
                source_hash = _sha256_hex_content(content)
                observed_content_hash = source_hash
                # Keep harness digest for provenance cross-check (may use canonical-JSON codec)
                harness_content_hash = snap.after_content_hash

                record = {
                    "schema_ref": "eb26_narrow_formal_after_capture_record_v1",
                    "case_id": case_id,
                    "case_id_short": short,
                    "query": str(case["query"]),
                    "source_identity": SOURCE_IDENTITY,
                    "after_source_id": AFTER_SOURCE_ID,
                    "after_source": AFTER_SOURCE_ID,
                    "run_identity": run_identity,
                    "base_sha": FROZEN_BASE_SHA,
                    "authorization_record_commit": AUTHORIZATION_RECORD_COMMIT,
                    "runtime_identity": RUNTIME_IDENTITY,
                    "capture_mode": CAPTURE_MODE,
                    "capture_path_identity": CAPTURE_PATH_IDENTITY,
                    "capture_path_submode": snap.capture_mode,
                    "model_backend_identity": MODEL_BACKEND_IDENTITY,
                    "model_identity": MODEL_BACKEND_IDENTITY,
                    "llm_called": False,
                    "llm_called_observed": False,
                    "generation_config": {
                        "chat_provider_keys": "forced_empty_via_eb15_force_zero_llm",
                        "rag_critic_enabled": False,
                        "agent_l3_critic_retrieval_enabled": False,
                    },
                    "content": content,
                    "citations": list(snap.after_citations or ()),
                    "source_hash": source_hash,
                    "observed_content_hash": observed_content_hash,
                    "harness_after_content_hash": harness_content_hash,
                    "after_citations_hash": snap.after_citations_hash,
                    "input_hash": snap.input_hash,
                    "gen_plan_reference": snap.gen_plan_reference,
                    "timestamp": ts,
                    "suite_id": SUITE_ID,
                    "binding_policy": BINDING_POLICY,
                    "formal_measurement": False,
                    "stream_phase_entered": snap.stream_phase_entered,
                    "plan_refusal": snap.plan_refusal,
                    "capture_provenance": {
                        "harness_id": "w10_eb15_product_after_capture",
                        "harness_entry": "capture_frozen_case_product_after",
                        "product_boundary": [
                            "prepare_agent_generation",
                            "_stream_generation_phase",
                            "state[content]",
                            "state[citations]",
                        ],
                        "worktree_head": FROZEN_BASE_SHA,
                        "authorization_stamp_schema": "eb30_owner_stamp_v1",
                    },
                }
                out_path = records_dir / f"{short}.json"
                out_path.write_text(
                    json.dumps(record, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
                status = "CAPTURED"
                captured += 1
            except Exception as exc:  # noqa: BLE001 — acquisition honesty log
                failed += 1
                status = "FAILED"
                error = f"{type(exc).__name__}: {exc}"
                fail_path = records_dir / f"{short}.FAILED.json"
                fail_path.write_text(
                    json.dumps(
                        {
                            "case_id": case_id,
                            "case_id_short": short,
                            "status": "FAILED",
                            "error": error,
                            "run_identity": run_identity,
                            "base_sha": FROZEN_BASE_SHA,
                            "timestamp": ts,
                        },
                        ensure_ascii=False,
                        indent=2,
                    )
                    + "\n",
                    encoding="utf-8",
                )

            per_case.append(
                {
                    "case_id": case_id,
                    "case_id_short": short,
                    "status": status,
                    "error": error,
                    "llm_called_observed": False if status == "CAPTURED" else None,
                    "capture_path_submode": None
                    if record is None
                    else record.get("capture_path_submode"),
                    "content_len": None
                    if record is None
                    else len(record.get("content") or ""),
                    "citation_count": None
                    if record is None
                    else len(record.get("citations") or []),
                    "source_hash": None if record is None else record.get("source_hash"),
                }
            )

    # C12 excluded before execution
    c12_record = {
        "schema_ref": "eb26_c12_ineligible_record_v1",
        "case_id": C12_CASE_ID,
        "case_id_short": "C12",
        "status": "INELIGIBLE_NOT_SCORED",
        "attempted_acquisition": False,
        "source_identity": SOURCE_IDENTITY,
        "after_source_id": AFTER_SOURCE_ID,
        "run_identity": run_identity,
        "base_sha": FROZEN_BASE_SHA,
        "runtime_identity": RUNTIME_IDENTITY,
        "capture_mode": CAPTURE_MODE,
        "model_backend_identity": MODEL_BACKEND_IDENTITY,
        "llm_called_observed": False,
        "content": None,
        "citations": None,
        "timestamp": _utc_now(),
        "suite_id": SUITE_ID,
        "binding_policy": BINDING_POLICY,
        "formal_measurement": False,
        "reason": "authorization_scope.c12_policy=INELIGIBLE_NOT_SCORED; excluded before execution",
    }
    (records_dir / "C12.INELIGIBLE.json").write_text(
        json.dumps(c12_record, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    per_case.append(
        {
            "case_id": C12_CASE_ID,
            "case_id_short": "C12",
            "status": "INELIGIBLE_NOT_SCORED",
            "error": None,
            "llm_called_observed": False,
            "capture_path_submode": None,
            "content_len": None,
            "citation_count": None,
            "source_hash": None,
        }
    )

    completed_at = _utc_now()
    contamination_ok = len(contamination_hits) == 0
    # Validity = authenticity/provenance of captured After, NOT case success rate.
    acquisition_valid = (
        captured > 0
        and contamination_ok
        and runtime_identity == RUNTIME_IDENTITY
        and RUN_IDENTITY_PATTERN.match(run_identity) is not None
        and all(
            row["status"] != "CAPTURED" or row.get("llm_called_observed") is False
            for row in per_case
        )
    )

    manifest = {
        "window": "W10-E-B38",
        "run_identity": run_identity,
        "started_at": started_at,
        "completed_at": completed_at,
        "base_sha": FROZEN_BASE_SHA,
        "authorization_record_commit": AUTHORIZATION_RECORD_COMMIT,
        "source_identity": SOURCE_IDENTITY,
        "after_source_id": AFTER_SOURCE_ID,
        "capture_mode": CAPTURE_MODE,
        "model_backend_identity": MODEL_BACKEND_IDENTITY,
        "runtime_identity": RUNTIME_IDENTITY,
        "runtime_observed": runtime_observed,
        "suite_id": SUITE_ID,
        "binding_policy": BINDING_POLICY,
        "eligible_count": 11,
        "attempted_count": 11,
        "captured_count": captured,
        "failed_count": failed,
        "excluded_count": 1,
        "per_case": per_case,
        "contamination_hits": contamination_hits,
        "llm_called_observed_suite": False,
        "formal_measurement": False,
        "ACQUISITION_EXECUTED": "YES" if captured > 0 else "NO",
        "PRODUCT_AFTER_CAPTURED": "YES" if captured > 0 else "NO",
        "ACQUISITION_VALID": "YES" if acquisition_valid else "NO",
        "E-B_FORMAL_READY": "NO",
        "MAY_ENTER_FORMAL_OBSERVATION_WINDOW": "NO",
        "FORMAL_OBSERVATION": "NOT_STARTED",
    }
    (output_dir / "acquisition-run-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="E-B38 frozen Product After acquisition")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--run-identity", type=str, required=True)
    args = parser.parse_args()

    if not RUN_IDENTITY_PATTERN.match(args.run_identity):
        print(
            f"FATAL: run_identity {args.run_identity!r} does not match "
            f"{RUN_IDENTITY_PATTERN.pattern}",
            file=sys.stderr,
        )
        return 2

    prior = _clear_provider_env()
    try:
        manifest = asyncio.run(
            _capture_suite(run_identity=args.run_identity, output_dir=args.output_dir)
        )
    finally:
        _restore_provider_env(prior)

    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    if manifest.get("ACQUISITION_VALID") != "YES":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
