"""W9 P1 critic control-plane architecture gates."""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.config import settings
from app.services.agent.runtime import execute_accounted_recovery_step
from app.services.agent.tools.semantic_search import (
    SemanticSearchHit,
    SemanticSearchOutput,
)
from app.services.agent.types import (
    AgentActionKind,
    AgentDecision,
    AgentRunOutcome,
    StepExecution,
)
from app.services.rag.critic import CriticAction, CriticResult, run_critic
from app.services.rag.engine import ChatEngine
from app.services.rag.feedback_attribution import LABEL_UNKNOWN
from app.services.rag.generation import AnswerVerification
from app.services.rag.types import RetrievedChunk

P1_ARTIFACT = (
    Path(__file__).parent
    / "fixtures"
    / "l4_critic"
    / "w9-critic-control-plane-p1.json"
)


def _chunk(content: str) -> RetrievedChunk:
    return RetrievedChunk(
        kb_id=uuid.uuid4(),
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        doc_name="制度.md",
        content=content,
        page_number=1,
        section_title="4.1 培训",
        heading_path="4.1 培训",
        similarity=0.9,
    )


@pytest.mark.asyncio
async def test_llm_critic_is_advisory_and_does_not_generate_revision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "rag_critic_enabled", True)
    monkeypatch.setattr(settings, "rag_critic_mode", "llm")
    calls = {"judgment": 0, "revision": 0}

    async def _judge(*_args, **_kwargs) -> AnswerVerification:
        calls["judgment"] += 1
        return AnswerVerification(
            verified=False,
            issues=("断言缺少证据",),
            degraded=False,
        )

    async def _forbidden_revision(*_args, **_kwargs) -> str | None:
        calls["revision"] += 1
        raise AssertionError("critic must not generate a revision")

    monkeypatch.setattr("app.services.rag.generation.inspect_answer", _judge)
    monkeypatch.setattr(
        "app.services.rag.generation.revise_answer_from_existing_evidence",
        _forbidden_revision,
    )

    result = await run_critic(
        "培训费需要按比例退还[片段1]。",
        [_chunk("员工提前离职时，培训费按比例退还。")],
        "培训费怎么退？",
    )

    assert result.ok is False
    assert result.recommended_action is CriticAction.REVISE_FROM_EXISTING_EVIDENCE
    assert result.corrected is None
    assert result.metadata["critic.issues"] == ["断言缺少证据"]
    assert calls == {"judgment": 1, "revision": 0}


@pytest.mark.asyncio
async def test_deterministic_preflight_blocks_semantic_critic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "rag_critic_enabled", True)
    monkeypatch.setattr(settings, "rag_critic_mode", "llm")

    async def _forbidden_semantic(*_args, **_kwargs) -> AnswerVerification:
        raise AssertionError("deterministic defects must not reach semantic critic")

    monkeypatch.setattr(
        "app.services.rag.generation.inspect_answer", _forbidden_semantic
    )
    result = await run_critic(
        "培训费需要按比例退还[片段9]。",
        [_chunk("员工提前离职时，培训费按比例退还。")],
        "培训费怎么退？",
    )

    assert result.ok is False
    assert result.method == "rules_v1"
    assert result.recommended_action is CriticAction.REVISE_FROM_EXISTING_EVIDENCE


class _Hooks:
    def __init__(self) -> None:
        self.events: list[tuple[str, object]] = []

    async def on_tool_start(self, event: object) -> None:
        self.events.append(("start", event))

    async def on_tool_result(self, event: object) -> None:
        self.events.append(("result", event))

    async def on_agent_budget(self, event: object) -> None:
        self.events.append(("budget", event))


@pytest.mark.asyncio
async def test_recovery_retrieval_uses_canonical_step_and_evidence_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services.agent import runtime

    run_id = uuid.uuid4()
    user_id = uuid.uuid4()
    thread_id = uuid.uuid4()
    kb_id = uuid.uuid4()
    chunk_id = uuid.uuid4()
    document_id = uuid.uuid4()
    hit = SemanticSearchHit(
        chunk_id=chunk_id,
        kb_id=kb_id,
        kb_name="制度库",
        doc_name="制度.md",
        page=3,
        section_title="4.1 培训",
        excerpt="员工提前离职时，培训费按比例退还。",
        score=0.91,
        document_id=document_id,
    )
    output = SemanticSearchOutput(hits=(hit,), retrieval_ms=17)
    captured: dict[str, object] = {}

    async def _execute(*_args, **kwargs) -> StepExecution:
        captured.update(kwargs)
        return StepExecution(
            ok=True,
            summary="1 hit",
            latency_ms=17,
            data=output,
        )

    db_step = SimpleNamespace(id=uuid.uuid4())
    create_step = AsyncMock(return_value=db_step)
    finish_step = AsyncMock()
    tool_audit = AsyncMock()
    update_usage = AsyncMock()
    monkeypatch.setattr(runtime, "_execute_step", _execute)
    monkeypatch.setattr(runtime, "create_agent_step", create_step)
    monkeypatch.setattr(runtime, "finish_agent_step", finish_step)
    monkeypatch.setattr(runtime, "audit_agent_tool_executed", tool_audit)
    monkeypatch.setattr(runtime, "update_agent_run_steps_used", update_usage)
    monkeypatch.setattr(runtime, "audit_agent_recovery_action", AsyncMock())

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
        args={"query": "培训费退还", "kb_ids": [str(kb_id)]},
        reason_code="critic_directed_retrieve",
    )
    hooks = _Hooks()

    db = AsyncMock()
    updated = await execute_accounted_recovery_step(
        db,
        outcome=outcome,
        decision=decision,
        user_id=user_id,
        thread_id=thread_id,
        workspace=MagicMock(),
        tool_scope=MagicMock(),
        hooks=hooks,
    )

    assert updated.steps_used == 1
    assert updated.critic_recovery_count == 1
    assert len(updated.steps) == 1
    record = updated.steps[0]
    assert record.origin == "critic_recovery"
    assert record.attempt_count == 1
    assert record.step_id == db_step.id
    assert record.latency_ms == 17
    assert updated.evidence_state.chunk_ids == (chunk_id,)
    assert updated.evidence_state.document_ids == (document_id,)
    assert record.data.hits[0].kb_id == kb_id
    assert captured["max_retries"] == 0
    create_step.assert_awaited_once()
    finish_step.assert_awaited_once()
    tool_audit.assert_awaited_once()
    update_usage.assert_awaited_once_with(
        db, run_id=run_id, user_id=user_id, steps_used=1
    )
    assert [kind for kind, _ in hooks.events] == ["start", "result", "budget"]


@pytest.mark.asyncio
async def test_fast_chat_critic_sees_and_publishes_regenerated_final_candidate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = ChatEngine(
        MagicMock(),
        user_id=uuid.uuid4(),
        message="培训费怎么退？",
        kb_id=uuid.uuid4(),
    )
    chunk = _chunk("员工提前离职时，培训费按比例退还。")
    responses = iter(
        [
            "培训费需要退还。",
            "培训费需要按比例退还[片段1]。",
        ]
    )
    critic_inputs: list[str] = []

    async def _load_history() -> None:
        engine.history = None
        engine.retrieval_query = engine.message

    async def _retrieve() -> list[RetrievedChunk]:
        engine.chunks = [chunk]
        return engine.chunks

    async def _save(_content: str, _citations: list) -> uuid.UUID:
        return uuid.uuid4()

    async def _tokens(_messages: list[dict[str, str]]):
        for char in next(responses):
            yield char

    async def _critic(answer: str, *_args) -> CriticResult:
        critic_inputs.append(answer)
        return CriticResult(
            ok=True,
            claims=(),
            label=LABEL_UNKNOWN,
            rationale="accepted",
        )

    async def _cache_get(*_args):
        return {
            "content": "stale cached draft",
            "citations": [],
            "message_id": str(uuid.uuid4()),
        }

    async def _cache_set(*_args):
        return None

    monkeypatch.setattr(engine, "_load_history", _load_history)
    monkeypatch.setattr(engine, "_retrieve", _retrieve)
    monkeypatch.setattr(engine, "_save", _save)
    monkeypatch.setattr("app.services.rag.engine.stream_deepseek_tokens", _tokens)
    monkeypatch.setattr("app.services.rag.critic.run_critic", _critic)
    monkeypatch.setattr("app.services.rag.engine.output_safety_check", lambda _t: (True, []))
    monkeypatch.setattr("app.services.rag.engine.degradation_requires_llm", lambda _d: True)
    monkeypatch.setattr("app.services.rag.engine.has_available_chat_provider_key", lambda: True)
    monkeypatch.setattr("app.services.rag.engine.llm_response_cache.get", _cache_get)
    monkeypatch.setattr("app.services.rag.engine.llm_response_cache.set", _cache_set)
    monkeypatch.setattr(settings, "rag_critic_enabled", True)
    monkeypatch.setattr(settings, "rag_critic_mode", "rules")
    monkeypatch.setattr(settings, "self_verify_enabled", False)
    monkeypatch.setattr(settings, "citation_density_check_enabled", True)
    monkeypatch.setattr(settings, "citation_density_regenerate_limit", 1)

    events = [event async for event in engine.stream()]
    final = "培训费需要按比例退还[片段1]。"

    assert critic_inputs == [final]
    assert "".join(
        event["data"]["text"]
        for event in events
        if event["event"] == "token"
    ) == final


@pytest.mark.asyncio
async def test_recovery_budget_exhaustion_is_audited_without_dispatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services.agent import runtime

    recovery_audit = AsyncMock()
    execute = AsyncMock()
    monkeypatch.setattr(runtime, "audit_agent_recovery_action", recovery_audit)
    monkeypatch.setattr(runtime, "_execute_step", execute)
    run_id = uuid.uuid4()
    user_id = uuid.uuid4()
    outcome = AgentRunOutcome(
        run_id=run_id,
        steps_used=2,
        max_steps=2,
        capped=True,
        timed_out=False,
        steps=(),
        deadline_monotonic=time.monotonic() + 30,
    )
    decision = AgentDecision(
        action=AgentActionKind.tool,
        tool_name="semantic_search",
        args={"query": "补证据"},
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

    assert updated.steps_used == outcome.steps_used
    assert updated.critic_actions[-1].status == "budget_exhausted"
    execute.assert_not_awaited()
    recovery_audit.assert_awaited_once()
    assert recovery_audit.await_args.kwargs["status"] == "budget_exhausted"
    assert recovery_audit.await_args.kwargs["budget_before"] == 0
    assert recovery_audit.await_args.kwargs["budget_after"] == 0


def test_p1_artifact_freezes_zero_tolerance_architecture_metrics() -> None:
    artifact = json.loads(P1_ARTIFACT.read_text(encoding="utf-8"))

    assert artifact["base_sha"] == "cc3321e7a768426f7d7d665984dfbcba6140bf9f"
    assert artifact["state"] == "PASS"
    verdicts = artifact["verdicts"]
    assert verdicts["single_orchestration_owner"] == "YES"
    assert verdicts["critic_autonomous_recovery"] == "NO"
    assert verdicts["final_output_boundary"] == "VALID"
    assert verdicts["trajectory_accounting"] == "COMPLETE"
    assert verdicts["evidence_state_accounting"] == "COMPLETE"
    assert verdicts["audit_accounting"] == "COMPLETE"
    assert verdicts["budget_accounting"] == "COMPLETE"
    assert verdicts["scope_provenance"] == "VALID"
    assert verdicts["default_behavior_preserved"] == "YES"
    assert verdicts["ready_for_real_local_measurement"] == "NO"
    metrics = artifact["architecture_metrics"]
    assert metrics.pop("orchestration_owner_count") == 1
    assert metrics.pop("trajectory_accounting_complete") is True
    assert metrics.pop("final_output_boundary_valid") is True
    assert set(metrics.values()) == {0}
    assert len(artifact["control_plane_cases"]) == 12
    assert all(case["test_refs"] for case in artifact["control_plane_cases"])
    for case in artifact["control_plane_cases"]:
        for test_ref in case["test_refs"]:
            test_file = test_ref.split("::", 1)[0]
            assert (Path(__file__).parent / test_file).is_file()
