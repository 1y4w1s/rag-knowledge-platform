"""P2-A7：清扫器按「最后活动时间」判超时，合法长对话不被误杀。

覆盖场景：
- run 创建超过阈值但最后 step 在阈值内 → 不算 stale（长对话存活）；
- run 与最后 step 均超过阈值 → stale；
- 无 step 的旧 run → 回退 run 创建时间判 stale；
- apply 只清真正 stale 的 run，活跃长 run 保持 running（含审计）。
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from app.core.database import SessionLocal
from app.models.agent_run import AgentRun
from app.models.agent_step import AgentStep
from app.models.chat_thread import ChatThread
from app.models.enums import (
    AgentRunMode,
    AgentRunStatus,
    AgentStepStatus,
    ThreadKind,
    ThreadStatus,
)
from app.services.agent.sweeper import apply_stale_agent_runs, scan_stale_agent_runs
from tests._a2a3b2b3_helpers import audit_count, utcnow


async def _seed_run(
    *,
    user_id: uuid.UUID,
    run_id: uuid.UUID,
    created_at: datetime,
    step_created_at: datetime | None = None,
) -> None:
    """直插 run（可选 step），返回后可复用 run_id 断言。"""
    thread_id = uuid.uuid4()
    async with SessionLocal() as db:
        db.add(
            ChatThread(
                id=thread_id,
                thread_kind=ThreadKind.workspace,
                user_id=user_id,
                status=ThreadStatus.active,
            )
        )
        await db.flush()
        db.add(
            AgentRun(
                id=run_id,
                thread_id=thread_id,
                user_id=user_id,
                mode=AgentRunMode.thorough,
                status=AgentRunStatus.running,
                created_at=created_at,
            )
        )
        await db.flush()
        if step_created_at is not None:
            db.add(
                AgentStep(
                    id=uuid.uuid4(),
                    run_id=run_id,
                    step_index=1,
                    tool_name="semantic_search",
                    status=AgentStepStatus.running,
                    created_at=step_created_at,
                )
            )
        await db.commit()


async def test_p2_a7_old_run_with_recent_step_not_stale(
    register_and_login,
) -> None:
    """合法长对话：创建 2 小时但 1 分钟前还有新 step，不应被清扫。"""
    _, user = await register_and_login(prefix="p2-a7-active")
    run_id = uuid.uuid4()
    now = utcnow()
    await _seed_run(
        user_id=uuid.UUID(user["id"]),
        run_id=run_id,
        created_at=now - timedelta(hours=2),
        step_created_at=now - timedelta(minutes=1),
    )

    async with SessionLocal() as db:
        found = await scan_stale_agent_runs(db, now=now)
    assert all(r.id != run_id for r in found)


async def test_p2_a7_old_run_with_old_step_is_stale(
    register_and_login,
) -> None:
    """run 与最后 step 都超过阈值 → 视为 crash/断线残留。"""
    _, user = await register_and_login(prefix="p2-a7-stale")
    run_id = uuid.uuid4()
    now = utcnow()
    await _seed_run(
        user_id=uuid.UUID(user["id"]),
        run_id=run_id,
        created_at=now - timedelta(hours=2),
        step_created_at=now - timedelta(hours=2),
    )

    async with SessionLocal() as db:
        found = await scan_stale_agent_runs(db, now=now)
    assert any(r.id == run_id for r in found)


async def test_p2_a7_old_run_without_steps_falls_back_to_created_at(
    register_and_login,
) -> None:
    """无 step 的旧 run 回退创建时间判定，保持 crash 残留兜底。"""
    _, user = await register_and_login(prefix="p2-a7-nostep")
    run_id = uuid.uuid4()
    now = utcnow()
    await _seed_run(
        user_id=uuid.UUID(user["id"]),
        run_id=run_id,
        created_at=now - timedelta(hours=2),
    )

    async with SessionLocal() as db:
        found = await scan_stale_agent_runs(db, now=now)
    assert any(r.id == run_id for r in found)


async def test_p2_a7_apply_spares_active_long_run(
    register_and_login,
) -> None:
    """apply 只标记真正 stale 的 run；活跃长 run 保持 running 且无审计。"""
    _, user = await register_and_login(prefix="p2-a7-apply")
    user_id = uuid.UUID(user["id"])
    active_id = uuid.uuid4()
    stale_id = uuid.uuid4()
    now = utcnow()
    await _seed_run(
        user_id=user_id,
        run_id=active_id,
        created_at=now - timedelta(hours=2),
        step_created_at=now - timedelta(minutes=1),
    )
    await _seed_run(
        user_id=user_id,
        run_id=stale_id,
        created_at=now - timedelta(hours=2),
        step_created_at=now - timedelta(hours=2),
    )

    async with SessionLocal() as db:
        marked = await apply_stale_agent_runs(db, dry_run=False, now=now)
        assert marked >= 1
        active = await db.get(AgentRun, active_id)
        stale = await db.get(AgentRun, stale_id)
        assert active.status == AgentRunStatus.running
        assert stale.status == AgentRunStatus.failed

    assert await audit_count("agent_run.sweep_marked_failed", active_id) == 0
    assert await audit_count("agent_run.sweep_marked_failed", stale_id) == 1


async def test_p2_a7_threshold_applies_to_last_activity(
    register_and_login,
) -> None:
    """阈值基于最后活动时间：10 分钟前有 step，按 5 分钟阈值 stale、15 分钟阈值存活。"""
    _, user = await register_and_login(prefix="p2-a7-threshold")
    run_id = uuid.uuid4()
    now = utcnow()
    await _seed_run(
        user_id=uuid.UUID(user["id"]),
        run_id=run_id,
        created_at=now - timedelta(hours=2),
        step_created_at=now - timedelta(minutes=10),
    )

    async with SessionLocal() as db:
        found_strict = await scan_stale_agent_runs(db, now=now, stale_minutes=5)
        found_lenient = await scan_stale_agent_runs(db, now=now, stale_minutes=15)
    assert any(r.id == run_id for r in found_strict)
    assert all(r.id != run_id for r in found_lenient)
