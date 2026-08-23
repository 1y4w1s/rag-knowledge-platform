"""W9 P1 critic recovery failure and revalidation gates."""

from __future__ import annotations

import asyncio
import time
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.config import settings
from app.services.agent.runtime import execute_accounted_recovery_step
from app.services.agent.stream import _stream_generation_phase
from app.services.agent.tools.scope import FORBIDDEN_KB_SUMMARY
from app.services.agent.types import (
    AgentActionKind,
    AgentDecision,
    AgentRunOutcome,
    StepExecution,
    ToolFailure,
    ToolFailureKind,
)
from app.services.rag.critic import METHOD_LLM_VERIFY_V1, CriticAction, CriticResult
from app.services.rag.feedback_attribution import LABEL_UNKNOWN
from app.services.rag.engine import ChatEngine
from app.services.rag.types import RetrievedChunk


def _fast_chunk() -> RetrievedChunk:
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
async def test_fast_degraded_candidate_still_crosses_final_critic_boundary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = ChatEngine(
        MagicMock(),
        user_id=uuid.uuid4(),
        message="What training is required?",
        kb_id=uuid.uuid4(),
    )
    engine.chunks = [_fast_chunk()]
    critic_inputs: list[str] = []

    async def _degraded(_message, _chunks):
        yield "Validated degraded answer.[片段1]"

    async def _critic(answer: str, *_args) -> CriticResult:
        critic_inputs.append(answer)
        return CriticResult(
            ok=True,
            claims=(),
            label=LABEL_UNKNOWN,
            rationale="accepted",
        )

    monkeypatch.setattr(
        "app.services.rag.engine.stream_degraded_fragment_reply", _degraded
    )
    monkeypatch.setattr("app.services.rag.critic.run_critic", _critic)
    monkeypatch.setattr(engine, "_save", AsyncMock(return_value=uuid.uuid4()))
    monkeypatch.setattr(settings, "rag_critic_enabled", True)
    monkeypatch.setattr(settings, "rag_critic_mode", "rules")

    events = [event async for event in engine._emit_degraded_reply()]

    assert critic_inputs == ["Validated degraded answer.[片段1]"]
    assert [e["data"]["text"] for e in events if e["event"] == "token"] == [
        "Validated degraded answer.[片段1]"
    ]
    assert engine.collected_text == "Validated degraded answer.[片段1]"


@pytest.mark.asyncio
async def test_fast_interruption_never_exposes_unvalidated_collected_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = ChatEngine(
        MagicMock(),
        user_id=uuid.uuid4(),
        message="What training is required?",
        kb_id=uuid.uuid4(),
    )
    chunk = _fast_chunk()
    started = asyncio.Event()
    blocker = asyncio.Event()

    async def _load_history() -> None:
        engine.history = None
        engine.retrieval_query = engine.message

    async def _retrieve() -> list[RetrievedChunk]:
        engine.chunks = [chunk]
        return engine.chunks

    async def _tokens(_messages):
        started.set()
        yield "unvalidated draft"
        await blocker.wait()

    async def _consume() -> None:
        async for _event in engine.stream():
            pass

    monkeypatch.setattr(engine, "_load_history", _load_history)
    monkeypatch.setattr(engine, "_retrieve", _retrieve)
    monkeypatch.setattr("app.services.rag.engine.stream_deepseek_tokens", _tokens)
    monkeypatch.setattr(
        "app.services.rag.engine.degradation_requires_llm", lambda _d: True
    )
    monkeypatch.setattr(
        "app.services.rag.engine.has_available_chat_provider_key", lambda: True
    )
    monkeypatch.setattr(
        "app.services.rag.engine.llm_response_cache.get",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(settings, "rag_critic_enabled", True)

    task = asyncio.create_task(_consume())
    await asyncio.wait_for(started.wait(), timeout=1)
    await asyncio.sleep(0)
    assert engine.collected_text == ""
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
async def test_scope_denied_recovery_is_one_visible_failed_step(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services.agent import runtime

    run_id = uuid.uuid4()
    user_id = uuid.uuid4()
    db_step = SimpleNamespace(id=uuid.uuid4())
    captured: dict[str, object] = {}

    async def _execute(*_args, **kwargs) -> StepExecution:
        captured.update(kwargs)
        return StepExecution(
            ok=False,
            summary=FORBIDDEN_KB_SUMMARY,
            latency_ms=7,
            data=None,
            failure=ToolFailure(
                kind=ToolFailureKind.denied,
                tool_name="semantic_search",
                summary=FORBIDDEN_KB_SUMMARY,
            ),
        )

    recovery_audit = AsyncMock()
    denied_audit = AsyncMock()
    monkeypatch.setattr(runtime, "_execute_step", _execute)
    monkeypatch.setattr(
        runtime, "create_agent_step", AsyncMock(return_value=db_step)
    )
    monkeypatch.setattr(runtime, "finish_agent_step", AsyncMock())
    monkeypatch.setattr(runtime, "audit_agent_tool_executed", AsyncMock())
    monkeypatch.setattr(runtime, "audit_agent_tool_denied", denied_audit)
    monkeypatch.setattr(runtime, "audit_agent_recovery_action", recovery_audit)
    monkeypatch.setattr(runtime, "update_agent_run_steps_used", AsyncMock())

    outcome = AgentRunOutcome(
        run_id=run_id,
        steps_used=0,
        max_steps=2,
        capped=False,
        timed_out=False,
        steps=(),
        deadline_monotonic=time.monotonic() + 30,
    )
    decision = AgentDecision(
        action=AgentActionKind.tool,
        tool_name="semantic_search",
        args={"query": "restricted evidence", "kb_ids": [str(uuid.uuid4())]},
        reason_code="critic_directed_retrieve",
    )

    updated = await execute_accounted_recovery_step(
        AsyncMock(),
        outcome=outcome,
        decision=decision,
        user_id=user_id,
        thread_id=uuid.uuid4(),
        workspace=MagicMock(),
        tool_scope=MagicMock(),
    )

    assert updated.steps_used == 1
    assert updated.critic_recovery_count == 1
    assert len(updated.steps) == 1
    assert updated.steps[0].ok is False
    assert updated.steps[0].origin == "critic_recovery"
    assert updated.steps[0].attempt_count == 1
    assert updated.evidence_state.chunk_ids == ()
    assert captured["max_retries"] == 0
    denied_audit.assert_awaited_once()
    recovery_audit.assert_awaited_once()
    assert recovery_audit.await_args.kwargs["status"] == "failed"
    assert recovery_audit.await_args.kwargs["attempt_count"] == 1


@pytest.mark.asyncio
async def test_recovery_dispatch_is_cancelled_at_shared_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services.agent import runtime

    async def _blocked(*_args, **_kwargs) -> StepExecution:
        await asyncio.Event().wait()
        raise AssertionError("unreachable")

    recovery_audit = AsyncMock()
    monkeypatch.setattr(runtime, "_execute_step", _blocked)
    monkeypatch.setattr(
        runtime,
        "create_agent_step",
        AsyncMock(return_value=SimpleNamespace(id=uuid.uuid4())),
    )
    monkeypatch.setattr(runtime, "finish_agent_step", AsyncMock())
    monkeypatch.setattr(runtime, "audit_agent_tool_executed", AsyncMock())
    monkeypatch.setattr(runtime, "audit_agent_recovery_action", recovery_audit)
    monkeypatch.setattr(runtime, "update_agent_run_steps_used", AsyncMock())
    outcome = AgentRunOutcome(
        run_id=uuid.uuid4(),
        steps_used=0,
        max_steps=2,
        capped=False,
        timed_out=False,
        steps=(),
        deadline_monotonic=time.monotonic() + 0.01,
    )

    updated = await execute_accounted_recovery_step(
        AsyncMock(),
        outcome=outcome,
        decision=AgentDecision(
            action=AgentActionKind.tool,
            tool_name="semantic_search",
            args={"query": "evidence"},
            reason_code="critic_directed_retrieve",
        ),
        user_id=uuid.uuid4(),
        thread_id=uuid.uuid4(),
        workspace=MagicMock(),
        tool_scope=MagicMock(),
    )

    assert updated.timed_out is True
    assert updated.steps_used == 1
    assert updated.steps[-1].ok is False
    assert updated.steps[-1].latency_ms >= 1
    assert updated.critic_actions[-1].status == "deadline_exhausted"
    assert recovery_audit.await_args.kwargs["status"] == "deadline_exhausted"


@pytest.mark.asyncio
async def test_revision_is_revalidated_before_final_candidate_is_published(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chunk = RetrievedChunk(
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
    initial = "Training is required."
    revised = "Employees complete offboarding training before departure.[片段1]"
    critic_inputs: list[str] = []

    async def _tokens(_messages):
        yield initial

    async def _critic(answer: str, *_args) -> CriticResult:
        critic_inputs.append(answer)
        if len(critic_inputs) == 1:
            return CriticResult(
                ok=False,
                claims=(),
                label=LABEL_UNKNOWN,
                rationale="citation missing",
                method=METHOD_LLM_VERIFY_V1,
                recommended_action=CriticAction.REVISE_FROM_EXISTING_EVIDENCE,
                metadata={"critic.issues": ["citation missing"]},
            )
        return CriticResult(
            ok=True,
            claims=(),
            label=LABEL_UNKNOWN,
            rationale="accepted",
        )

    revision = AsyncMock(return_value=revised)
    revision_audit = AsyncMock()
    monkeypatch.setattr(
        "app.services.agent.stream.stream_deepseek_tokens", _tokens
    )
    monkeypatch.setattr("app.services.rag.critic.run_critic", _critic)
    monkeypatch.setattr(
        "app.services.rag.generation.revise_answer_from_existing_evidence",
        revision,
    )
    monkeypatch.setattr(
        "app.services.agent.stream.audit_agent_recovery_action",
        revision_audit,
    )
    monkeypatch.setattr(
        "app.services.agent.stream.degradation_requires_llm", lambda _d: True
    )
    monkeypatch.setattr(
        "app.services.agent.stream.has_available_chat_provider_key", lambda: True
    )
    monkeypatch.setattr(settings, "rag_critic_enabled", True)
    monkeypatch.setattr(settings, "rag_critic_mode", "rules")
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
        gated_chunks=(chunk,),
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

    assert critic_inputs == [initial, revised]
    revision.assert_awaited_once()
    revision_audit.assert_awaited_once()
    assert revision_audit.await_args.kwargs["action"] == (
        "REVISE_FROM_EXISTING_EVIDENCE"
    )
    assert revision_audit.await_args.kwargs["status"] == "executed"
    final_tokens = [event for event in events if "event: token" in event]
    assert len(final_tokens) == 1
    assert revised in final_tokens[0]
    assert state["content"] == revised
    updated = state["outcome"]
    assert isinstance(updated, AgentRunOutcome)
    assert updated.critic_revision_count == 1
    assert updated.critic_validation_count == 2
