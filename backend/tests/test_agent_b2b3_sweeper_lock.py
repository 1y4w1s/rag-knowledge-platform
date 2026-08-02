"""阶段 1 序 1.5 验收（B2 + B3）：清扫器 + 审批过期 · 分布式锁 + 锁泄漏。

对应 `docs/tasks/audit-a2a3b2b3-agent-write-boundaries.md`；吸收 T4 H2/H6/H8 与
P1-03/07/09 缺陷项。A2/A3 见 `test_agent_a2a3b2b3.py`。全部用例离线可跑。
"""

from __future__ import annotations

import time
import uuid
from datetime import timedelta
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.agent_run import AgentRun
from app.models.agent_step import AgentStep
from app.models.chat_thread import ChatThread
from app.models.enums import (
    AgentRunMode,
    AgentRunStatus,
    AgentStepStatus,
    ApprovalStatus,
    ThreadKind,
    ThreadStatus,
)
from app.services.agent.sweeper import (
    apply_stale_agent_runs,
    run_agent_sweep,
    scan_stale_agent_runs,
)
from app.services.rag.distributed_lock import (
    _registry,
    acquire_lock,
    release_lock,
    reset_lock_registry,
)
from app.services.rag.thread_generation_lock import (
    release_thread_generation_lock,
    reset_thread_generation_locks,
    try_acquire_thread_generation_lock,
)
from tests._a2a3b2b3_helpers import (
    audit_count,
    get_approval,
    insert_approval,
    upload_dir,
    utcnow,
)
from tests.conftest import create_test_kb


APPROVE_URL = "/api/v1/agent/approvals/{approval_id}/resolve"


# ═══════════════════════════════════════════════════════════════════════════
# B2 · 清扫器（run 超时强制 failed） + 审批过期（resolve 惰性 + sweeper 批量）
# ═══════════════════════════════════════════════════════════════════════════


async def test_b2_sweeper_marks_stale_runs_failed(
    client: AsyncClient,
    register_and_login,
) -> None:
    """超时 running run → failed + steps error + 审计；二次清扫幂等 0。"""
    headers, user = await register_and_login(prefix="b2-sweeper")
    user_id = uuid.UUID(user["id"])
    thread_id = uuid.UUID(uuid.uuid4().hex)
    run_id = uuid.UUID(uuid.uuid4().hex)
    step_id = uuid.UUID(uuid.uuid4().hex)
    now = utcnow()

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
                created_at=now - timedelta(hours=2),
            )
        )
        await db.flush()
        db.add(
            AgentStep(
                id=step_id,
                run_id=run_id,
                step_index=1,
                tool_name="semantic_search",
                status=AgentStepStatus.running,
            )
        )
        await db.commit()

    async with SessionLocal() as db:
        found = await scan_stale_agent_runs(db, now=now)
        # 共享开发库可能残留历史 running 行（被杀进程遗留）——只断言包含本测试注入的 run
        assert any(r.id == run_id for r in found)
        marked = await apply_stale_agent_runs(db, dry_run=False, now=now)
        assert marked >= 1
        # 幂等：二次清扫 0
        marked2 = await apply_stale_agent_runs(db, dry_run=False, now=now)
        assert marked2 == 0

    async with SessionLocal() as db:
        run = await db.get(AgentRun, run_id)
        step = await db.get(AgentStep, step_id)
        assert run.status == AgentRunStatus.failed
        assert run.finished_at is not None
        assert step.status == AgentStepStatus.error
    assert await audit_count("agent_run.sweep_marked_failed", run_id) == 1


async def test_b2_resolve_expired_approval_409_and_status_persisted(
    client: AsyncClient,
    register_and_login,
) -> None:
    """P1-03：超 TTL pending 审批 resolve → 409（audit_reason=expired），status 置 expired 并落库。"""
    headers, user = await register_and_login(prefix="b2-expired")
    kb = await create_test_kb(client, headers, user, name="B2 过期库")
    kb_id = uuid.UUID(kb["id"])
    user_id = uuid.UUID(user["id"])
    approval_id = await insert_approval(
        kb_id=kb_id,
        user_id=user_id,
        created_at=utcnow() - timedelta(hours=48),
    )

    resp = await client.post(
        APPROVE_URL.format(approval_id=approval_id),
        headers=headers,
        json={"action": "adopt"},
    )
    assert resp.status_code == 409, resp.text

    approval = await get_approval(approval_id)
    assert approval.status == ApprovalStatus.expired
    assert await audit_count("agent.approval_expired", approval_id) == 1


async def test_b2_sweeper_marks_expired_approvals(
    client: AsyncClient,
    register_and_login,
) -> None:
    """sweeper 批量清理过期 pending 审批（不依赖惰性路径被访问）。"""
    headers, user = await register_and_login(prefix="b2-exp-sweep")
    kb = await create_test_kb(client, headers, user, name="B2 过期清扫库")
    kb_id = uuid.UUID(kb["id"])
    user_id = uuid.UUID(user["id"])
    old_id = await insert_approval(
        kb_id=kb_id,
        user_id=user_id,
        created_at=utcnow() - timedelta(hours=48),
    )
    fresh_id = await insert_approval(kb_id=kb_id, user_id=user_id)

    async with SessionLocal() as db:
        report = await run_agent_sweep(db, dry_run=True, now=utcnow())
        assert report.expired_approvals_found >= 1
        report = await run_agent_sweep(db, dry_run=False, now=utcnow())
        assert report.approvals_marked_expired >= 1

    old = await get_approval(old_id)
    fresh = await get_approval(fresh_id)
    assert old.status == ApprovalStatus.expired
    assert fresh.status == ApprovalStatus.pending
    assert await audit_count("agent.approval_expired", old_id) == 1


async def test_b2_fresh_approval_resolve_still_200(
    client: AsyncClient,
    register_and_login,
    upload_dir,
) -> None:
    """TTL 内 pending 审批照常可采纳（惰性过期不误伤）。"""
    headers, user = await register_and_login(prefix="b2-fresh")
    kb = await create_test_kb(client, headers, user, name="B2 新鲜库")
    kb_id = uuid.UUID(kb["id"])
    user_id = uuid.UUID(user["id"])
    approval_id = await insert_approval(kb_id=kb_id, user_id=user_id)

    resp = await client.post(
        APPROVE_URL.format(approval_id=approval_id),
        headers=headers,
        json={"action": "adopt"},
    )
    assert resp.status_code == 200, resp.text
    approval = await get_approval(approval_id)
    assert approval.status == ApprovalStatus.adopted


# ═══════════════════════════════════════════════════════════════════════════
# B3 · 分布式锁（memory 互斥/TTL · redis SETNX · H6 锁泄漏）
# ═══════════════════════════════════════════════════════════════════════════


@pytest.fixture(autouse=True)
def _isolate_locks() -> None:
    reset_lock_registry()
    reset_thread_generation_locks()
    yield
    reset_lock_registry()
    reset_thread_generation_locks()


async def test_b3_memory_lock_mutex_release_ttl(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "lock_backend", "memory")
    assert await acquire_lock("k-mutex", ttl_seconds=60)
    assert not await acquire_lock("k-mutex", ttl_seconds=60)
    await release_lock("k-mutex")
    assert await acquire_lock("k-mutex", ttl_seconds=60)

    # TTL 过期后可再获取（H6/L28 兜底）
    assert await acquire_lock("k-ttl", ttl_seconds=60)
    _registry["k-ttl"] = (time.monotonic() - 1, "stale")
    assert await acquire_lock("k-ttl", ttl_seconds=60)


async def test_b3_redis_lock_uses_setnx_and_token_delete(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "lock_backend", "redis")
    fake = AsyncMock()
    fake.set.return_value = True
    fake.get.return_value = "tok-1"
    fake.eval.return_value = 1
    fake.delete.return_value = 1

    async def _fake_get_redis():
        return fake

    monkeypatch.setattr("app.core.redis.get_redis", _fake_get_redis)

    assert await acquire_lock("k-redis", ttl_seconds=30, token="tok-1")
    fake.set.assert_awaited_once_with("k-redis", "tok-1", nx=True, ex=30)

    await release_lock("k-redis", "tok-1")
    # 比较删除走 Lua（token 匹配才删）
    assert fake.eval.await_count == 1
    args = fake.eval.await_args.args
    assert args[1] == 1 and args[2] == "k-redis" and args[3] == "tok-1"


async def test_b3_thread_lock_released_on_stream_construction_error(
    client: AsyncClient,
    register_and_login,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """H6：锁获取后构造流抛错（planner 异常）→ 路由释放锁，thread 不永久 409。"""
    headers, user = await register_and_login(prefix="h6-leak")
    kb = await create_test_kb(client, headers, user, name="H6 锁泄漏库")
    kb_id = uuid.UUID(kb["id"])
    resp = await client.post(
        f"/api/v1/knowledge-bases/{kb_id}/threads",
        headers=headers,
        json={"title": "H6 会话"},
    )
    thread_id = uuid.UUID(resp.json()["id"])

    def _boom_planner(*_args, **_kwargs):
        raise ValueError("planner boom")

    monkeypatch.setattr("app.api.kb_threads.create_tool_planner", _boom_planner)
    with pytest.raises(ValueError):
        await client.post(
            f"/api/v1/knowledge-bases/{kb_id}/threads/{thread_id}/chat",
            headers=headers,
            json={"message": "你好", "mode": "thorough"},
        )

    # 异常路径已释放锁 → 可再次获取
    assert await try_acquire_thread_generation_lock(thread_id)
    await release_thread_generation_lock(thread_id)
