"""W9 P1 deterministic/semantic boundary and terminal-owner gates."""

from __future__ import annotations

import time
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.config import settings
from app.services.agent.runtime import execute_accounted_recovery_step
from app.services.agent.stream import _stream_generation_phase
from app.services.agent.types import (
    AgentActionKind,
    AgentDecision,
    AgentRunOutcome,
)
from app.services.rag.critic import (
    METHOD_LLM_VERIFY_V1,
    CriticAction,
    CriticResult,
    run_critic,
)
from app.services.rag.feedback_attribution import LABEL_UNKNOWN
from app.services.rag.generation import AnswerVerification, no_context_reply_for
from app.services.rag.types import RetrievedChunk


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


@pytest.mark.asyncio
async def test_shallow_overlap_is_not_a_deterministic_semantic_blocker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inspect_answer = AsyncMock(
        return_value=AnswerVerification(
            verified=True,
            issues=(),
            degraded=False,
        )
    )
    monkeypatch.setattr(
        "app.services.rag.generation.inspect_answer", inspect_answer
    )
    monkeypatch.setattr(settings, "rag_critic_enabled", True)
    monkeypatch.setattr(settings, "rag_critic_mode", "llm")

    result = await run_critic(
        "A semantically unrelated assertion.[片段1]",
        [_chunk()],
        "What training is required?",
    )

    assert result.ok is True
    inspect_answer.assert_awaited_once()


async def _run_terminal_phase(
    monkeypatch: pytest.MonkeyPatch,
    *,
    critic: object,
    deadline_monotonic: float,
    on_fail: str = "annotate_only",
) -> tuple[list[str], dict[str, object], AsyncMock]:
    async def _tokens(_messages):
        yield "Unverified draft.[片段1]"

    audit = AsyncMock()
    monkeypatch.setattr(
        "app.services.agent.stream.stream_deepseek_tokens", _tokens
    )
    monkeypatch.setattr("app.services.rag.critic.run_critic", critic)
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
    monkeypatch.setattr(settings, "rag_critic_on_fail", on_fail)
    monkeypatch.setattr(settings, "agent_l3_critic_retrieval_enabled", False)
    outcome = AgentRunOutcome(
        run_id=uuid.uuid4(),
        steps_used=0,
        max_steps=2,
        capped=False,
        timed_out=False,
        steps=(),
        deadline_monotonic=deadline_monotonic,
    )
    state: dict[str, object] = {}
    events = [
        event
        async for event in _stream_generation_phase(
            AsyncMock(),
            message="What training is required?",
            gen_plan=SimpleNamespace(
                citations=[],
                refusal=False,
                gated_chunks=(_chunk(),),
                external_context=None,
            ),
            outcome=outcome,
            user_id=uuid.uuid4(),
            assistant_message_id=uuid.uuid4(),
            state=state,
        )
    ]
    return events, state, audit


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("recommendation", "expected_status"),
    [
        (CriticAction.REFUSE, "executed"),
        (CriticAction.CLARIFY, "mapped_to_refuse"),
    ],
)
async def test_terminal_recommendations_are_owned_audited_and_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
    recommendation: CriticAction,
    expected_status: str,
) -> None:
    async def _critic(*_args) -> CriticResult:
        return CriticResult(
            ok=False,
            claims=(),
            label=LABEL_UNKNOWN,
            rationale="terminal recommendation",
            method=METHOD_LLM_VERIFY_V1,
            recommended_action=recommendation,
        )

    events, state, audit = await _run_terminal_phase(
        monkeypatch,
        critic=_critic,
        deadline_monotonic=time.monotonic() + 30,
    )

    outcome = state["outcome"]
    assert isinstance(outcome, AgentRunOutcome)
    assert outcome.terminal_decision is not None
    assert outcome.terminal_decision.action is AgentActionKind.refuse
    assert outcome.critic_actions[-1].action == recommendation.value
    assert outcome.critic_actions[-1].status == expected_status
    assert state["content"] == no_context_reply_for("What training is required?")
    assert state["content"] in next(
        event for event in events if "event: token" in event
    )
    audit.assert_awaited_once()
    assert audit.await_args.kwargs["status"] == expected_status


@pytest.mark.asyncio
async def test_initial_critic_deadline_precheck_records_zero_attempts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    critic = AsyncMock()
    _events, state, audit = await _run_terminal_phase(
        monkeypatch,
        critic=critic,
        deadline_monotonic=time.monotonic() - 1,
        on_fail="fail_closed",
    )

    critic.assert_not_awaited()
    outcome = state["outcome"]
    assert isinstance(outcome, AgentRunOutcome)
    validation = next(
        action
        for action in outcome.critic_actions
        if action.action == "SEMANTIC_VALIDATION"
    )
    assert validation.status == "deadline_exhausted"
    assert validation.attempt_count == 0
    assert outcome.timed_out is True
    assert outcome.terminal_decision is not None
    assert audit.await_count == 2
    assert audit.await_args_list[0].kwargs["attempt_count"] == 0


@pytest.mark.asyncio
async def test_recovery_executor_rejects_non_semantic_tools(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services.agent import runtime

    execute = AsyncMock()
    monkeypatch.setattr(runtime, "_execute_step", execute)
    outcome = AgentRunOutcome(
        run_id=uuid.uuid4(),
        steps_used=0,
        max_steps=2,
        capped=False,
        timed_out=False,
        steps=(),
    )
    updated = await execute_accounted_recovery_step(
        AsyncMock(),
        outcome=outcome,
        decision=AgentDecision(
            action=AgentActionKind.tool,
            tool_name="generate_faq_draft",
            args={"filename": "unsafe.md"},
            reason_code="critic_directed_retrieve",
        ),
        user_id=uuid.uuid4(),
        thread_id=uuid.uuid4(),
        workspace=MagicMock(),
        tool_scope=MagicMock(),
    )

    assert updated is outcome
    execute.assert_not_awaited()
