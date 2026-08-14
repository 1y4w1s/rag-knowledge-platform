"""A-M1 · LLM Planner 审计链路 + _planner_with_retrieval_query 单元测试。

覆盖（AGENTS.md §验收口径 · design doc §5）：
1. 审计函数写入 audit_logs 表（action 含 agent.llm_plan_fallback / success）
2. _planner_with_retrieval_query 当 planner=LLMPlanner 时走工厂重建
3. _stream_agent_core 的 isinstance(planner, LLMPlanner) 分支正确发审计事件
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.audit_log import AuditLog
from app.services.agent.planners import (
    LLMPlanner,
    SafetyFrame,
    ThoroughReadPlanner,
)
from app.services.agent.stream import (
    _planner_with_retrieval_query,
    _stream_agent_core,
)
from app.services.agent.tools.registry import ReadOnlyToolName
from app.services.agent.types import AgentRunOutcome, ParseResult, ToolCallPlan
from app.models.user import User
from app.services.auth.password import hash_password
from app.services.audit.agent import (
    audit_llm_plan_fallback,
    audit_llm_plan_success,
)

pytestmark = pytest.mark.asyncio


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #


async def _latest_audit_log(action: str) -> AuditLog | None:
    async with SessionLocal() as db:
        stmt = (
            select(AuditLog)
            .where(AuditLog.action == action)
            .order_by(AuditLog.created_at.desc())
            .limit(1)
        )
        return await db.scalar(stmt)


# --------------------------------------------------------------------------- #
# 1. 审计函数直接测试（design doc §5.2 §5.3 — 验证 DB 写入）
# --------------------------------------------------------------------------- #


async def _insert_test_user() -> User:
    """直插 users 表一行（commit 持久化），返回 FK 可用的 user 对象。"""
    async with SessionLocal() as db:
        user = User(
            id=uuid.uuid4(),
            email=f"a1-{uuid.uuid4().hex[:8]}@example.com",
            username=f"a1{uuid.uuid4().hex[:8]}"[:32],
            password_hash=hash_password("Test123!@"),
            account_type="personal",
        )
        db.add(user)
        await db.commit()
        return user


async def test_audit_llm_plan_fallback_writes_log() -> None:
    """audit_llm_plan_fallback → audit_logs 写入 action=agent.llm_plan_fallback。"""
    user = await _insert_test_user()
    run_id = uuid.uuid4()

    async with SessionLocal() as db:
        await audit_llm_plan_fallback(
            db,
            actor_user_id=user.id,
            run_id=run_id,
            reason="empty_output",
            llm_raw='[{"tool_name": "nonexistent", "args": {}}]',
        )
        await db.commit()

    row = await _latest_audit_log("agent.llm_plan_fallback")
    assert row is not None
    assert row.actor_user_id == user.id
    assert row.resource_type == "agent_run"
    assert row.resource_id == run_id
    assert row.details["reason"] == "empty_output"
    assert "llm_raw_snippet" in row.details
    assert len(row.details["llm_raw_snippet"]) <= 500


async def test_audit_llm_plan_success_writes_log() -> None:
    """audit_llm_plan_success → audit_logs 写入 action=agent.llm_plan_success。"""
    user = await _insert_test_user()
    run_id = uuid.uuid4()

    async with SessionLocal() as db:
        await audit_llm_plan_success(
            db,
            actor_user_id=user.id,
            run_id=run_id,
            tool_count=3,
            llm_raw='[{"tool_name": "semantic_search", "args": {"query": "test"}}]',
        )
        await db.commit()

    row = await _latest_audit_log("agent.llm_plan_success")
    assert row is not None
    assert row.actor_user_id == user.id
    assert row.resource_type == "agent_run"
    assert row.resource_id == run_id
    assert row.details["tool_count"] == 3
    assert "llm_raw_snippet" in row.details


async def test_audit_llm_plan_fallback_without_llm_raw() -> None:
    """llm_raw 为 None 时 metadata 不含 llm_raw_snippet。"""
    user = await _insert_test_user()
    run_id = uuid.uuid4()

    async with SessionLocal() as db:
        await audit_llm_plan_fallback(
            db,
            actor_user_id=user.id,
            run_id=run_id,
            reason="llm_error",
            llm_raw=None,
        )
        await db.commit()

    row = await _latest_audit_log("agent.llm_plan_fallback")
    assert row is not None
    assert "llm_raw_snippet" not in row.details
    assert row.details["reason"] == "llm_error"


# --------------------------------------------------------------------------- #
# 2. _planner_with_retrieval_query 单元测试（design doc §5.2）
# --------------------------------------------------------------------------- #


async def test_planner_with_retrieval_llm_planner() -> None:
    """LLMPlanner 入 → 走 LLMPlannerFactory.create，返回重建后的新 planner。"""
    safety_frame = SafetyFrame("对比公司考勤制度和请假流程")
    tool_specs = safety_frame.all_tool_specs()
    original = LLMPlanner(
        "对比公司考勤制度和请假流程",
        safety_frame=safety_frame,
        tool_specs=tool_specs,
    )

    # 用复杂查询确保触发了工厂的 LLM 路径
    result = _planner_with_retrieval_query(
        original,
        "请对比公司的考勤制度和年假规定",
    )

    # 不是原对象 → 说明经过了工厂重建
    assert result is not original
    # 工厂产出实现 ToolPlanner Protocol
    assert isinstance(result, (LLMPlanner, ThoroughReadPlanner))


async def test_planner_with_retrieval_thorough_planner() -> None:
    """ThoroughReadPlanner 入 → 走 create_tool_planner，返回新 ThoroughReadPlanner。"""
    original = ThoroughReadPlanner("餐补多少")
    result = _planner_with_retrieval_query(original, "餐补多少")
    assert result is not original
    assert isinstance(result, ThoroughReadPlanner)


async def test_planner_with_retrieval_default_kb_id_preserved() -> None:
    """LLMPlanner 的 default_kb_id 经工厂重建后被保留。"""
    kb_id = uuid.uuid4()
    safety_frame = SafetyFrame("对比公司考勤制度和请假流程", default_kb_id=kb_id)
    tool_specs = safety_frame.all_tool_specs()
    original = LLMPlanner(
        "对比公司考勤制度和请假流程",
        safety_frame=safety_frame,
        tool_specs=tool_specs,
        default_kb_id=kb_id,
    )
    result = _planner_with_retrieval_query(
        original,
        "请对比公司的考勤制度和年假规定",
    )
    assert result is not original
    # ThoroughReadPlanner 也有 _default_kb_id
    if hasattr(result, "default_kb_id"):
        assert result.default_kb_id == kb_id
    elif hasattr(result, "_default_kb_id"):
        assert result._default_kb_id == kb_id


# --------------------------------------------------------------------------- #
# 3. _stream_agent_core 审计调用测试（design doc §5.4 §5.5）
# --------------------------------------------------------------------------- #


async def _noop_gen(*args, **kwargs):
    """空 async generator：替换 _stream_generation_phase 使 mock 可被 async for 消费。"""
    if False:
        yield


async def test_stream_agent_core_calls_fallback_audit() -> None:
    """LLM planner fallback → _stream_agent_core 触发 audit_llm_plan_fallback。"""
    user_id = uuid.uuid4()
    thread_id = uuid.uuid4()
    run_id = uuid.uuid4()

    # 准备 LLMPlanner（fallback 状态）
    safety_frame = SafetyFrame("对比公司考勤制度和请假流程")
    tool_specs = safety_frame.all_tool_specs()
    planner = LLMPlanner(
        "对比公司考勤制度和请假流程",
        safety_frame=safety_frame,
        tool_specs=tool_specs,
    )
    planner.fallback_reason = "empty_output"
    planner.last_llm_raw = ""
    planner._cached_plan = ParseResult(ok=False, error="empty_output", llm_raw="")

    outcome = AgentRunOutcome(
        run_id=run_id,
        steps_used=1,
        max_steps=5,
        capped=False,
        timed_out=False,
        steps=(),
    )

    with (
        patch("app.services.agent.stream.inc_chats_total"),
        patch(
            "app.services.agent.stream.prepare_multi_turn_query",
            return_value=([], "对比公司考勤制度和请假流程"),
        ),
        patch(
            "app.services.agent.stream._planner_with_retrieval_query",
            side_effect=lambda p, q: p,
        ),
        patch(
            "app.services.agent.stream.run_react_loop",
            return_value=outcome,
        ),
        patch(
            "app.services.agent.stream.prepare_agent_generation",
            return_value=MagicMock(citations=[]),
        ),
        patch(
            "app.services.agent.stream._stream_generation_phase",
            side_effect=_noop_gen,
        ),
        patch(
            "app.services.agent.stream._finalize_agent_turn",
            new_callable=AsyncMock,
        ),
        patch(
            "app.services.agent.stream.audit_llm_plan_fallback",
            new_callable=AsyncMock,
        ) as mock_fallback,
        patch(
            "app.services.agent.stream.audit_llm_plan_success",
            new_callable=AsyncMock,
        ) as mock_success,
    ):
        async with SessionLocal() as db:
            _ = [
                event
                async for event in _stream_agent_core(
                    db,
                    user_id=user_id,
                    message="对比公司考勤制度",
                    thread_id=thread_id,
                    workspace=MagicMock(),
                    tool_scope=MagicMock(),
                    planner=planner,
                    org_scope=None,
                    workspace_mode=True,
                    thread=MagicMock(),
                    user_message_id=uuid.uuid4(),
                    assistant_message_id=uuid.uuid4(),
                    common={},
                )
            ]

    mock_fallback.assert_awaited_once()
    mock_success.assert_not_awaited()

    call_kwargs = mock_fallback.await_args.kwargs
    assert call_kwargs["actor_user_id"] == user_id
    assert call_kwargs["run_id"] == run_id
    assert call_kwargs["reason"] == "empty_output"
    assert call_kwargs["llm_raw"] == ""


async def test_stream_agent_core_calls_success_audit() -> None:
    """LLM planner 成功 → _stream_agent_core 触发 audit_llm_plan_success。"""
    user_id = uuid.uuid4()
    thread_id = uuid.uuid4()
    run_id = uuid.uuid4()

    safety_frame = SafetyFrame("对比公司考勤制度和请假流程")
    tool_specs = safety_frame.all_tool_specs()
    planner = LLMPlanner(
        "对比公司考勤制度和请假流程",
        safety_frame=safety_frame,
        tool_specs=tool_specs,
    )
    planner.fallback_reason = None
    planner.last_llm_raw = (
        '[{"tool_name": "semantic_search", "args": {"query": "test"}}]'
    )
    planner._cached_plan = ParseResult(
        ok=True,
        plan=[
            ToolCallPlan(
                tool_name=ReadOnlyToolName.semantic_search.value,
                args={"query": "test", "kb_ids": ["kb-id"]},
            ),
        ],
        llm_raw='[{"tool_name": "semantic_search", "args": {"query": "test"}}]',
    )

    outcome = AgentRunOutcome(
        run_id=run_id,
        steps_used=1,
        max_steps=5,
        capped=False,
        timed_out=False,
        steps=(),
    )

    with (
        patch("app.services.agent.stream.inc_chats_total"),
        patch(
            "app.services.agent.stream.prepare_multi_turn_query",
            return_value=([], "对比公司考勤制度和请假流程"),
        ),
        patch(
            "app.services.agent.stream._planner_with_retrieval_query",
            side_effect=lambda p, q: p,
        ),
        patch(
            "app.services.agent.stream.run_react_loop",
            return_value=outcome,
        ),
        patch(
            "app.services.agent.stream.prepare_agent_generation",
            return_value=MagicMock(citations=[]),
        ),
        patch(
            "app.services.agent.stream._stream_generation_phase",
            side_effect=_noop_gen,
        ),
        patch(
            "app.services.agent.stream._finalize_agent_turn",
            new_callable=AsyncMock,
        ),
        patch(
            "app.services.agent.stream.audit_llm_plan_fallback",
            new_callable=AsyncMock,
        ) as mock_fallback,
        patch(
            "app.services.agent.stream.audit_llm_plan_success",
            new_callable=AsyncMock,
        ) as mock_success,
    ):
        async with SessionLocal() as db:
            _ = [
                event
                async for event in _stream_agent_core(
                    db,
                    user_id=user_id,
                    message="对比公司考勤制度",
                    thread_id=thread_id,
                    workspace=MagicMock(),
                    tool_scope=MagicMock(),
                    planner=planner,
                    org_scope=None,
                    workspace_mode=True,
                    thread=MagicMock(),
                    user_message_id=uuid.uuid4(),
                    assistant_message_id=uuid.uuid4(),
                    common={},
                )
            ]

    mock_success.assert_awaited_once()
    mock_fallback.assert_not_awaited()

    call_kwargs = mock_success.await_args.kwargs
    assert call_kwargs["actor_user_id"] == user_id
    assert call_kwargs["run_id"] == run_id
    assert call_kwargs["tool_count"] == 1  # cached_plan 含 1 步 tool
