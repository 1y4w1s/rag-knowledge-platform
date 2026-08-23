"""W9 P1 scope-denied recovery must override annotate-only policy."""

from __future__ import annotations

import time
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.config import settings
from app.services.agent.stream import _stream_generation_phase
from app.services.agent.tools.scope import FORBIDDEN_KB_SUMMARY
from app.services.agent.types import AgentRunOutcome, AgentStepRecord
from app.services.rag.critic import ClaimCheck, CriticAction, CriticResult
from app.services.rag.feedback_attribution import LABEL_UNKNOWN
from app.services.rag.generation import no_context_reply_for
from app.services.rag.types import RetrievedChunk


@pytest.mark.asyncio
async def test_scope_denied_recovery_forces_final_refusal_under_annotate_only(
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
    initial = AgentRunOutcome(
        run_id=uuid.uuid4(),
        steps_used=0,
        max_steps=2,
        capped=False,
        timed_out=False,
        steps=(),
        deadline_monotonic=time.monotonic() + 30,
    )
    denied = AgentStepRecord(
        step_index=1,
        tool_name="semantic_search",
        args={"query": "restricted"},
        ok=False,
        summary=FORBIDDEN_KB_SUMMARY,
        latency_ms=1,
        origin="critic_recovery",
    )
    denied_outcome = AgentRunOutcome(
        run_id=initial.run_id,
        steps_used=1,
        max_steps=2,
        capped=False,
        timed_out=False,
        steps=(denied,),
        deadline_monotonic=initial.deadline_monotonic,
        critic_recovery_count=1,
    )

    async def _tokens(_messages):
        yield "Unverified draft.[片段1]"

    async def _critic(*_args) -> CriticResult:
        return CriticResult(
            ok=False,
            claims=(
                ClaimCheck(
                    text="Unverified draft.[片段1]",
                    citation_nums=(1,),
                    ok=False,
                    issue="shallow evidence overlap=0.00",
                ),
            ),
            label=LABEL_UNKNOWN,
            rationale="shallow evidence",
            recommended_action=CriticAction.RETRIEVE_MISSING_EVIDENCE,
        )

    monkeypatch.setattr(
        "app.services.agent.stream.stream_deepseek_tokens", _tokens
    )
    monkeypatch.setattr("app.services.rag.critic.run_critic", _critic)
    monkeypatch.setattr(
        "app.services.agent.stream._maybe_critic_retrieve_and_revise",
        AsyncMock(return_value=(denied_outcome, None, None, None)),
    )
    monkeypatch.setattr(
        "app.services.agent.stream.audit_agent_recovery_action", AsyncMock()
    )
    monkeypatch.setattr(
        "app.services.agent.stream.degradation_requires_llm", lambda _d: True
    )
    monkeypatch.setattr(
        "app.services.agent.stream.has_available_chat_provider_key", lambda: True
    )
    monkeypatch.setattr(settings, "rag_critic_enabled", True)
    monkeypatch.setattr(settings, "rag_critic_mode", "rules")
    monkeypatch.setattr(settings, "rag_critic_on_fail", "annotate_only")
    monkeypatch.setattr(settings, "agent_l3_critic_retrieval_enabled", True)
    state: dict[str, object] = {}

    events = [
        event
        async for event in _stream_generation_phase(
            AsyncMock(),
            message="What evidence is missing?",
            gen_plan=SimpleNamespace(
                citations=[],
                refusal=False,
                gated_chunks=(chunk,),
                external_context=None,
            ),
            outcome=initial,
            user_id=uuid.uuid4(),
            assistant_message_id=uuid.uuid4(),
            state=state,
            workspace=MagicMock(),
            tool_scope=MagicMock(),
            thread_id=uuid.uuid4(),
        )
    ]

    refusal = no_context_reply_for("What evidence is missing?")
    assert state["content"] == refusal
    assert [event for event in events if "event: correction" in event] == []
    assert refusal in next(event for event in events if "event: token" in event)
