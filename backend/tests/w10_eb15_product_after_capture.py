"""W10 E-B15 — Product After snapshot capture harness (Scheme A).

Canonical path (test-only):

    prepare_agent_generation
            ↓
    real _stream_generation_phase
            ↓
    state["content"] / state["citations"]
            ↓
    (product-internal citation align when non-refusal)
            ↓
    After snapshot → E-B2 per_case slot mapping

Forbidden: synthetic body, W9 answer backfill, plan-as-final, P2-R1 inject,
Critic oracle, LLM / LM Studio, reserved formal write, flipping E-B_FORMAL_READY.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest

from app.core.config import settings
from app.services.agent.finalize import AgentGenerationPlan, prepare_agent_generation
from app.services.agent.stream import _stream_generation_phase
from app.services.agent.types import AgentRunOutcome
from app.services.rag.generation import no_context_reply_for
from tests.w10_ea2_scope_eligibility import (
    ProductPathExecution,
    execute_product_path_plan,
)
from tests.w10_eb2_generation_observation_contract import (
    CLASSIFICATION_INVALID,
    FROZEN_CASE_COUNT,
    OBSERVATION_POINT,
    PER_CASE_REQUIRED,
    PROTOCOL_VERSION,
    RESERVED_RESULT_FILENAME,
    RESERVED_RESULT_PATH,
    STATUS_INELIGIBLE,
    STATUS_NOT_OBSERVED,
    STATUS_OBSERVED_SLOT,
    SUITE_ID,
    assert_reserved_result_absent,
)
from tests.w10_eb6_generation_observation_executor import (
    SYNTHETIC_BODY_PREFIX,
    hash_case_input,
    hash_gen_plan,
)
from tests.w10_eb_empty_gate_cases_contract import (
    CASES_PATH,
    CASE_COUNT as EMPTY_GATE_CASE_COUNT,
    SUITE_ID as EMPTY_GATE_SUITE_ID,
    load_real_cases,
)
from tests.w9_critic_p2_r1_harness import stable_uuid

# ---------------------------------------------------------------------------
# Gate / identity (readiness — not formal unlock)
# ---------------------------------------------------------------------------

HARNESS_ID = "w10_eb15_product_after_capture"
HARNESS_MODULE = "tests.w10_eb15_product_after_capture"
SCHEME = "A"
CAPTURE_MODE_PRODUCT_STREAM_REFUSAL = "product_stream_refusal"
CAPTURE_MODE_PRODUCT_STREAM_DEGRADED = "product_stream_degraded"
CAPTURE_MODE_INELIGIBLE = "ineligible_no_after"

PRODUCT_AFTER_CAPTURE_HARNESS_READY = "YES"
PRODUCT_AFTER_CAPTURE_FEASIBLE = "YES"
E_B_FORMAL_READY = "NO"
MAY_ENTER_FORMAL_OBSERVATION_WINDOW = "NO"
B2_PRIME_AFTER_SNAPSHOTS = "BLOCKING_RESIDUAL"

TARGET_T1 = "T1"
TARGET_T4 = "T4"
SMOKE_INVALID_REASON = "OTHER_PROTOCOL_BREAK"

FORBIDDEN_SHORTCUT_MARKERS: frozenset[str] = frozenset(
    {
        "execute_frozen_case",
        "author_owned_synthetic_content",
        "eb6-synthetic",
        "expected_action",
        "oracle_cases",
        "w9_critic_oracle",
    }
)


class ProductAfterCaptureError(ValueError):
    """Raised when the product After harness refuses an illegal capture."""


@dataclass(frozen=True, slots=True)
class ProductAfterSnapshot:
    """Product-stream After capture (state slots + honesty labels)."""

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
    stream_phase_entered: bool
    state: Mapping[str, Any]
    suite_id: str
    target: str

    def to_per_case_observation(self) -> dict[str, Any]:
        scope_result: dict[str, Any] | None
        if not self.eligibility:
            scope_result = None
        else:
            scope_result = {
                "target": self.target,
                "capture_mode": self.capture_mode,
                "stream_phase_entered": self.stream_phase_entered,
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


def hash_empty_gate_input(case: Mapping[str, object]) -> str:
    return _sha256_hex(
        {
            "case_id": case.get("case_id"),
            "query": case.get("query"),
            "retrieval_result_state": case.get("retrieval_result_state"),
            "evidence_count": case.get("evidence_count"),
        }
    )


def assert_formal_gates_remain_locked() -> None:
    if E_B_FORMAL_READY != "NO":
        raise ProductAfterCaptureError("E-B_FORMAL_READY must remain NO")
    if MAY_ENTER_FORMAL_OBSERVATION_WINDOW != "NO":
        raise ProductAfterCaptureError(
            "MAY_ENTER_FORMAL_OBSERVATION_WINDOW must remain NO"
        )
    assert_reserved_result_absent()


def assert_eb2_identity_untouched() -> None:
    """Harness must not rewrite E-B2 frozen suite identity."""
    from tests import w10_eb2_generation_observation_contract as eb2

    if eb2.SUITE_ID != SUITE_ID:
        raise ProductAfterCaptureError(f"E-B2 SUITE_ID drift: {eb2.SUITE_ID!r}")
    if eb2.FROZEN_CASE_COUNT != FROZEN_CASE_COUNT:
        raise ProductAfterCaptureError(
            f"E-B2 FROZEN_CASE_COUNT drift: {eb2.FROZEN_CASE_COUNT}"
        )
    if eb2.PROTOCOL_VERSION != PROTOCOL_VERSION:
        raise ProductAfterCaptureError(
            f"E-B2 PROTOCOL_VERSION drift: {eb2.PROTOCOL_VERSION!r}"
        )
    if eb2.OBSERVATION_POINT != OBSERVATION_POINT:
        raise ProductAfterCaptureError(
            f"E-B2 OBSERVATION_POINT drift: {eb2.OBSERVATION_POINT!r}"
        )


def validate_eb2_per_case_slot(payload: Mapping[str, Any]) -> None:
    """Schema-compatibility check for one E-B2 per_case_observation slot."""
    missing = [key for key in PER_CASE_REQUIRED if key not in payload]
    if missing:
        raise ProductAfterCaptureError(f"per_case slot missing fields: {missing}")
    for key in (
        "expected_action",
        "oracle_cases",
        "oracle_case",
        "critic_score",
        "w9_critic_oracle",
        "scope_compliance_pass",
        "scorer_observation_point",
    ):
        if key in payload:
            raise ProductAfterCaptureError(f"forbidden Critic/E-A5 key present: {key}")
    status_keys = ("grounding_observation_status", "refusal_observation_status")
    allowed = {STATUS_NOT_OBSERVED, STATUS_OBSERVED_SLOT, STATUS_INELIGIBLE}
    for key in status_keys:
        if payload[key] not in allowed:
            raise ProductAfterCaptureError(f"invalid {key}={payload[key]!r}")


def _forbid_llm_tokens(_messages: Any):
    raise ProductAfterCaptureError(
        "forbidden: LLM / stream_deepseek_tokens must not be called in E-B15"
    )
    yield  # pragma: no cover — async-generator shape


def force_zero_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force product stream into refusal/degraded branches; never call a provider."""
    monkeypatch.setattr(settings, "chat_provider", "deepseek")
    monkeypatch.setattr(settings, "deepseek_api_key", "")
    monkeypatch.setattr(settings, "tongyi_api_key", "")
    monkeypatch.setattr(settings, "rag_critic_enabled", False)
    monkeypatch.setattr(settings, "agent_l3_critic_retrieval_enabled", False)
    monkeypatch.setattr(
        "app.services.agent.stream.has_available_chat_provider_key",
        lambda: False,
    )
    monkeypatch.setattr(
        "app.services.agent.stream.stream_deepseek_tokens",
        _forbid_llm_tokens,
    )


def _assert_not_forbidden_content(
    content: str,
    case: Mapping[str, object],
) -> None:
    if content.startswith(SYNTHETIC_BODY_PREFIX) or "[eb6-synthetic:" in content:
        raise ProductAfterCaptureError(
            "forbidden: author/synthetic isomorphic body must not be After content"
        )
    fixture_answer = case.get("answer")
    if isinstance(fixture_answer, str) and fixture_answer and content == fixture_answer:
        raise ProductAfterCaptureError(
            "forbidden: W9 fixture answer must not be used as After content"
        )


def _assert_not_plan_as_final(
    *,
    plan: AgentGenerationPlan,
    after_content: str,
    after_citations: Sequence[Mapping[str, Any]],
) -> None:
    """Reject using prepare-only plan citations/text as if they were generation After."""
    if plan.refusal:
        if after_citations:
            raise ProductAfterCaptureError(
                "refusal After must not keep plan citations as final"
            )
        return
    # Non-refusal: After citations may equal plan only after real align; content must
    # come from stream (degraded/LLM), never an empty placeholder left by harness.
    if after_content is None or after_content == "":
        raise ProductAfterCaptureError("product After content missing after stream")


async def prepare_empty_gate_plan(
    monkeypatch: pytest.MonkeyPatch,
    case: Mapping[str, object],
) -> tuple[AgentGenerationPlan, AgentRunOutcome]:
    """Real prepare with empty steps → product refusal plan (no inject)."""
    del monkeypatch  # no finalize patch needed when steps are empty
    case_id = str(case["case_id"])
    query = str(case["query"])
    steps: tuple = ()
    outcome = AgentRunOutcome(
        run_id=stable_uuid(f"{case_id}:eb15:run"),
        steps_used=0,
        max_steps=1,
        capped=False,
        timed_out=False,
        steps=steps,
        deadline_monotonic=time.monotonic() + 30,
    )
    gen_plan = await prepare_agent_generation(
        AsyncMock(),
        query=query,
        steps=steps,
        workspace_mode=True,
        outcome=outcome,
    )
    if not gen_plan.refusal:
        raise ProductAfterCaptureError(
            f"empty-gate prepare must refuse; got refusal=False for {case_id}"
        )
    if gen_plan.gated_chunks:
        raise ProductAfterCaptureError(
            f"empty-gate prepare must have empty gated_chunks for {case_id}"
        )
    return gen_plan, outcome


async def drain_product_generation_phase(
    monkeypatch: pytest.MonkeyPatch,
    *,
    message: str,
    gen_plan: AgentGenerationPlan,
    outcome: AgentRunOutcome,
    case_id: str,
) -> tuple[dict[str, Any], bool, list[str]]:
    """Drain real `_stream_generation_phase`; return state + entered flag + events."""
    force_zero_llm(monkeypatch)
    entered = False
    state: dict[str, Any] = {"content": None, "citations": None}
    events: list[str] = []

    async for frame in _stream_generation_phase(
        AsyncMock(),
        message=message,
        gen_plan=gen_plan,
        outcome=outcome,
        user_id=stable_uuid(f"{case_id}:eb15:user"),
        assistant_message_id=stable_uuid(f"{case_id}:eb15:message"),
        state=state,
    ):
        entered = True
        events.append(frame)

    # Calling the real coroutine body implies entry even if it yielded nothing;
    # product path always yields at least `done`.
    if not events:
        raise ProductAfterCaptureError(
            "_stream_generation_phase produced no SSE events"
        )
    entered = True
    if "content" not in state or state["content"] is None:
        raise ProductAfterCaptureError(
            "product stream did not write state['content']"
        )
    if "citations" not in state or state["citations"] is None:
        raise ProductAfterCaptureError(
            "product stream did not write state['citations']"
        )
    return state, entered, events


def _snapshot_from_state(
    *,
    case: Mapping[str, object],
    case_id: str,
    plan: AgentGenerationPlan,
    state: Mapping[str, Any],
    stream_phase_entered: bool,
    capture_mode: str,
    suite_id: str,
    target: str,
    input_hash: str,
) -> ProductAfterSnapshot:
    content = str(state["content"])
    citations_raw = state["citations"]
    if not isinstance(citations_raw, list):
        raise ProductAfterCaptureError("state['citations'] must be a list")
    citations = tuple(dict(c) for c in citations_raw)
    _assert_not_forbidden_content(content, case)
    _assert_not_plan_as_final(
        plan=plan, after_content=content, after_citations=citations
    )
    plan_hash = hash_gen_plan(plan)
    return ProductAfterSnapshot(
        case_id=case_id,
        eligibility=True,
        classification=None,
        input_hash=input_hash,
        gen_plan_reference=plan_hash,
        before_gen_plan_hash=plan_hash,
        after_content=content,
        after_content_hash=_sha256_hex(content),
        after_citations=citations,
        after_citations_hash=_sha256_hex(list(citations)),
        plan_refusal=plan.refusal,
        refusal_observation_status=STATUS_OBSERVED_SLOT,
        grounding_observation_status=STATUS_NOT_OBSERVED,
        capture_mode=capture_mode,
        llm_called=False,
        stream_phase_entered=stream_phase_entered,
        state=dict(state),
        suite_id=suite_id,
        target=target,
    )


def _ineligible_snapshot(case: Mapping[str, object]) -> ProductAfterSnapshot:
    case_id = str(case["case_id"])
    return ProductAfterSnapshot(
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
        stream_phase_entered=False,
        state={"content": None, "citations": None},
        suite_id=SUITE_ID,
        target=TARGET_T1,
    )


async def capture_empty_gate_product_after(
    monkeypatch: pytest.MonkeyPatch,
    case: Mapping[str, object],
) -> ProductAfterSnapshot:
    """A1: empty-gate prepare → real stream refusal After (zero LLM)."""
    assert_formal_gates_remain_locked()
    case_id = str(case["case_id"])
    query = str(case["query"])
    gen_plan, outcome = await prepare_empty_gate_plan(monkeypatch, case)
    state, entered, _events = await drain_product_generation_phase(
        monkeypatch,
        message=query,
        gen_plan=gen_plan,
        outcome=outcome,
        case_id=case_id,
    )
    expected = no_context_reply_for(query)
    if str(state["content"]) != expected:
        raise ProductAfterCaptureError(
            f"refusal After content mismatch for {case_id}: "
            f"got {state['content']!r}, expected {expected!r}"
        )
    if list(state["citations"]) != []:
        raise ProductAfterCaptureError(
            f"refusal After citations must be [] for {case_id}"
        )
    snap = _snapshot_from_state(
        case=case,
        case_id=case_id,
        plan=gen_plan,
        state=state,
        stream_phase_entered=entered,
        capture_mode=CAPTURE_MODE_PRODUCT_STREAM_REFUSAL,
        suite_id=EMPTY_GATE_SUITE_ID,
        target=TARGET_T4,
        input_hash=hash_empty_gate_input(case),
    )
    validate_eb2_per_case_slot(snap.to_per_case_observation())
    return snap


async def capture_frozen_case_product_after(
    monkeypatch: pytest.MonkeyPatch,
    case: Mapping[str, object],
) -> ProductAfterSnapshot:
    """A2: E-A2 prepare → real stream degraded After (zero LLM; mechanism only)."""
    assert_formal_gates_remain_locked()
    execution: ProductPathExecution = await execute_product_path_plan(
        monkeypatch, case
    )
    if not execution.eligibility.product_path_eligible or execution.gen_plan is None:
        snap = _ineligible_snapshot(case)
        validate_eb2_per_case_slot(snap.to_per_case_observation())
        return snap

    plan = execution.gen_plan
    if plan.refusal:
        # Eligible-but-refuse (empty evidence) still drains product refusal path.
        capture_mode = CAPTURE_MODE_PRODUCT_STREAM_REFUSAL
        target = TARGET_T4
    else:
        capture_mode = CAPTURE_MODE_PRODUCT_STREAM_DEGRADED
        target = TARGET_T1

    outcome = AgentRunOutcome(
        run_id=stable_uuid(f"{execution.case_id}:eb15:run"),
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
        case_id=execution.case_id,
    )
    snap = _snapshot_from_state(
        case=case,
        case_id=execution.case_id,
        plan=plan,
        state=state,
        stream_phase_entered=entered,
        capture_mode=capture_mode,
        suite_id=SUITE_ID,
        target=target,
        input_hash=hash_case_input(case),
    )
    validate_eb2_per_case_slot(snap.to_per_case_observation())
    return snap


async def run_empty_gate_product_after_suite(
    monkeypatch: pytest.MonkeyPatch | None = None,
) -> list[ProductAfterSnapshot]:
    """Capture product After for all REAL_ELIGIBLE empty-gate cases."""
    artifact = load_real_cases()
    cases = artifact["cases"]
    assert isinstance(cases, list)
    if len(cases) != EMPTY_GATE_CASE_COUNT:
        raise ProductAfterCaptureError(
            f"empty-gate case_count drifted: {len(cases)} != {EMPTY_GATE_CASE_COUNT}"
        )
    snapshots: list[ProductAfterSnapshot] = []
    context = (
        pytest.MonkeyPatch.context()
        if monkeypatch is None
        else _nullcontext(monkeypatch)
    )
    with context as mp:
        for case in cases:
            assert isinstance(case, Mapping)
            snapshots.append(await capture_empty_gate_product_after(mp, case))
    assert_formal_gates_remain_locked()
    return snapshots


def readiness_summary() -> dict[str, str]:
    return {
        "scheme": SCHEME,
        "PRODUCT_AFTER_CAPTURE_FEASIBLE": PRODUCT_AFTER_CAPTURE_FEASIBLE,
        "PRODUCT_AFTER_CAPTURE_HARNESS_READY": PRODUCT_AFTER_CAPTURE_HARNESS_READY,
        "B2_PRIME_AFTER_SNAPSHOTS": B2_PRIME_AFTER_SNAPSHOTS,
        "MAY_ENTER_FORMAL_OBSERVATION_WINDOW": MAY_ENTER_FORMAL_OBSERVATION_WINDOW,
        "E-B_FORMAL_READY": E_B_FORMAL_READY,
        "harness_id": HARNESS_ID,
        "harness_module": HARNESS_MODULE,
        "empty_gate_cases_path": str(CASES_PATH),
        "reserved_formal_result": RESERVED_RESULT_FILENAME,
    }


def refuse_formal_result_write(path: Path) -> None:
    if path.name == RESERVED_RESULT_FILENAME or path.resolve() == RESERVED_RESULT_PATH.resolve():
        raise ProductAfterCaptureError(
            f"refusing to write reserved formal result {RESERVED_RESULT_FILENAME}"
        )
    raise ProductAfterCaptureError(
        "E-B15 harness must not write formal observation results"
    )


class _nullcontext:
    def __init__(self, value: pytest.MonkeyPatch) -> None:
        self._value = value

    def __enter__(self) -> pytest.MonkeyPatch:
        return self._value

    def __exit__(self, *args: object) -> None:
        return None
