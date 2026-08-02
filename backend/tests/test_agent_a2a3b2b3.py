"""阶段 1 序 1.5 验收（A2 + A3）：agent 路径 DWC 收敛 · adopt/memory 事务边界 · 写端点纪律。

对应 `docs/tasks/audit-a2a3b2b3-agent-write-boundaries.md`；吸收 T4 C1/H3/H4/H5 与
P1-05/06/07/08 缺陷项。B2/B3（清扫器/审批过期/分布式锁）见 `test_agent_b2b3_sweeper_lock.py`。
全部用例离线可跑（拒答路径无 LLM；adopt 走真实写库 + mock 嵌入）。
"""

from __future__ import annotations

import asyncio
import json
import uuid
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.core.database import SessionLocal
from app.models.agent_approval import AgentApproval
from app.models.agent_run import AgentRun
from app.models.chat_message import ChatMessage
from app.models.document import Document
from app.models.enums import (
    AgentRunStatus,
    ApprovalStatus,
    MessageRole,
    MessageStatus,
    ThreadKind,
)
from app.services.agent.memory import load_active_memories, upsert_memory
from app.services.agent.tools.scope import AgentToolScope
from app.services.rag.thread_persistence import (
    create_kb_thread,
    create_workspace_thread,
)
from app.services.workspace.scope import WorkspaceKind, WorkspaceScope
from tests._a2a3b2b3_helpers import (
    audit_count,
    insert_approval,
    upload_dir,
)
from tests.conftest import create_test_kb
from tests.test_agent_runtime import SequencePlanner


APPROVE_URL = "/api/v1/agent/approvals/{approval_id}/resolve"


# ═══════════════════════════════════════════════════════════════════════════
# A2 · agent 三渲染路径收敛 turn_writer（DWC 单一提交 + 断线兜底 + 终态回填）
# ═══════════════════════════════════════════════════════════════════════════


async def _collect_agent_kb_stream(
    *,
    kb_id: uuid.UUID,
    user_id: uuid.UUID,
    thread_id: uuid.UUID,
    message: str,
    disconnect_after_first: bool = False,
) -> list[str]:
    """直调 stream_agent_kb_events（SequencePlanner 空计划 → 拒答路径，完全离线）。"""
    from app.services.agent.stream import stream_agent_kb_events

    workspace = WorkspaceScope(
        kind=WorkspaceKind.personal,
        user_id=user_id,
        org_id=None,
    )
    tool_scope = AgentToolScope(
        visible_kb_ids=frozenset({kb_id}),
        default_kb_id=kb_id,
    )
    planner = SequencePlanner([None])
    frames: list[str] = []
    async with SessionLocal() as db:
        stream = stream_agent_kb_events(
            db,
            kb_id=kb_id,
            user_id=user_id,
            message=message,
            thread_id=thread_id,
            workspace=workspace,
            tool_scope=tool_scope,
            planner=planner,
        )
        try:
            async for frame in stream:
                frames.append(frame)
                if disconnect_after_first:
                    break
        finally:
            await stream.aclose()
    return frames


async def test_a2_agent_stream_single_commit_and_run_link(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
) -> None:
    """A2 正常路径：done 事件 + user/assistant 一次 commit + run 终态 + assistant_message_id 回填。"""
    headers, user = await register_and_login(prefix="a2-dwc")
    kb = await create_test_kb(client, headers, user, name="A2 收敛库")
    kb_id = uuid.UUID(kb["id"])
    user_id = uuid.UUID(user["id"])

    async with SessionLocal() as db:
        thread = await create_kb_thread(db, kb_id=kb_id, user_id=user_id)
        await db.commit()
        thread_id = thread.id

    frames = await _collect_agent_kb_stream(
        kb_id=kb_id,
        user_id=user_id,
        thread_id=thread_id,
        message="年假有几天？",
    )
    done = next(
        json_ for f in frames if f.startswith("event: done")
        for json_ in [f.split("data: ", 1)[1].strip()]
    )
    done_data = json.loads(done)
    assistant_id = uuid.UUID(done_data["message_id"])
    run_id = uuid.UUID(done_data["agent_run_id"])

    async with SessionLocal() as db:
        rows = (
            await db.execute(
                select(ChatMessage)
                .where(ChatMessage.thread_id == thread_id)
                .order_by(ChatMessage.role)
            )
        ).scalars().all()
        assert len(rows) == 2
        user_row = next(r for r in rows if r.role == MessageRole.user)
        assistant_row = next(r for r in rows if r.role == MessageRole.assistant)
        assert user_row.status == MessageStatus.completed
        assert assistant_row.status == MessageStatus.completed
        assert assistant_row.id == assistant_id
        assert assistant_row.content  # 拒答文案已落库

        run = await db.get(AgentRun, run_id)
        assert run is not None
        assert run.status == AgentRunStatus.completed
        assert run.assistant_message_id == assistant_id

    assert await audit_count("agent.run_completed", run_id) == 1


async def test_a2_agent_stream_disconnect_persists_partial(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
) -> None:
    """A2 断线兜底（P1-08）：首帧后关闭 → user 问句 + interrupted partial 落库，run 终态落库。"""
    headers, user = await register_and_login(prefix="a2-disconnect")
    kb = await create_test_kb(client, headers, user, name="A2 断线库")
    kb_id = uuid.UUID(kb["id"])
    user_id = uuid.UUID(user["id"])

    async with SessionLocal() as db:
        thread = await create_kb_thread(db, kb_id=kb_id, user_id=user_id)
        await db.commit()
        thread_id = thread.id

    frames = await _collect_agent_kb_stream(
        kb_id=kb_id,
        user_id=user_id,
        thread_id=thread_id,
        message="断线测试问题",
        disconnect_after_first=True,
    )
    assert frames  # 至少首帧已发出

    async with SessionLocal() as db:
        rows = (
            await db.execute(
                select(ChatMessage)
                .where(ChatMessage.thread_id == thread_id)
                .order_by(ChatMessage.role)
            )
        ).scalars().all()
        assert len(rows) == 2
        user_row = next(r for r in rows if r.role == MessageRole.user)
        assistant_row = next(r for r in rows if r.role == MessageRole.assistant)
        assert user_row.status == MessageStatus.completed
        # 断线未收到 done → assistant 为 interrupted，且至少保住已生成文本
        assert assistant_row.status == MessageStatus.interrupted
        run = await db.scalar(
            select(AgentRun)
            .where(AgentRun.thread_id == thread_id)
            .order_by(AgentRun.created_at.desc())
            .limit(1)
        )
        assert run is not None
        assert run.status in (AgentRunStatus.completed, AgentRunStatus.failed)
        assert run.assistant_message_id == assistant_row.id


# ═══════════════════════════════════════════════════════════════════════════
# A3 · memory 独立 session（H4/P1-05：不再中途提交主事务）
# ═══════════════════════════════════════════════════════════════════════════


async def test_a3_memory_upsert_independent_session(
    client: AsyncClient,
    register_and_login,
) -> None:
    """主 session 存在未提交写入 → upsert 后主 session rollback：记忆仍在（独立事务已 commit）。"""
    headers, user = await register_and_login(prefix="a3-memory")
    user_id = uuid.UUID(user["id"])

    async with SessionLocal() as db:
        thread = await create_workspace_thread(
            db,
            user_id=user_id,
            workspace_kind=WorkspaceKind.personal,
            workspace_org_id=None,
            department_id=None,
        )
        await db.flush()
        # 主 session 塞一条未提交的 pending 消息（模拟 run 中途）
        db.add(
            ChatMessage(
                thread_kind=ThreadKind.workspace,
                thread_id=thread.id,
                user_id=user_id,
                role=MessageRole.assistant,
                content="",
                status=MessageStatus.pending,
            )
        )
        await db.flush()
        await upsert_memory(db, user_id, "preference", "lang", "en")
        await db.rollback()  # 主事务回滚：pending 消息消失，但记忆不应受影响

    async with SessionLocal() as db:
        memories = await load_active_memories(db, user_id)
        assert any(m.key == "lang" and m.value == "en" for m in memories)
        pending_count = await db.scalar(
            select(ChatMessage).where(ChatMessage.user_id == user_id)
        )
    assert pending_count is None  # 主事务回滚生效


# ═══════════════════════════════════════════════════════════════════════════
# A3 · adopt 事务边界（H5 先 flush 后写盘） + 并发单文档（H3 行锁）
# ═══════════════════════════════════════════════════════════════════════════


async def test_a3_adopt_flush_before_write_file_and_audit(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
) -> None:
    """真实 adopt：resolve 200 → Document 行 + 磁盘文件（commit 后）+ adopted 状态 + 审计。"""
    headers, user = await register_and_login(prefix="a3-adopt")
    kb = await create_test_kb(client, headers, user, name="A3 采纳库")
    kb_id = uuid.UUID(kb["id"])
    user_id = uuid.UUID(user["id"])
    approval_id = await insert_approval(kb_id=kb_id, user_id=user_id)

    resp = await client.post(
        APPROVE_URL.format(approval_id=approval_id),
        headers=headers,
        json={"action": "adopt"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "processing"

    async with SessionLocal() as db:
        approval = await db.get(AgentApproval, approval_id)
        assert approval is not None
        assert approval.status == ApprovalStatus.adopted
        doc = await db.get(Document, approval.document_id)
        assert doc is not None
        assert doc.kb_id == kb_id
        storage = Path(doc.storage_path)
        assert storage.is_file(), "文件应在 DB commit 后写盘"
        assert storage.read_bytes().startswith(b"# FAQ")

    assert await audit_count("agent.approval_adopted", approval_id) == 1


async def test_a3_adopt_concurrent_single_document(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
) -> None:
    """H3 并发 adopt：行锁串行化 → 一 200 一 409，且只产生一个 Document。"""
    headers, user = await register_and_login(prefix="a3-concurrent")
    kb = await create_test_kb(client, headers, user, name="A3 并发库")
    kb_id = uuid.UUID(kb["id"])
    user_id = uuid.UUID(user["id"])
    approval_id = await insert_approval(kb_id=kb_id, user_id=user_id)

    async def _resolve() -> int:
        resp = await client.post(
            APPROVE_URL.format(approval_id=approval_id),
            headers=headers,
            json={"action": "adopt"},
        )
        return resp.status_code

    codes = await asyncio.gather(_resolve(), _resolve())
    assert sorted(codes) == [200, 409]

    async with SessionLocal() as db:
        doc_count = await db.scalar(
            select(func.count())
            .select_from(Document)
            .where(Document.kb_id == kb_id)
        )
        approval = await db.get(AgentApproval, approval_id)
    assert doc_count == 1
    assert approval.status == ApprovalStatus.adopted
