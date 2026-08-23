"""W9 P2b C11 repair regression; fully offline and no provider execution."""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.core.config import settings
from app.services.agent.stream import _stream_generation_phase
from app.services.agent.types import AgentRunOutcome
from app.services.rag.critic import METHOD_LLM_VERIFY_V1, CriticAction, CriticResult
from app.services.rag.feedback_attribution import LABEL_UNKNOWN, METHOD_RULES_V1
from app.services.rag.generation import no_context_reply_for
from app.services.rag.types import RetrievedChunk


FIXTURES = Path(__file__).parent / "fixtures" / "l4_critic"
P2_INJECTED_PATH = FIXTURES / "w9-critic-p2-injected-reports.json"
P2B_ARTIFACT_PATH = FIXTURES / "w9-critic-p2b-c11-remediation.json"
MESSAGE = "What training is required?"
INITIAL = "Draft with an invalid citation.[片段2]"
REVISED = "Employees complete offboarding training before departure.[片段1]"


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


def _failed_revision(method: str) -> CriticResult:
    return CriticResult(
        ok=False,
        claims=(),
        label=LABEL_UNKNOWN,
        rationale="citation out of range: [2]",
        method=method,
        metadata={"critic.issues": ["citation out of range: [2]"]},
        recommended_action=CriticAction.REVISE_FROM_EXISTING_EVIDENCE,
    )


def _accepted(method: str) -> CriticResult:
    return CriticResult(
        ok=True,
        claims=(),
        label=LABEL_UNKNOWN,
        rationale="validated",
        method=method,
    )


async def _run_phase(
    monkeypatch: pytest.MonkeyPatch,
    *,
    critic: object,
    revision: object,
    outcome: AgentRunOutcome | None = None,
) -> tuple[list[str], dict[str, object], AsyncMock, RetrievedChunk]:
    async def _tokens(_messages):
        yield INITIAL

    async def _forbidden_retrieval(*_args, **_kwargs):
        raise AssertionError("C11 revision must not trigger retrieval")

    audit = AsyncMock()
    chunk = _chunk()
    monkeypatch.setattr("app.services.agent.stream.stream_deepseek_tokens", _tokens)
    monkeypatch.setattr("app.services.rag.critic.run_critic", critic)
    monkeypatch.setattr(
        "app.services.rag.generation.revise_answer_from_existing_evidence", revision
    )
    monkeypatch.setattr(
        "app.services.agent.stream._maybe_critic_retrieve_and_revise",
        _forbidden_retrieval,
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
    monkeypatch.setattr(settings, "rag_critic_mode", "rules")
    monkeypatch.setattr(settings, "rag_critic_on_fail", "fail_closed")
    monkeypatch.setattr(settings, "agent_l3_critic_retrieval_enabled", False)
    if outcome is None:
        outcome = AgentRunOutcome(
            run_id=uuid.uuid4(),
            steps_used=0,
            max_steps=2,
            capped=False,
            timed_out=False,
            steps=(),
            deadline_monotonic=time.monotonic() + 30,
        )
    state: dict[str, object] = {}
    frames = [
        frame
        async for frame in _stream_generation_phase(
            AsyncMock(),
            message=MESSAGE,
            gen_plan=SimpleNamespace(
                citations=[],
                refusal=False,
                gated_chunks=(chunk,),
                external_context=None,
            ),
            outcome=outcome,
            user_id=uuid.uuid4(),
            assistant_message_id=uuid.uuid4(),
            state=state,
        )
    ]
    return frames, state, audit, chunk


@pytest.mark.asyncio
async def test_c11_rules_revision_uses_existing_executor_and_validates_before_publish(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    injected = json.loads(P2_INJECTED_PATH.read_text(encoding="utf-8"))
    c11 = next(
        item
        for item in injected["reports"]
        if item["case_id"] == "C11-citation-format-only-defect"
    )
    assert c11 == {
        "case_id": "C11-citation-format-only-defect",
        "ok": False,
        "method": METHOD_RULES_V1,
        "recommended_action": CriticAction.REVISE_FROM_EXISTING_EVIDENCE.value,
    }
    trace: list[str] = []

    async def _critic(*_args) -> CriticResult:
        trace.append("validation")
        return (
            _failed_revision(METHOD_RULES_V1)
            if len(trace) == 1
            else _accepted(METHOD_RULES_V1)
        )

    async def _revision(*args) -> str:
        trace.append("revision")
        assert len(args[1]) == 1
        assert args[1][0].content == _chunk().content
        return REVISED

    frames, state, audit, _chunk_value = await _run_phase(
        monkeypatch, critic=_critic, revision=_revision
    )

    observed = state["outcome"]
    assert isinstance(observed, AgentRunOutcome)
    assert trace == ["validation", "revision", "validation"]
    assert observed.critic_revision_count == 1
    assert observed.critic_validation_count == 2
    assert [(item.action, item.status, item.attempt_count) for item in observed.critic_actions] == [
        (CriticAction.REVISE_FROM_EXISTING_EVIDENCE.value, "executed", 1)
    ]
    assert state["content"] == REVISED
    final_tokens = [frame for frame in frames if "event: token" in frame]
    assert len(final_tokens) == 1 and REVISED in final_tokens[0]
    assert INITIAL not in final_tokens[0]
    audit.assert_awaited_once()
    assert audit.await_args.kwargs["run_id"] == observed.run_id
    assert audit.await_args.kwargs["action"] == (
        CriticAction.REVISE_FROM_EXISTING_EVIDENCE.value
    )
    assert audit.await_args.kwargs["status"] == "executed"
    assert audit.await_args.kwargs["budget_before"] == 1
    assert audit.await_args.kwargs["budget_after"] == 0
    assert audit.await_args.kwargs["attempt_count"] == 1


@pytest.mark.asyncio
async def test_rules_revision_deadline_exhaustion_has_no_attempt_or_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock_calls = 0

    def _clock() -> float:
        nonlocal clock_calls
        clock_calls += 1
        return 10.0 if clock_calls == 1 else 31.0

    monkeypatch.setattr("app.services.agent.stream.time.monotonic", _clock)
    revision = AsyncMock(return_value=REVISED)
    outcome = AgentRunOutcome(
        run_id=uuid.uuid4(),
        steps_used=0,
        max_steps=2,
        capped=False,
        timed_out=False,
        steps=(),
        deadline_monotonic=30.0,
    )
    _frames, state, audit, _chunk_value = await _run_phase(
        monkeypatch,
        critic=AsyncMock(return_value=_failed_revision(METHOD_RULES_V1)),
        revision=revision,
        outcome=outcome,
    )

    observed = state["outcome"]
    assert isinstance(observed, AgentRunOutcome)
    assert observed.timed_out is True
    assert observed.critic_revision_count == 1
    assert observed.critic_actions[-1].status == "deadline_exhausted"
    assert observed.critic_actions[-1].attempt_count == 0
    assert state["content"] == no_context_reply_for(MESSAGE)
    revision.assert_not_awaited()
    audit.assert_awaited_once()


@pytest.mark.asyncio
async def test_rules_revision_executor_failure_is_visible_and_bounded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _failed_executor(*_args) -> str:
        raise RuntimeError("offline executor failure")

    _frames, state, audit, _chunk_value = await _run_phase(
        monkeypatch,
        critic=AsyncMock(return_value=_failed_revision(METHOD_RULES_V1)),
        revision=_failed_executor,
    )

    observed = state["outcome"]
    assert isinstance(observed, AgentRunOutcome)
    assert observed.critic_revision_count == 1
    assert observed.critic_actions[-1].status == "failed"
    assert observed.critic_actions[-1].attempt_count == 1
    assert state["content"] == no_context_reply_for(MESSAGE)
    audit.assert_awaited_once()


@pytest.mark.asyncio
async def test_rules_revision_does_not_exceed_consumed_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    revision = AsyncMock(return_value=REVISED)
    outcome = AgentRunOutcome(
        run_id=uuid.uuid4(),
        steps_used=0,
        max_steps=2,
        capped=False,
        timed_out=False,
        steps=(),
        deadline_monotonic=time.monotonic() + 30,
        critic_revision_count=1,
    )
    _frames, state, audit, _chunk_value = await _run_phase(
        monkeypatch,
        critic=AsyncMock(return_value=_failed_revision(METHOD_RULES_V1)),
        revision=revision,
        outcome=outcome,
    )

    observed = state["outcome"]
    assert isinstance(observed, AgentRunOutcome)
    assert observed.critic_revision_count == 1
    assert observed.critic_actions[-1].status == "skipped_unavailable"
    assert observed.critic_actions[-1].attempt_count == 0
    assert state["content"] == no_context_reply_for(MESSAGE)
    revision.assert_not_awaited()
    audit.assert_awaited_once()


@pytest.mark.asyncio
async def test_llm_verify_revision_remains_routable_through_same_executor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    critic = AsyncMock(
        side_effect=[
            _failed_revision(METHOD_LLM_VERIFY_V1),
            _accepted(METHOD_LLM_VERIFY_V1),
        ]
    )
    revision = AsyncMock(return_value=REVISED)
    _frames, state, audit, _chunk_value = await _run_phase(
        monkeypatch, critic=critic, revision=revision
    )

    observed = state["outcome"]
    assert isinstance(observed, AgentRunOutcome)
    assert observed.critic_revision_count == 1
    assert observed.critic_actions[-1].status == "executed"
    assert state["content"] == REVISED
    revision.assert_awaited_once()
    audit.assert_awaited_once()


def test_p2b_artifact_records_c11_closure_without_mutating_frozen_p2() -> None:
    artifact = json.loads(P2B_ARTIFACT_PATH.read_text(encoding="utf-8"))
    assert artifact["state"] == "PASS"
    assert artifact["case_id"] == "C11-citation-format-only-defect"
    assert artifact["before_status"] == "skipped_unavailable"
    assert artifact["after_status"] == "executed"
    assert artifact["critic_method"] == METHOD_RULES_V1
    assert artifact["recommended_action"] == "REVISE_FROM_EXISTING_EVIDENCE"
    assert artifact["revision_attempts"] == 1
    assert artifact["retrieval_attempts"] == 0
    assert artifact["trajectory_accounted"] is True
    assert artifact["audit_accounted"] is True
    assert artifact["budget_accounted"] is True
    assert artifact["final_boundary_valid"] is True
    assert artifact["safe_outcome"] is True
    assert artifact["default_behavior_changed"] is False
    assert artifact["runtime_rollout"] is False
    assert artifact["ready_to_rerun_p2"] is True
