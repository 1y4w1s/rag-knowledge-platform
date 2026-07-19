"""agent_run / agent_step 落库 CRUD（G3-0.4 · user_id 隔离）。"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_run import AgentRun
from app.models.agent_step import AgentStep
from app.models.enums import AgentRunMode, AgentRunStatus, AgentStepStatus

DEFAULT_MAX_STEPS = 5


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def create_agent_run(
    db: AsyncSession,
    *,
    thread_id: UUID,
    user_id: UUID,
    max_steps: int = DEFAULT_MAX_STEPS,
    mode: AgentRunMode = AgentRunMode.thorough,
) -> AgentRun:
    """创建 agent_run（status=running · mode 默认 thorough · G4 编辑流传 edit）。"""
    run = AgentRun(
        id=uuid.uuid4(),
        thread_id=thread_id,
        user_id=user_id,
        mode=mode,
        status=AgentRunStatus.running,
        steps_used=0,
        max_steps=max_steps,
    )
    db.add(run)
    await db.flush()
    return run


async def get_agent_run_for_user(
    db: AsyncSession,
    *,
    run_id: UUID,
    user_id: UUID,
) -> AgentRun | None:
    """按 id 取 run；非 owner 返回 None（G3-E10）。"""
    run = await db.get(AgentRun, run_id)
    if run is None or run.user_id != user_id:
        return None
    return run


async def list_agent_steps_for_run(
    db: AsyncSession,
    *,
    run_id: UUID,
    user_id: UUID,
) -> list[AgentStep] | None:
    """列出 run 下 steps（step_index 升序）；run 非 owner 返回 None。"""
    if await get_agent_run_for_user(db, run_id=run_id, user_id=user_id) is None:
        return None
    result = await db.execute(
        select(AgentStep)
        .where(AgentStep.run_id == run_id)
        .order_by(AgentStep.step_index)
    )
    return list(result.scalars().all())


async def create_agent_step(
    db: AsyncSession,
    *,
    run_id: UUID,
    user_id: UUID,
    step_index: int,
    tool_name: str,
    args_json: dict[str, Any] | None = None,
) -> AgentStep | None:
    """新建 step（status=running）；run 须属 user。"""
    if await get_agent_run_for_user(db, run_id=run_id, user_id=user_id) is None:
        return None
    step = AgentStep(
        id=uuid.uuid4(),
        run_id=run_id,
        step_index=step_index,
        tool_name=tool_name,
        args_json=args_json,
        status=AgentStepStatus.running,
    )
    db.add(step)
    await db.flush()
    return step


async def finish_agent_step(
    db: AsyncSession,
    *,
    step_id: UUID,
    user_id: UUID,
    ok: bool,
    result_summary: str,
    latency_ms: int,
    status: AgentStepStatus | None = None,
) -> AgentStep | None:
    """更新 step 结果；step 所属 run 须属 user。"""
    step = await db.get(AgentStep, step_id)
    if step is None:
        return None
    if await get_agent_run_for_user(db, run_id=step.run_id, user_id=user_id) is None:
        return None
    step.ok = ok
    step.result_summary = result_summary
    step.latency_ms = latency_ms
    step.status = status or (AgentStepStatus.done if ok else AgentStepStatus.error)
    db.add(step)
    await db.flush()
    return step


async def update_agent_run_steps_used(
    db: AsyncSession,
    *,
    run_id: UUID,
    user_id: UUID,
    steps_used: int,
) -> AgentRun | None:
    """更新 run 已用步数（agent_budget 同步）。"""
    run = await get_agent_run_for_user(db, run_id=run_id, user_id=user_id)
    if run is None:
        return None
    run.steps_used = steps_used
    db.add(run)
    await db.flush()
    return run


async def finish_agent_run(
    db: AsyncSession,
    *,
    run_id: UUID,
    user_id: UUID,
    status: AgentRunStatus,
    assistant_message_id: UUID | None = None,
) -> AgentRun | None:
    """结束 run（completed / failed / capped）。"""
    run = await get_agent_run_for_user(db, run_id=run_id, user_id=user_id)
    if run is None:
        return None
    run.status = status
    run.finished_at = _utcnow()
    if assistant_message_id is not None:
        run.assistant_message_id = assistant_message_id
    db.add(run)
    await db.flush()
    return run
