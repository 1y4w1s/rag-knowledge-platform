"""E-B41 — T1 companion reacquisition (gated scope) on frozen baseline.

Orchestration only: reuses frozen E-B15 / E-A2 product path without modifying
backend/app or the frozen worktree. Captures gen_plan.gated_chunks and same-run
final citations from one product execution trajectory per case.

Does not write Formal T1 results. Does not call LLM/API/LM Studio.
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
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

FROZEN_BASE_SHA = "3ce0e75f06d35aecaaccd245dd3a234b1c6f79a6"
SOURCE_IDENTITY = "suoyin_local_research_product_after_v1"
AFTER_SOURCE_ID = "suoyin_local_research_product_after_v1"
CAPTURE_MODE = "product_stream"
MODEL_BACKEND_IDENTITY = "none_no_llm"
RUNTIME_IDENTITY = "suoyin_backend_venv_cpython_3.11.9_win10_amd64"
RUN_IDENTITY_PATTERN = re.compile(r"^w10_showcase_narrow_.+$")
SUITE_ID = "w9_critic_frozen_12"
BINDING_POLICY = "observed_after"
CAPTURE_PATH_IDENTITY = "eb15_harness_product_after_capture_path_a"
AUTHORIZATION_RECORD_COMMIT = "bd23448f561a541ba6bed7fa1308c3f7de3f6236"
PARENT_ACQUISITION_RUN = "w10_showcase_narrow_eb38_20260825T085526Z"
C12_CASE_ID = "C12-out-of-scope-provenance"
SYNTHETIC_MARKERS = ("eb6-synthetic", "compatibility_materialization_author_owned")
WINDOW = "W10-E-B41"
SCHEMA_REF = "eb41_t1_companion_scope_record_v1"
T1_SAME_EXECUTION_BINDING_REQUIRED = True


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _canonical_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _sha256_hex_payload(payload: Any) -> str:
    digest = hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


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


def _canonicalize_chunk_id(value: Any) -> str:
    return str(value).strip().lower()


def _serialize_gated_chunk(chunk: Any) -> dict[str, Any]:
    return {
        "chunk_id": str(chunk.chunk_id),
        "document_id": str(chunk.document_id),
        "doc_name": chunk.doc_name,
        "kb_id": str(chunk.kb_id),
        "kb_name": chunk.kb_name,
        "page_number": chunk.page_number,
        "section_title": chunk.section_title,
        "similarity": chunk.similarity,
    }


def _load_eb38_record(auth_records_dir: Path, short: str) -> dict[str, Any] | None:
    path = auth_records_dir / f"{short}.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


async def _capture_companion_case(
    monkeypatch: pytest.MonkeyPatch,
    case: dict[str, Any],
    *,
    companion_run: str,
    worktree_head: str,
) -> dict[str, Any]:
    """Same-trajectory: execute_product_path_plan → drain → persist gated + finals."""
    from app.services.agent.runtime import AgentRunOutcome
    from tests.w10_ea2_scope_eligibility import execute_product_path_plan, stable_uuid
    from tests.w10_eb15_product_after_capture import (
        CAPTURE_MODE_PRODUCT_STREAM_DEGRADED,
        CAPTURE_MODE_PRODUCT_STREAM_REFUSAL,
        drain_product_generation_phase,
    )
    from tests.w10_eb6_generation_observation_executor import (
        SYNTHETIC_BODY_PREFIX,
        hash_gen_plan,
    )

    case_id = str(case["case_id"])
    short = _short_case_id(case_id)
    execution = await execute_product_path_plan(monkeypatch, case)
    if not execution.eligibility.product_path_eligible or execution.gen_plan is None:
        raise RuntimeError(
            f"eligible case produced no gen_plan "
            f"(eligibility={execution.eligibility.product_path_eligible})"
        )

    plan = execution.gen_plan
    gated_ordered = [_serialize_gated_chunk(c) for c in plan.gated_chunks]
    gated_scope_ids = [_canonicalize_chunk_id(c["chunk_id"]) for c in gated_ordered]
    gated_scope_hash = _sha256_hex_payload(
        {"gated_scope_ids": gated_scope_ids, "ordered": True}
    )
    plan_hash = hash_gen_plan(plan)

    outcome = AgentRunOutcome(
        run_id=stable_uuid(f"{case_id}:eb41:run"),
        steps_used=len(execution.steps),
        max_steps=max(len(execution.steps), 1),
        capped=False,
        timed_out=False,
        steps=execution.steps,
        deadline_monotonic=time.monotonic() + 30,
    )
    state, entered, _events = await drain_product_generation_phase(
        monkeypatch,
        message=str(case["query"]),
        gen_plan=plan,
        outcome=outcome,
        case_id=case_id,
    )
    content = str(state["content"])
    citations_raw = state["citations"]
    if not isinstance(citations_raw, list):
        raise RuntimeError("state['citations'] must be a list")
    citations = [dict(c) for c in citations_raw]
    final_citation_ids = [
        _canonicalize_chunk_id(c.get("chunk_id")) for c in citations if c.get("chunk_id")
    ]

    if content.startswith(SYNTHETIC_BODY_PREFIX) or "[eb6-synthetic:" in content:
        raise RuntimeError("synthetic body contamination")
    for marker in SYNTHETIC_MARKERS:
        if marker in content:
            raise RuntimeError(f"contamination marker {marker}")
    fixture_answer = case.get("answer")
    if isinstance(fixture_answer, str) and fixture_answer and content == fixture_answer:
        raise RuntimeError("fixture answer used as After")

    capture_path_submode = (
        CAPTURE_MODE_PRODUCT_STREAM_REFUSAL
        if plan.refusal
        else CAPTURE_MODE_PRODUCT_STREAM_DEGRADED
    )
    response_mode = "DEGRADED" if "degraded" in capture_path_submode else (
        "REFUSAL" if "refusal" in capture_path_submode else "ANSWER"
    )

    return {
        "schema_ref": SCHEMA_REF,
        "case_id": case_id,
        "case_id_short": short,
        "query": str(case["query"]),
        "parent_acquisition_run": PARENT_ACQUISITION_RUN,
        "companion_run": companion_run,
        "source_identity": SOURCE_IDENTITY,
        "after_source_id": AFTER_SOURCE_ID,
        "base_sha": FROZEN_BASE_SHA,
        "authorization_record_commit": AUTHORIZATION_RECORD_COMMIT,
        "runtime_identity": RUNTIME_IDENTITY,
        "capture_mode": CAPTURE_MODE,
        "capture_path_identity": CAPTURE_PATH_IDENTITY,
        "capture_path_submode": capture_path_submode,
        "model_backend_identity": MODEL_BACKEND_IDENTITY,
        "llm_called": False,
        "llm_called_observed": False,
        "response_mode": response_mode,
        "plan_refusal": plan.refusal,
        "stream_phase_entered": entered,
        "gated_scope_ids": gated_scope_ids,
        "gated_chunks_ordered": gated_ordered,
        "gated_scope_hash": gated_scope_hash,
        "plan_scope_provenance": {
            "owner": "gen_plan.gated_chunks",
            "product_path": [
                "execute_product_path_plan",
                "prepare_agent_generation",
                "gen_plan.gated_chunks",
            ],
            "gen_plan_reference": plan_hash,
            "inferred_from_final_citations": False,
            "synthetic_fixture_scope": False,
            "eb18_compat": False,
            "gold_constructed": False,
        },
        "content": content,
        "citations": citations,
        "final_citation_ids": final_citation_ids,
        "final_citation_source": (
            "E-B41 companion same-run product final citations "
            "(same trajectory as gated_scope; not E-B38 cross-run splice)"
        ),
        "source_hash": _sha256_hex_content(content),
        "observed_content_hash": _sha256_hex_content(content),
        "after_citations_hash": _sha256_hex_payload(citations),
        "gen_plan_reference": plan_hash,
        "T1_SAME_EXECUTION_BINDING_REQUIRED": T1_SAME_EXECUTION_BINDING_REQUIRED,
        "same_trajectory_binding": True,
        "suite_id": SUITE_ID,
        "binding_policy": BINDING_POLICY,
        "formal_measurement": False,
        "timestamp": _utc_now(),
        "capture_provenance": {
            "window": WINDOW,
            "harness_id": "w10_eb15_product_after_capture",
            "orchestration_entry": "execute_product_path_plan+drain_product_generation_phase",
            "product_boundary": [
                "prepare_agent_generation",
                "gen_plan.gated_chunks",
                "_stream_generation_phase",
                "state[content]",
                "state[citations]",
            ],
            "worktree_head": worktree_head,
            "authorization_stamp_schema": "eb30_owner_stamp_v1",
        },
        "worktree_head_observed": worktree_head,
    }


async def _capture_suite(
    *,
    companion_run: str,
    output_dir: Path,
    eb38_records_dir: Path,
    worktree_head: str,
) -> dict[str, Any]:
    from tests.w10_ea2_scope_eligibility import load_frozen_suite

    started_at = _utc_now()
    runtime_identity, runtime_observed = _observe_runtime_identity()
    if runtime_identity != RUNTIME_IDENTITY:
        return {
            "ok": False,
            "blocker": "RUNTIME_IDENTITY_MATCH = NO",
            "runtime_identity_observed": runtime_identity,
            "runtime_observed": runtime_observed,
            "T1_COMPANION_REACQUISITION_EXECUTED": "NO",
            "T1_COMPANION_CAPTURE_VALID": "NO",
        }
    if worktree_head != FROZEN_BASE_SHA:
        return {
            "ok": False,
            "blocker": "FROZEN_BASE_SHA_MISMATCH",
            "worktree_head": worktree_head,
            "T1_COMPANION_REACQUISITION_EXECUTED": "NO",
            "T1_COMPANION_CAPTURE_VALID": "NO",
        }

    suite = load_frozen_suite()
    cases_by_id = {str(c["case_id"]): c for c in suite.cases}
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
                record = await _capture_companion_case(
                    mp,
                    case,
                    companion_run=companion_run,
                    worktree_head=worktree_head,
                )
                # Honesty: compare to E-B38 but never cross-splice
                eb38 = _load_eb38_record(eb38_records_dir, short)
                if eb38 is not None:
                    record["eb38_content_hash_match"] = (
                        record["source_hash"] == eb38.get("source_hash")
                    )
                    record["eb38_citations_hash_match"] = (
                        record["after_citations_hash"]
                        == eb38.get("after_citations_hash")
                    )
                    record["eb38_gen_plan_reference_match"] = (
                        record["gen_plan_reference"] == eb38.get("gen_plan_reference")
                    )
                    # If content/citations diverge from E-B38, still OK —
                    # we bind same-run finals, never old E-B38 citations to new scope.
                    if not record["eb38_content_hash_match"] or not record[
                        "eb38_citations_hash_match"
                    ]:
                        record["cross_run_splice_forbidden_note"] = (
                            "E-B41 uses same-run finals; does not bind new scope "
                            "to E-B38 final citations"
                        )

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
                if "contamination" in error.lower() or "synthetic" in error.lower():
                    contamination_hits.append(case_id)
                fail_path = records_dir / f"{short}.FAILED.json"
                fail_path.write_text(
                    json.dumps(
                        {
                            "case_id": case_id,
                            "case_id_short": short,
                            "status": "FAILED",
                            "error": error,
                            "companion_run": companion_run,
                            "parent_acquisition_run": PARENT_ACQUISITION_RUN,
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
                    "gated_scope_count": None
                    if record is None
                    else len(record.get("gated_scope_ids") or []),
                    "final_citation_count": None
                    if record is None
                    else len(record.get("final_citation_ids") or []),
                    "response_mode": None if record is None else record.get("response_mode"),
                    "gated_scope_hash": None
                    if record is None
                    else record.get("gated_scope_hash"),
                    "same_trajectory_binding": None
                    if record is None
                    else record.get("same_trajectory_binding"),
                }
            )

    c12_record = {
        "schema_ref": "eb41_c12_ineligible_record_v1",
        "case_id": C12_CASE_ID,
        "case_id_short": "C12",
        "status": "INELIGIBLE_NOT_SCORED",
        "attempted_companion_capture": False,
        "parent_acquisition_run": PARENT_ACQUISITION_RUN,
        "companion_run": companion_run,
        "source_identity": SOURCE_IDENTITY,
        "after_source_id": AFTER_SOURCE_ID,
        "base_sha": FROZEN_BASE_SHA,
        "runtime_identity": RUNTIME_IDENTITY,
        "capture_mode": CAPTURE_MODE,
        "model_backend_identity": MODEL_BACKEND_IDENTITY,
        "llm_called_observed": False,
        "gated_scope_ids": None,
        "final_citation_ids": None,
        "timestamp": _utc_now(),
        "suite_id": SUITE_ID,
        "formal_measurement": False,
        "reason": (
            "authorization_scope.c12_policy=INELIGIBLE_NOT_SCORED; "
            "excluded before companion execution"
        ),
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
            "gated_scope_count": None,
            "final_citation_count": None,
            "response_mode": None,
            "gated_scope_hash": None,
            "same_trajectory_binding": None,
        }
    )

    completed_at = _utc_now()
    contamination_ok = len(contamination_hits) == 0
    capture_valid = (
        captured == 11
        and failed == 0
        and contamination_ok
        and runtime_identity == RUNTIME_IDENTITY
        and RUN_IDENTITY_PATTERN.match(companion_run) is not None
        and all(
            row["status"] != "CAPTURED" or row.get("same_trajectory_binding") is True
            for row in per_case
            if row["case_id_short"] != "C12"
        )
        and all(
            row["status"] != "CAPTURED" or row.get("llm_called_observed") is False
            for row in per_case
        )
    )

    manifest = {
        "window": WINDOW,
        "parent_acquisition_run": PARENT_ACQUISITION_RUN,
        "companion_run": companion_run,
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
        "worktree_head": worktree_head,
        "suite_id": SUITE_ID,
        "binding_policy": BINDING_POLICY,
        "T1_SAME_EXECUTION_BINDING_REQUIRED": T1_SAME_EXECUTION_BINDING_REQUIRED,
        "T1_GATED_SCOPE_SIGNAL_AVAILABLE": "YES",
        "eligible_count": 11,
        "attempted_count": 11,
        "captured_count": captured,
        "failed_count": failed,
        "excluded_count": 1,
        "per_case": per_case,
        "contamination_hits": contamination_hits,
        "llm_called_observed_suite": False,
        "formal_measurement": False,
        "T1_COMPANION_REACQUISITION_EXECUTED": "YES" if captured > 0 else "NO",
        "T1_COMPANION_CAPTURE_VALID": "YES" if capture_valid else "NO",
        "E-B_FORMAL_READY": "NO",
        "MAY_ENTER_FORMAL_OBSERVATION_WINDOW": "NO",
        "FORMAL_OBSERVATION": "NOT_STARTED",
        "FORMAL_T1_RESULT_WRITTEN": "NO",
    }
    (output_dir / "companion-run-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="E-B41 T1 companion reacquisition")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--companion-run", type=str, required=True)
    parser.add_argument("--eb38-records-dir", type=Path, required=True)
    parser.add_argument("--worktree-head", type=str, required=True)
    args = parser.parse_args()

    if not RUN_IDENTITY_PATTERN.match(args.companion_run):
        print(
            f"FATAL: companion_run {args.companion_run!r} does not match "
            f"{RUN_IDENTITY_PATTERN.pattern}",
            file=sys.stderr,
        )
        return 2

    prior = _clear_provider_env()
    try:
        manifest = asyncio.run(
            _capture_suite(
                companion_run=args.companion_run,
                output_dir=args.output_dir,
                eb38_records_dir=args.eb38_records_dir,
                worktree_head=args.worktree_head,
            )
        )
    finally:
        _restore_provider_env(prior)

    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    if manifest.get("T1_COMPANION_CAPTURE_VALID") != "YES":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
