"""W10 E-B15 — Product After capture harness tests (deterministic · zero LLM)."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.services.rag.generation import no_context_reply_for
from tests.w10_ea2_scope_eligibility import load_frozen_suite
from tests.w10_eb2_generation_observation_contract import (
    C12_CASE_ID,
    FROZEN_CASE_COUNT,
    OBSERVATION_POINT,
    PROTOCOL_VERSION,
    RESERVED_RESULT_FILENAME,
    RESERVED_RESULT_PATH,
    SUITE_ID,
    assert_reserved_result_absent,
)
from tests.w10_eb15_product_after_capture import (
    B2_PRIME_AFTER_SNAPSHOTS,
    CAPTURE_MODE_INELIGIBLE,
    CAPTURE_MODE_PRODUCT_STREAM_DEGRADED,
    CAPTURE_MODE_PRODUCT_STREAM_REFUSAL,
    E_B_FORMAL_READY,
    HARNESS_ID,
    MAY_ENTER_FORMAL_OBSERVATION_WINDOW,
    PRODUCT_AFTER_CAPTURE_HARNESS_READY,
    ProductAfterCaptureError,
    ProductAfterSnapshot,
    assert_eb2_identity_untouched,
    assert_formal_gates_remain_locked,
    capture_empty_gate_product_after,
    capture_frozen_case_product_after,
    readiness_summary,
    refuse_formal_result_write,
    run_empty_gate_product_after_suite,
    validate_eb2_per_case_slot,
)
from tests.w10_eb6_generation_observation_executor import SYNTHETIC_BODY_PREFIX
from tests.w10_eb_empty_gate_cases_contract import CASE_COUNT as EMPTY_GATE_CASE_COUNT


@pytest.mark.asyncio
async def test_empty_gate_suite_enters_real_stream_and_captures_after() -> None:
    snapshots = await run_empty_gate_product_after_suite()
    assert len(snapshots) == EMPTY_GATE_CASE_COUNT
    for snap in snapshots:
        assert isinstance(snap, ProductAfterSnapshot)
        assert snap.stream_phase_entered is True
        assert snap.capture_mode == CAPTURE_MODE_PRODUCT_STREAM_REFUSAL
        assert snap.llm_called is False
        assert snap.plan_refusal is True
        assert snap.eligibility is True
        assert snap.after_content is not None
        assert snap.after_citations == ()
        assert snap.state["content"] == snap.after_content
        assert snap.state["citations"] == []
        assert not snap.after_content.startswith(SYNTHETIC_BODY_PREFIX)
        slot = snap.to_per_case_observation()
        validate_eb2_per_case_slot(slot)
        assert slot["final_content_observation"] == snap.after_content
        assert slot["final_citations"] == []


@pytest.mark.asyncio
async def test_empty_gate_refusal_matches_product_no_context_reply(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tests.w10_eb_empty_gate_cases_contract import load_real_cases

    cases = load_real_cases()["cases"]
    case = cases[0]
    snap = await capture_empty_gate_product_after(monkeypatch, case)
    assert snap.after_content == no_context_reply_for(str(case["query"]))
    assert snap.after_content == case["no_context_reply_for"]
    assert snap.stream_phase_entered is True


@pytest.mark.asyncio
async def test_frozen_eligible_case_uses_degraded_product_stream(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    suite = load_frozen_suite()
    case = next(c for c in suite.cases if str(c["case_id"]).startswith("C01"))
    snap = await capture_frozen_case_product_after(monkeypatch, case)

    assert snap.eligibility is True
    assert snap.stream_phase_entered is True
    assert snap.capture_mode == CAPTURE_MODE_PRODUCT_STREAM_DEGRADED
    assert snap.llm_called is False
    assert snap.plan_refusal is False
    assert snap.after_content is not None
    assert snap.after_content != case["answer"]
    assert not snap.after_content.startswith(SYNTHETIC_BODY_PREFIX)
    assert snap.after_citations is not None
    assert snap.gen_plan_reference is not None
    assert snap.before_gen_plan_hash == snap.gen_plan_reference
    validate_eb2_per_case_slot(snap.to_per_case_observation())


@pytest.mark.asyncio
async def test_c12_stays_ineligible_without_stream_entry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    suite = load_frozen_suite()
    case = next(c for c in suite.cases if c["case_id"] == C12_CASE_ID)
    snap = await capture_frozen_case_product_after(monkeypatch, case)
    assert snap.eligibility is False
    assert snap.stream_phase_entered is False
    assert snap.capture_mode == CAPTURE_MODE_INELIGIBLE
    assert snap.after_content is None
    assert snap.after_citations is None
    assert snap.gen_plan_reference is None
    validate_eb2_per_case_slot(snap.to_per_case_observation())


@pytest.mark.asyncio
async def test_rejects_w9_answer_and_synthetic_as_after(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tests.w10_eb15_product_after_capture import _assert_not_forbidden_content

    suite = load_frozen_suite()
    case = next(c for c in suite.cases if str(c["case_id"]).startswith("C01"))
    with pytest.raises(ProductAfterCaptureError, match="fixture answer"):
        _assert_not_forbidden_content(str(case["answer"]), case)
    with pytest.raises(ProductAfterCaptureError, match="synthetic"):
        _assert_not_forbidden_content(f"{SYNTHETIC_BODY_PREFIX}C01] fake", case)

    # Real capture must not equal fixture answer.
    snap = await capture_frozen_case_product_after(monkeypatch, case)
    assert snap.after_content != case["answer"]


def test_eb2_identity_preserved_and_formal_gates_locked() -> None:
    assert_eb2_identity_untouched()
    assert_formal_gates_remain_locked()
    assert SUITE_ID == "w9_critic_frozen_12"
    assert FROZEN_CASE_COUNT == 12
    assert PROTOCOL_VERSION == "w10_eb2_generation_observation_v1"
    assert OBSERVATION_POINT == "generation_final_content_and_citations"
    assert E_B_FORMAL_READY == "NO"
    assert MAY_ENTER_FORMAL_OBSERVATION_WINDOW == "NO"
    assert PRODUCT_AFTER_CAPTURE_HARNESS_READY == "YES"
    assert B2_PRIME_AFTER_SNAPSHOTS == "BLOCKING_RESIDUAL"
    assert not RESERVED_RESULT_PATH.exists()
    assert_reserved_result_absent()

    summary = readiness_summary()
    assert summary["E-B_FORMAL_READY"] == "NO"
    assert summary["PRODUCT_AFTER_CAPTURE_HARNESS_READY"] == "YES"
    assert summary["harness_id"] == HARNESS_ID


def test_refuses_formal_observation_result_write(tmp_path: Path) -> None:
    with pytest.raises(ProductAfterCaptureError, match="reserved formal"):
        refuse_formal_result_write(RESERVED_RESULT_PATH)
    with pytest.raises(ProductAfterCaptureError, match="must not write formal"):
        refuse_formal_result_write(tmp_path / "informal-smoke.json")
    assert RESERVED_RESULT_FILENAME == "w10-eb2-generation-observation-result.json"
    assert not RESERVED_RESULT_PATH.exists()
