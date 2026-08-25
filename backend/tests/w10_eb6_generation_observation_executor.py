"""W10 E-B6 — test-only After-window generation observation executor.

Implements the E-B5-ready zero-LLM isomorphic capture path:

    gen_plan (E-A2 prepare) → author-owned body → align_citations_to_answer
        → state["content"] / state["citations"] snapshot → E-B2 envelope

Capture only. No product runtime edits, no LLM / LM Studio, no formal
measurement claim, no reserved result file write, no P2-R1 unblock.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from app.services.agent.finalize import AgentGenerationPlan
from app.services.rag.citation_align import align_citations_to_answer
from app.services.rag.executor import workspace_chunk_to_citation
from tests.w10_ea2_scope_eligibility import (
    ProductPathExecution,
    execute_product_path_plan,
    load_frozen_suite,
)
from tests.w10_eb2_generation_observation_contract import (
    ALLOWED_CLAIM,
    ARTIFACT_KIND_FORMAL_OBS,
    C12_CASE_ID,
    CLASSIFICATION_INVALID,
    EA5_RESULT_FILENAME,
    ELIGIBILITY_PROTOCOL_ID,
    FROZEN_CASE_COUNT,
    FORBIDDEN_CLAIMS,
    INVALID_EXPECTED,
    OBSERVATION_POINT,
    PARENT_PROTOCOL_ID,
    P2_R1_STATUS_BLOCKED,
    PRODUCT_PATH_ELIGIBLE_EXPECTED,
    PROTOCOL_VERSION,
    RESERVED_RESULT_FILENAME,
    RESERVED_RESULT_PATH,
    RUNNER_ID,
    RUNNER_MODULE,
    STATUS_INELIGIBLE,
    STATUS_NOT_OBSERVED,
    STATUS_OBSERVED_SLOT,
    SUITE_ID,
    GenerationObservationContractError,
    assert_reserved_result_absent,
    validate_reserved_artifact,
)

CAPTURE_MODE_ISOMORPHIC = "zero_llm_isomorphic"
CAPTURE_MODE_INELIGIBLE = "ineligible_no_after"
TARGET_T1 = "T1"
SYNTHETIC_BODY_PREFIX = "[eb6-synthetic:"

# Synthetic / implementation smoke is never a formal observation result.
SMOKE_INVALID_REASON = "OTHER_PROTOCOL_BREAK"


class GenerationObservationExecutorError(ValueError):
    """Raised when the E-B6 executor refuses an illegal capture or write."""


@dataclass(frozen=True, slots=True)
class AfterObservationSnapshot:
    """After-window capture record (before plan ref + after state + hashes)."""

    case_id: str
    eligibility: bool
    classification: str | None
    input_hash: str
    gen_plan_reference: str | None
    before_gen_plan_hash: str | None
    after_content: str | None
    after_content_hash: str | None
    after_citations: tuple[dict[str, Any], ...] | None
    after_citations_hash: str | None
    plan_refusal: bool | None
    refusal_observation_status: str
    grounding_observation_status: str
    capture_mode: str
    llm_called: bool
    state: Mapping[str, Any]

    def to_per_case_observation(self) -> dict[str, Any]:
        scope_result: dict[str, Any] | None
        if not self.eligibility:
            scope_result = None
        else:
            scope_result = {
                "target": TARGET_T1,
                "capture_mode": self.capture_mode,
                "align_applied": self.plan_refusal is False,
                "final_citation_count": (
                    0 if self.after_citations is None else len(self.after_citations)
                ),
                "formal_measurement": False,
            }
        return {
            "case_id": self.case_id,
            "eligibility": self.eligibility,
            "classification": self.classification,
            "input_hash": self.input_hash,
            "gen_plan_reference": self.gen_plan_reference,
            "final_content_observation": self.after_content,
            "final_citations": (
                None if self.after_citations is None else list(self.after_citations)
            ),
            "scope_compliance_result": scope_result,
            "grounding_observation_status": self.grounding_observation_status,
            "refusal_observation_status": self.refusal_observation_status,
        }


def _canonical_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _sha256_hex(payload: Any) -> str:
    digest = hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def hash_case_input(case: Mapping[str, object]) -> str:
    """Stable input hash — query/evidence/scope only; never fixture answer."""
    scope = case.get("scope")
    evidence = case.get("evidence")
    return _sha256_hex(
        {
            "case_id": case.get("case_id"),
            "query": case.get("query"),
            "scope": scope,
            "evidence_ids": [
                item.get("evidence_id")
                for item in (evidence if isinstance(evidence, list) else [])
                if isinstance(item, Mapping)
            ],
        }
    )


def hash_gen_plan(plan: AgentGenerationPlan) -> str:
    return _sha256_hex(
        {
            "refusal": plan.refusal,
            "gated_chunk_ids": [str(chunk.chunk_id) for chunk in plan.gated_chunks],
            "citation_chunk_ids": [
                str(c.get("chunk_id") or c.get("id") or c.get("citation_id") or "")
                for c in plan.citations
            ],
            "external_context_len": len(plan.external_context or ""),
        }
    )


def author_owned_synthetic_content(case_id: str, gated_count: int) -> str:
    """Author-owned isomorphic body. Must not reuse W9 fixture `answer`."""
    if gated_count <= 0:
        return f"{SYNTHETIC_BODY_PREFIX}{case_id}] empty-gate isomorphic body"
    return (
        f"{SYNTHETIC_BODY_PREFIX}{case_id}] isomorphic observation body "
        f"with citation marker [片段1]."
    )


def _assert_not_fixture_answer(content: str, case: Mapping[str, object]) -> None:
    fixture_answer = case.get("answer")
    if isinstance(fixture_answer, str) and fixture_answer and content == fixture_answer:
        raise GenerationObservationExecutorError(
            "forbidden: W9 fixture answer must not be used as After content"
        )


def _empty_state() -> dict[str, Any]:
    return {"content": None, "citations": None}


def _ineligible_snapshot(case: Mapping[str, object]) -> AfterObservationSnapshot:
    case_id = str(case["case_id"])
    return AfterObservationSnapshot(
        case_id=case_id,
        eligibility=False,
        classification=CLASSIFICATION_INVALID,
        input_hash=hash_case_input(case),
        gen_plan_reference=None,
        before_gen_plan_hash=None,
        after_content=None,
        after_content_hash=None,
        after_citations=None,
        after_citations_hash=None,
        plan_refusal=None,
        refusal_observation_status=STATUS_INELIGIBLE,
        grounding_observation_status=STATUS_INELIGIBLE,
        capture_mode=CAPTURE_MODE_INELIGIBLE,
        llm_called=False,
        state=_empty_state(),
    )


def capture_isomorphic_after(
    execution: ProductPathExecution,
    case: Mapping[str, object],
) -> AfterObservationSnapshot:
    """gen_plan → generation observation path (isomorphic) → state content/citations."""
    if not execution.eligibility.product_path_eligible or execution.gen_plan is None:
        return _ineligible_snapshot(case)

    plan = execution.gen_plan
    plan_hash = hash_gen_plan(plan)
    state: dict[str, Any] = {"content": None, "citations": None}

    if plan.refusal:
        content = author_owned_synthetic_content(execution.case_id, 0)
        _assert_not_fixture_answer(content, case)
        citations: list[dict[str, Any]] = []
    else:
        content = author_owned_synthetic_content(
            execution.case_id, len(plan.gated_chunks)
        )
        _assert_not_fixture_answer(content, case)
        citations = align_citations_to_answer(
            content,
            list(plan.gated_chunks),
            to_citation=workspace_chunk_to_citation,
        )

    state["content"] = content
    state["citations"] = citations
    content_hash = _sha256_hex(content)
    citations_hash = _sha256_hex(citations)

    return AfterObservationSnapshot(
        case_id=execution.case_id,
        eligibility=True,
        classification=None,
        input_hash=hash_case_input(case),
        gen_plan_reference=plan_hash,
        before_gen_plan_hash=plan_hash,
        after_content=content,
        after_content_hash=content_hash,
        after_citations=tuple(dict(c) for c in citations),
        after_citations_hash=citations_hash,
        plan_refusal=plan.refusal,
        refusal_observation_status=STATUS_OBSERVED_SLOT,
        grounding_observation_status=STATUS_NOT_OBSERVED,
        capture_mode=CAPTURE_MODE_ISOMORPHIC,
        llm_called=False,
        state=state,
    )


async def observe_case(
    monkeypatch: pytest.MonkeyPatch,
    case: Mapping[str, object],
) -> AfterObservationSnapshot:
    """Single-case After observation (E-A2 Before + isomorphic After)."""
    execution = await execute_product_path_plan(monkeypatch, case)
    return capture_isomorphic_after(execution, case)


async def run_isomorphic_observation_suite(
    monkeypatch: pytest.MonkeyPatch | None = None,
) -> list[AfterObservationSnapshot]:
    """Run frozen-12 isomorphic observation; capture only; no formal write."""
    suite = load_frozen_suite()
    if len(suite.cases) != FROZEN_CASE_COUNT:
        raise GenerationObservationExecutorError(
            f"frozen suite size drifted: {len(suite.cases)}"
        )

    snapshots: list[AfterObservationSnapshot] = []
    context = (
        pytest.MonkeyPatch.context()
        if monkeypatch is None
        else _nullcontext(monkeypatch)
    )
    with context as mp:
        for case in suite.cases:
            snapshots.append(await observe_case(mp, case))
    return snapshots


class _nullcontext:
    def __init__(self, value: pytest.MonkeyPatch) -> None:
        self._value = value

    def __enter__(self) -> pytest.MonkeyPatch:
        return self._value

    def __exit__(self, *args: object) -> None:
        return None


def build_smoke_observation_artifact(
    snapshots: Sequence[AfterObservationSnapshot],
    *,
    base_sha: str,
    run_id: str | None = None,
) -> dict[str, Any]:
    """Build E-B2 envelope from snapshots. Always non-formal for isomorphic path."""
    if len(snapshots) != FROZEN_CASE_COUNT:
        raise GenerationObservationExecutorError(
            f"artifact requires {FROZEN_CASE_COUNT} snapshots, got {len(snapshots)}"
        )
    if any(snap.llm_called for snap in snapshots):
        raise GenerationObservationExecutorError("E-B6 path forbids llm_called=true")

    rid = run_id or (
        "w10-eb6-isomorphic-smoke-"
        + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        + "-"
        + base_sha[:12]
    )
    if rid.startswith("SCHEMA_EXAMPLE_"):
        raise GenerationObservationExecutorError(
            "smoke run_id must not use SCHEMA_EXAMPLE_ prefix"
        )

    per_case = [snap.to_per_case_observation() for snap in snapshots]
    c12 = next(item for item in per_case if item["case_id"] == C12_CASE_ID)
    if c12["eligibility"] is not False or c12["classification"] != CLASSIFICATION_INVALID:
        raise GenerationObservationExecutorError("C12 must remain ineligible")

    payload: dict[str, Any] = {
        "protocol_version": PROTOCOL_VERSION,
        "artifact_schema_version": "w10-eb2-generation-observation-v1",
        "run_id": rid,
        "base_sha": base_sha,
        "suite_id": SUITE_ID,
        "case_count": FROZEN_CASE_COUNT,
        "runner_id": RUNNER_ID,
        "runner_module": RUNNER_MODULE,
        "eligibility_protocol_id": ELIGIBILITY_PROTOCOL_ID,
        "parent_protocol_id": PARENT_PROTOCOL_ID,
        "eligibility_summary": {
            "frozen_cases": FROZEN_CASE_COUNT,
            "product_path_eligible": PRODUCT_PATH_ELIGIBLE_EXPECTED,
            "invalid_for_product_path": INVALID_EXPECTED,
            "c12_in_denominator": False,
            "invalid_case_ids": [C12_CASE_ID],
            "targets_measured": [TARGET_T1],
        },
        "per_case_observation": per_case,
        "measurement_validity": {
            "measurement_valid": False,
            "invalid_reasons": [SMOKE_INVALID_REASON],
            "structurally_schema_ok": True,
            "observation_point_honest": True,
            "ea5_artifact_not_reused": True,
            "p2_r3_artifact_not_reused": True,
            "critic_oracle_fields_absent": True,
            "p2_r1_remains_blocked": True,
            "llm_called": False,
        },
        "measurement_claims": {
            "allowed": [ALLOWED_CLAIM],
            "asserted": [ALLOWED_CLAIM],
            "forbidden_rejected": list(FORBIDDEN_CLAIMS),
        },
        "p2_r1_status": P2_R1_STATUS_BLOCKED,
        "does_not_unblock_p2_r1": True,
        "observation_point": OBSERVATION_POINT,
        "artifact_kind": ARTIFACT_KIND_FORMAL_OBS,
        "parent_l0_artifact": EA5_RESULT_FILENAME,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "notes": (
            "W10 E-B6 isomorphic smoke only: zero-LLM After capture for T1 wiring. "
            "Not a formal generation observation; measurement_valid remains false."
        ),
    }
    validate_observation_artifact(payload)
    return payload


def validate_observation_artifact(payload: Mapping[str, Any]) -> None:
    """Accept only E-B2 envelopes; reject E-A5 / P2-R3 / Critic oracle shapes."""
    try:
        validate_reserved_artifact(payload)
    except GenerationObservationContractError as exc:
        raise GenerationObservationExecutorError(str(exc)) from exc
    if payload.get("observation_point") != OBSERVATION_POINT:
        raise GenerationObservationExecutorError(
            "observation_point must be generation_final_content_and_citations"
        )


def write_observation_artifact(
    payload: Mapping[str, Any],
    path: Path,
) -> Path:
    """Write smoke artifact to an explicit non-reserved path only."""
    if path.name == RESERVED_RESULT_FILENAME or path.resolve() == RESERVED_RESULT_PATH.resolve():
        raise GenerationObservationExecutorError(
            f"refusing to write reserved formal result {RESERVED_RESULT_FILENAME}"
        )
    protected = {
        "w10-ea4-formal-window-result.json",
        "w9-critic-p2-r1-independent-review.json",
        "w9-critic-p2-r3-full-product-rerun.json",
        "w9-critic-p2-r1-offline-product.json",
    }
    if path.name in protected:
        raise GenerationObservationExecutorError(
            f"refusing to overwrite protected artifact {path.name}"
        )

    validate_observation_artifact(payload)
    validity = payload["measurement_validity"]
    if validity.get("measurement_valid") is True:
        raise GenerationObservationExecutorError(
            "synthetic/smoke path cannot claim formal measurement_valid=true"
        )
    if validity.get("llm_called") is not False:
        raise GenerationObservationExecutorError("llm_called must remain false")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(dict(payload), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    assert_reserved_result_absent()
    return path


def assert_formal_reserved_result_absent() -> None:
    assert_reserved_result_absent()


def git_base_sha() -> str:
    import subprocess

    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=Path(__file__).resolve().parents[2],
        check=True,
        capture_output=True,
        text=True,
    )
    sha = result.stdout.strip()
    if len(sha) < 7:
        raise GenerationObservationExecutorError(f"invalid git sha {sha!r}")
    return sha
