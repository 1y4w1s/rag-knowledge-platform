"""G1 W3 · LLM 提示重规划测试（planners + config 接线）。

覆盖实施文档 §9.3 六条用例：invalid_args 重规划 + 审计、预算耗尽、
denied 不重规划、SafetyFrame 仍拦截重规划产物、同调用判重 guard、
cursor 按缓存顺序消费（替换步插入后不跳步）。
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.audit_log import AuditLog
from app.services.agent.planners import LLMPlanner, SafetyFrame
from app.services.agent.runtime import run_react_loop
from app.services.agent.tools.get_chunk_excerpt import (
    GetChunkExcerptToolResult,
)
from app.services.agent.tools.scope import FORBIDDEN_KB_SUMMARY, AgentToolScope
from app.services.agent.tools.semantic_search import (
    SemanticSearchHit,
    SemanticSearchOutput,
    SemanticSearchToolResult,
)
from app.services.agent.types import (
    AgentStepRecord,
    ToolCallPlan,
    ToolFailure,
    ToolFailureKind,
)
from app.services.rag.thread_persistence import create_workspace_thread
from app.services.workspace.scope import WorkspaceKind, WorkspaceScope

_QUERY = "请说明公司考勤制度的请假流程"
_CHUNK_ID = "11111111-1111-1111-1111-111111111111"


@pytest.fixture(autouse=True)
def _disable_retry_backoff(monkeypatch: pytest.MonkeyPatch) -> None:
    """单测 infra：关闭指数退避，避免失败用例等待约 1s。"""
    monkeypatch.setattr(settings, "retry_max_attempts", 0)


@pytest.fixture(autouse=True)
def _set_chat_provider_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """LLM 重规划路径固定主 provider key，避免无 key CI 下提前走 no_key fallback。"""
    monkeypatch.setattr(settings, "chat_provider", "deepseek")
    monkeypatch.setattr(settings, "deepseek_api_key", "sk-ds-test")
    monkeypatch.setattr(settings, "tongyi_api_key", "")


def _personal_workspace(user_id: UUID) -> WorkspaceScope:
    return WorkspaceScope(kind=WorkspaceKind.personal, user_id=user_id, org_id=None)


async def _create_personal_thread(user_id: UUID) -> UUID:
    async with SessionLocal() as db:
        thread = await create_workspace_thread(
            db, user_id=user_id, workspace_kind=WorkspaceKind.personal,
            workspace_org_id=None, department_id=None,
        )
        await db.commit()
        return thread.id


def _llm_planner() -> LLMPlanner:
    frame = SafetyFrame(_QUERY)
    return LLMPlanner(_QUERY, safety_frame=frame, tool_specs=frame.all_tool_specs())


def _mock_complete_chat(monkeypatch: pytest.MonkeyPatch, *responses: str) -> AsyncMock:
    mock = AsyncMock(side_effect=[(r, None) for r in responses])
    monkeypatch.setattr(
        "app.services.rag.chat_llm.complete_chat_with_usage",
        mock,
    )
    return mock


def _semantic_result(*, score: float = 0.9) -> SemanticSearchToolResult:
    hit = SemanticSearchHit(
        chunk_id=uuid.uuid4(), kb_id=uuid.uuid4(), kb_name="制度库",
        doc_name="考勤手册.md", page=1, section_title="请假流程",
        excerpt="员工请假需提前申请", score=score,
    )
    return SemanticSearchToolResult(
        ok=True,
        data=SemanticSearchOutput(hits=(hit,), retrieval_ms=1),
        summary="命中 1 条",
    )


async def _call_next(planner: LLMPlanner, *, step_index: int = 1, steps_used: int = 0,
                     prior_steps: tuple[AgentStepRecord, ...] = ()) -> ToolCallPlan | None:
    return await planner.next_tool_call(
        query=_QUERY, step_index=step_index, steps_used=steps_used,
        max_steps=5, prior_steps=prior_steps,
    )


@pytest.mark.asyncio
async def test_llm_replan_after_invalid_args(
    register_and_login,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """get_chunk_excerpt invalid_args → replan 为 semantic_search，审计 +1。"""
    _, user = await register_and_login(prefix="g1-replan-invalid")
    user_id = UUID(user["id"])
    thread_id = await _create_personal_thread(user_id)

    mock_llm = _mock_complete_chat(
        monkeypatch,
        f'[{{"tool_name": "get_chunk_excerpt", "args": {{"chunk_id": "{_CHUNK_ID}"}}}}]',
        '[{"tool_name": "semantic_search", "args": {"query": "请假流程"}}]',
    )
    monkeypatch.setattr(
        "app.services.agent.runtime.run_get_chunk_excerpt",
        AsyncMock(
            return_value=GetChunkExcerptToolResult(
                ok=False,
                data=None,
                summary="缺少 chunk_id",
            )
        ),
    )
    monkeypatch.setattr(
        "app.services.agent.runtime.run_semantic_search",
        AsyncMock(return_value=_semantic_result()),
    )
    planner = _llm_planner()

    async with SessionLocal() as db:
        outcome = await run_react_loop(
            db,
            user_id=user_id,
            thread_id=thread_id,
            query=_QUERY,
            workspace=_personal_workspace(user_id),
            tool_scope=AgentToolScope(),
            planner=planner,
            max_steps=5,
        )
        await db.commit()

    assert [s.tool_name for s in outcome.steps] == [
        "get_chunk_excerpt",
        "semantic_search",
    ]
    assert outcome.steps_used == 2
    assert outcome.tool_replanned == 1
    assert mock_llm.await_count == 2

    second_prompt = mock_llm.await_args_list[1].args[0][0]["content"]
    assert "上一轮工具调用失败：get_chunk_excerpt" in second_prompt
    assert "请选择其他工具或修正参数" in second_prompt

    async with SessionLocal() as db:
        rows = (await db.execute(select(AuditLog).where(
            AuditLog.action == "agent.tool_replanned",
            AuditLog.resource_id == outcome.run_id,
        ))).scalars().all()
    assert len(rows) == 1
    row = rows[0]
    assert row.details["tool"] == "get_chunk_excerpt"
    assert row.details["kind"] == "invalid_args"
    assert row.details["fallback_tool"] == "semantic_search"
    assert row.details["replan_count"] == 1
    assert "query" not in row.details


@pytest.mark.asyncio
async def test_replan_budget_exhausted(
    register_and_login,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """agent_max_tool_replans=1：第二次失败不再触发 LLM 重规划。"""
    monkeypatch.setattr(settings, "agent_max_tool_replans", 1)
    _, user = await register_and_login(prefix="g1-replan-budget")
    user_id = UUID(user["id"])
    thread_id = await _create_personal_thread(user_id)

    mock_llm = _mock_complete_chat(
        monkeypatch,
        '[{"tool_name": "semantic_search", "args": {"query": "请假流程"}}]',
        f'[{{"tool_name": "get_chunk_excerpt", "args": {{"chunk_id": "{_CHUNK_ID}"}}}}]',
    )
    monkeypatch.setattr(
        "app.services.agent.runtime.run_semantic_search",
        AsyncMock(
            return_value=SemanticSearchToolResult(
                ok=False,
                data=None,
                summary="参数非法",
            )
        ),
    )
    monkeypatch.setattr(
        "app.services.agent.runtime.run_get_chunk_excerpt",
        AsyncMock(
            return_value=GetChunkExcerptToolResult(
                ok=False,
                data=None,
                summary="缺少 chunk_id",
            )
        ),
    )
    planner = _llm_planner()

    async with SessionLocal() as db:
        outcome = await run_react_loop(
            db,
            user_id=user_id,
            thread_id=thread_id,
            query=_QUERY,
            workspace=_personal_workspace(user_id),
            tool_scope=AgentToolScope(),
            planner=planner,
            max_steps=5,
        )
        await db.commit()

    assert [s.tool_name for s in outcome.steps] == [
        "semantic_search",
        "get_chunk_excerpt",
    ]
    assert outcome.steps_used == 2
    assert outcome.tool_replanned == 1
    assert mock_llm.await_count == 2


@pytest.mark.asyncio
async def test_replan_never_for_denied(
    register_and_login,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """越权失败不触发 LLM 重规划，agent.tool_denied 审计保留。"""
    _, user = await register_and_login(prefix="g1-replan-denied")
    user_id = UUID(user["id"])
    thread_id = await _create_personal_thread(user_id)

    mock_llm = _mock_complete_chat(
        monkeypatch,
        '[{"tool_name": "semantic_search", "args": {"query": "请假流程"}}]',
    )
    monkeypatch.setattr(
        "app.services.agent.runtime.run_semantic_search",
        AsyncMock(
            return_value=SemanticSearchToolResult(
                ok=False,
                data=None,
                summary=FORBIDDEN_KB_SUMMARY,
            )
        ),
    )
    planner = _llm_planner()

    async with SessionLocal() as db:
        outcome = await run_react_loop(
            db,
            user_id=user_id,
            thread_id=thread_id,
            query=_QUERY,
            workspace=_personal_workspace(user_id),
            tool_scope=AgentToolScope(),
            planner=planner,
            max_steps=5,
        )
        await db.commit()

    assert outcome.steps_used == 1
    assert outcome.tool_replanned == 0
    assert mock_llm.await_count == 1

    async with SessionLocal() as db:
        denied = (await db.execute(select(AuditLog).where(
            AuditLog.action == "agent.tool_denied",
            AuditLog.resource_id == outcome.run_id,
        ))).scalars().all()
        replanned = (await db.execute(select(AuditLog).where(
            AuditLog.action == "agent.tool_replanned",
            AuditLog.resource_id == outcome.run_id,
        ))).scalars().all()
    assert len(denied) == 1
    assert replanned == []


@pytest.mark.asyncio
async def test_replan_preserves_safety_frame(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """重规划产物含写 tool / 关闭中的 web_search → 仍被 SafetyFrame.validate 拒绝。"""
    monkeypatch.setattr(settings, "external_tools_enabled", False)
    mock_llm = _mock_complete_chat(
        monkeypatch,
        '[{"tool_name": "semantic_search", "args": {"query": "请假流程"}}]',
        '['
        '{"tool_name": "generate_faq_draft", "args": {"kb_id": "kb-1", "filename": "x.md"}},'
        '{"tool_name": "web_search", "args": {"query": "请假流程"}}'
        ']',
    )
    planner = _llm_planner()

    first = await _call_next(planner)
    assert first is not None
    assert first.tool_name == "semantic_search"

    failure = ToolFailure(
        kind=ToolFailureKind.invalid_args,
        tool_name="semantic_search",
        summary="参数非法",
    )
    prior_steps = (
        AgentStepRecord(
            step_index=1,
            tool_name="semantic_search",
            args={"query": "请假流程"},
            ok=False,
            summary="参数非法",
            latency_ms=0,
        ),
    )
    replanned = await planner.replan_after_failure(
        query=_QUERY,
        step_index=2,
        steps_used=1,
        max_steps=5,
        prior_steps=prior_steps,
        failure=failure,
    )

    assert planner._is_fallback is True
    assert planner.fallback_reason == "safety_violation"
    assert replanned is not None
    assert replanned.tool_name == "semantic_search"
    assert mock_llm.await_count == 2


@pytest.mark.asyncio
async def test_replan_same_call_guard(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """新计划与失败步同工具同 args → replan_after_failure 返回 None。"""
    same_plan = '[{"tool_name": "semantic_search", "args": {"query": "请假流程"}}]'
    mock_llm = _mock_complete_chat(monkeypatch, same_plan, same_plan)
    planner = _llm_planner()

    first = await _call_next(planner)
    assert first is not None
    assert first.args == {"query": "请假流程"}

    failure = ToolFailure(
        kind=ToolFailureKind.infra,
        tool_name="semantic_search",
        summary="服务不可用",
    )
    prior_steps = (
        AgentStepRecord(
            step_index=1,
            tool_name="semantic_search",
            args={"query": "请假流程"},
            ok=False,
            summary="服务不可用",
            latency_ms=0,
        ),
    )
    replanned = await planner.replan_after_failure(
        query=_QUERY,
        step_index=2,
        steps_used=1,
        max_steps=5,
        prior_steps=prior_steps,
        failure=failure,
    )

    assert replanned is None
    assert mock_llm.await_count == 2
    assert planner._failure_context is failure


@pytest.mark.asyncio
async def test_llm_plan_cursor_after_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """插入替换步后 LLMPlanner 仍按 cursor 消费原始缓存，不跳步。"""
    mock_llm = _mock_complete_chat(
        monkeypatch,
        '['
        '{"tool_name": "semantic_search", "args": {"query": "请假流程"}},'
        f'{{"tool_name": "get_chunk_excerpt", "args": {{"chunk_id": "{_CHUNK_ID}"}}}}'
        ']',
    )
    planner = _llm_planner()

    first = await _call_next(planner, step_index=1)
    # 模拟 runtime 在第 2 步插入了等价替换步
    second = await _call_next(planner, step_index=3, steps_used=2)
    third = await _call_next(planner, step_index=4, steps_used=3)

    assert first is not None
    assert first.tool_name == "semantic_search"
    assert second is not None
    assert second.tool_name == "get_chunk_excerpt"
    assert second.args["chunk_id"] == _CHUNK_ID
    assert third is None
    assert mock_llm.await_count == 1
