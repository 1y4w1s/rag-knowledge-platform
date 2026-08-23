"""W9 P1 outer-owner action outcome and failure accounting gates."""

from __future__ import annotations

import inspect
import time
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.core.config import settings
from app.services.agent.stream import (
    _maybe_critic_retrieve_and_revise,
    _stream_generation_phase,
)
from app.services.agent.planners import (
    LLMPlanner,
    LLMPlannerFactory,
    NextActionPlanner,
)
from app.services.agent.types import AgentRunOutcome
from app.services.rag.critic import (
    METHOD_LLM_VERIFY_V1,
    ClaimCheck,
    CriticAction,
    CriticResult,
)
from app.services.rag.feedback_attribution import LABEL_UNKNOWN
from app.services.rag.types import RetrievedChunk


def test_e2_and_l3_remain_mutually_exclusive_with_critic_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services.agent import runtime

    monkeypatch.setattr(settings, "rag_critic_enabled", True)
    monkeypatch.setattr(settings, "agent_l3_critic_retrieval_enabled", True)
    monkeypatch.setattr(settings, "agent_l3_next_action_enabled", False)
    legacy = LLMPlannerFactory.create(
        "Compare Docker and Compose, then calculate their differences."
    )
    assert isinstance(legacy, LLMPlanner)

    monkeypatch.setattr(settings, "agent_l3_next_action_enabled", True)
    l3 = LLMPlannerFactory.create(
        "Compare Docker and Compose, then calculate their differences."
    )
    assert isinstance(l3, NextActionPlanner)
    assert "run_critic" not in inspect.getsource(runtime)


def _chunk() -> RetrievedChunk:
    return RetrievedChunk(
        kb_id=uuid.uuid4(),
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        doc_name="policy.md",
        content="Employees complete offboarding training before departure.",
        page_number=1,
        section_title="Offboarding",
        heading_path="Offboarding",
        similarity=0.9,
    )


async def _run_phase(
    monkeypatch: pytest.MonkeyPatch,
    *,
    critic: object,
    revision: object,
) -> tuple[list[str], dict[str, object], AsyncMock]:
    async def _tokens(_messages):
        yield "Training is required."

    audit = AsyncMock()
    monkeypatch.setattr(
        "app.services.agent.stream.stream_deepseek_tokens", _tokens
    )
    monkeypatch.setattr("app.services.rag.critic.run_critic", critic)
    monkeypatch.setattr(
        "app.services.rag.generation.revise_answer_from_existing_evidence",
        revision,
    )
    monkeypatch.setattr(
        "app.services.agent.stream.audit_agent_recovery_action", audit
    )
    monkeypatch.setattr(
        "app.services.agent.stream.degradation_requires_llm", lambda _d: True
    )
    monkeypatch.setattr(
        "app.services.agent.stream.has_available_chat_provider_key", lambda: True
    )
    monkeypatch.setattr(settings, "rag_critic_enabled", True)
    monkeypatch.setattr(settings, "rag_critic_mode", "llm")
    monkeypatch.setattr(settings, "rag_critic_on_fail", "fail_closed")
    monkeypatch.setattr(settings, "agent_l3_critic_retrieval_enabled", False)
    outcome = AgentRunOutcome(
        run_id=uuid.uuid4(),
        steps_used=0,
        max_steps=2,
        capped=False,
        timed_out=False,
        steps=(),
        deadline_monotonic=time.monotonic() + 30,
    )
    plan = SimpleNamespace(
        citations=[],
        refusal=False,
        gated_chunks=(_chunk(),),
        external_context=None,
    )
    state: dict[str, object] = {}
    events = [
        event
        async for event in _stream_generation_phase(
            AsyncMock(),
            message="What training is required?",
            gen_plan=plan,
            outcome=outcome,
            user_id=uuid.uuid4(),
            assistant_message_id=uuid.uuid4(),
            state=state,
        )
    ]
    return events, state, audit


@pytest.mark.asyncio
async def test_accept_has_no_outer_action(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _accept(*_args) -> CriticResult:
        return CriticResult(
            ok=True,
            claims=(),
            label=LABEL_UNKNOWN,
            rationale="accepted",
            method=METHOD_LLM_VERIFY_V1,
        )

    events, state, audit = await _run_phase(
        monkeypatch,
        critic=_accept,
        revision=AsyncMock(),
    )

    assert not [event for event in events if "event: correction" in event]
    outcome = state["outcome"]
    assert isinstance(outcome, AgentRunOutcome)
    assert outcome.critic_validation_count == 1
    assert outcome.critic_revision_count == 0
    assert outcome.critic_actions == ()
    audit.assert_not_awaited()


@pytest.mark.asyncio
async def test_failed_revision_consumes_budget_and_is_audited(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _revise(*_args) -> CriticResult:
        return CriticResult(
            ok=False,
            claims=(),
            label=LABEL_UNKNOWN,
            rationale="unsupported claim",
            method=METHOD_LLM_VERIFY_V1,
            recommended_action=CriticAction.REVISE_FROM_EXISTING_EVIDENCE,
            metadata={"critic.issues": ["unsupported claim"]},
        )

    events, state, audit = await _run_phase(
        monkeypatch,
        critic=_revise,
        revision=AsyncMock(return_value=None),
    )

    assert not [event for event in events if "event: correction" in event]
    outcome = state["outcome"]
    assert isinstance(outcome, AgentRunOutcome)
    assert outcome.critic_validation_count == 1
    assert outcome.critic_revision_count == 1
    assert outcome.critic_actions[-1].status == "failed"
    audit.assert_awaited_once()
    assert audit.await_args.kwargs["status"] == "failed"


@pytest.mark.asyncio
async def test_same_action_after_recheck_is_recorded_as_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    revise_result = CriticResult(
        ok=False,
        claims=(),
        label=LABEL_UNKNOWN,
        rationale="unsupported claim",
        method=METHOD_LLM_VERIFY_V1,
        recommended_action=CriticAction.REVISE_FROM_EXISTING_EVIDENCE,
        metadata={"critic.issues": ["unsupported claim"]},
    )
    critic = AsyncMock(side_effect=[revise_result, revise_result])

    _events, state, audit = await _run_phase(
        monkeypatch,
        critic=critic,
        revision=AsyncMock(return_value="Still unsupported.[片段1]"),
    )

    outcome = state["outcome"]
    assert isinstance(outcome, AgentRunOutcome)
    revision_actions = [
        action
        for action in outcome.critic_actions
        if action.action == CriticAction.REVISE_FROM_EXISTING_EVIDENCE.value
    ]
    assert [action.status for action in revision_actions] == [
        "executed",
        "skipped_unavailable",
    ]
    assert outcome.critic_revision_count == 1
    assert outcome.critic_validation_count == 2
    assert audit.await_count == 2


@pytest.mark.asyncio
async def test_production_retrieval_planner_budget_skip_enters_trajectory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    audit = AsyncMock()
    monkeypatch.setattr(
        "app.services.agent.stream.audit_agent_recovery_action", audit
    )
    monkeypatch.setattr(settings, "agent_l3_critic_retrieval_enabled", True)
    outcome = AgentRunOutcome(
        run_id=uuid.uuid4(),
        steps_used=2,
        max_steps=2,
        capped=True,
        timed_out=False,
        steps=(),
        deadline_monotonic=time.monotonic() + 30,
    )
    result = await _maybe_critic_retrieve_and_revise(
        AsyncMock(),
        message="What evidence is missing?",
        query_for_gen="What evidence is missing?",
        critic_result=CriticResult(
            ok=False,
            claims=(
                ClaimCheck(
                    text="The policy requires missing evidence.[片段1]",
                    citation_nums=(1,),
                    ok=False,
                    issue="shallow evidence overlap=0.00",
                ),
            ),
            label=LABEL_UNKNOWN,
            rationale="shallow evidence",
            recommended_action=CriticAction.RETRIEVE_MISSING_EVIDENCE,
        ),
        outcome=outcome,
        active_plan=SimpleNamespace(),
        history=None,
        workspace=AsyncMock(),
        tool_scope=AsyncMock(),
        org_scope=None,
        workspace_mode=False,
        default_kb_id=None,
        user_id=uuid.uuid4(),
        thread_id=uuid.uuid4(),
        hooks=None,
        current_user=None,
    )

    assert result is not None
    updated, revised_plan, revised_content, revised_critic = result
    assert revised_plan is revised_content is revised_critic is None
    assert updated.critic_actions[-1].status == "budget_exhausted"
    audit.assert_awaited_once()


@pytest.mark.asyncio
async def test_retrieval_revision_deadline_is_canonical_and_timed_out(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chunk = _chunk()
    record = SimpleNamespace(ok=True, data=object())
    audit = AsyncMock()
    initial = AgentRunOutcome(
        run_id=uuid.uuid4(),
        steps_used=0,
        max_steps=2,
        capped=False,
        timed_out=False,
        steps=(),
        deadline_monotonic=time.monotonic() + 30,
    )
    recovered = AgentRunOutcome(
        run_id=initial.run_id,
        steps_used=1,
        max_steps=2,
        capped=False,
        timed_out=False,
        steps=(record,),
        deadline_monotonic=time.monotonic() - 1,
        critic_recovery_count=1,
    )
    monkeypatch.setattr(
        "app.services.agent.stream.execute_accounted_recovery_step",
        AsyncMock(return_value=recovered),
    )
    monkeypatch.setattr(
        "app.services.agent.finalize.merge_step_hits_to_chunks",
        AsyncMock(return_value=[chunk]),
    )
    monkeypatch.setattr(
        "app.services.agent.stream.audit_agent_recovery_action", audit
    )
    monkeypatch.setattr(settings, "agent_l3_critic_retrieval_enabled", True)
    critic_result = CriticResult(
        ok=False,
        claims=(
            ClaimCheck(
                text="The policy requires missing evidence.[片段1]",
                citation_nums=(1,),
                ok=False,
                issue="shallow evidence overlap=0.00",
            ),
        ),
        label=LABEL_UNKNOWN,
        rationale="shallow evidence",
        recommended_action=CriticAction.RETRIEVE_MISSING_EVIDENCE,
    )
    plan = SimpleNamespace(
        gated_chunks=(chunk,),
        citations=(),
        refusal=False,
        external_context=None,
    )
    monkeypatch.setattr(
        "app.services.agent.finalize.gate_agent_chunks",
        lambda *_args, **_kwargs: plan,
    )

    result = await _maybe_critic_retrieve_and_revise(
        AsyncMock(),
        message="What evidence is missing?",
        query_for_gen="What evidence is missing?",
        critic_result=critic_result,
        outcome=initial,
        active_plan=plan,
        history=None,
        workspace=AsyncMock(),
        tool_scope=AsyncMock(),
        org_scope=None,
        workspace_mode=False,
        default_kb_id=None,
        user_id=uuid.uuid4(),
        thread_id=uuid.uuid4(),
        hooks=None,
        current_user=None,
    )

    assert result is not None
    updated, revised_plan, revised_content, revised_critic = result
    assert revised_plan is revised_content is revised_critic is None
    assert updated.timed_out is True
    assert updated.critic_actions[-1].status == "deadline_exhausted"
    assert updated.critic_actions[-1].attempt_count == 0
    assert audit.await_args.kwargs["status"] == "deadline_exhausted"
    assert audit.await_args.kwargs["attempt_count"] == 0
