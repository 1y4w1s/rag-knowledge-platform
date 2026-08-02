"""A1+B1 合并窗验收：对话写入统一编排（turn_writer）+ run 终态幂等/循环兜底。

覆盖 masterplan §2 主题 A/B 在本窗的验收点：
- 消息列表顺序断言：user 恒在 assistant 之前（P0-10）；
- 断线/异常兜底仍落库：SSE 中途断开 → user 问句 + assistant partial（interrupted）均保留（P1-08）；
- 单一提交契约：user → assistant → run 终态 → 审计 → 一次 commit（P0-06/07/08）；
- run 终态条件更新幂等：重复 finish 不覆盖终态（B1-1 / P0-01）；
- run_react_loop 异常兜底：planner/tool 异常 → run=failed + 未收尾 steps=error 落库（P1-02）；
- 并发 30 流无连接池 TimeoutError（A 主题验收）。
"""

from __future__ import annotations

import asyncio
import uuid
from pathlib import Path

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.agent_run import AgentRun
from app.models.agent_step import AgentStep
from app.models.chat_message import ChatMessage
from app.models.chat_thread import ChatThread
from app.models.enums import (
    AgentRunStatus,
    AgentStepStatus,
    MessageRole,
    MessageStatus,
    ThreadKind,
)
from app.services.agent.runs import (
    create_agent_run,
    finish_agent_run,
)
from app.services.agent.runtime import run_react_loop
from app.services.agent.tools.scope import AgentToolScope
from app.services.agent.types import ToolCallPlan
from app.services.rag.chat import stream_chat_events
from app.services.rag.persistence import list_chat_messages
from app.services.rag.thread_persistence import (
    create_kb_thread,
    create_workspace_thread,
)
from app.services.rag.turn_writer import TurnMessage, finalize_turn
from app.services.workspace.scope import WorkspaceKind, WorkspaceScope
from tests.conftest import create_test_kb
from tests.test_agent_runtime import SequencePlanner
from tests.test_chat import GOLDEN_MD, _chat, _ingest_fixture


def _personal_workspace(user_id: uuid.UUID) -> WorkspaceScope:
    return WorkspaceScope(
        kind=WorkspaceKind.personal,
        user_id=user_id,
        org_id=None,
    )


async def _create_personal_thread(user_id: uuid.UUID) -> uuid.UUID:
    async with SessionLocal() as db:
        thread = await create_workspace_thread(
            db,
            user_id=user_id,
            workspace_kind=WorkspaceKind.personal,
            workspace_org_id=None,
            department_id=None,
        )
        await db.commit()
        return thread.id


@pytest.fixture
def upload_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    return tmp_path


# ── A1 · 消息顺序（P0-10）────────────────────────────────────────────


@pytest.mark.asyncio
async def test_chat_messages_ordered_user_before_assistant(
    client,
    register_and_login,
    upload_dir: Path,
) -> None:
    """P0-10：一轮对话落库后，GET messages user 恒在 assistant 前。"""
    headers, user = await register_and_login(prefix="a1-order")
    kb = await create_test_kb(client, headers, user, name="A1 顺序库")
    kb_id = kb["id"]
    await _ingest_fixture(
        kb_id=uuid.UUID(kb_id),
        user_id=uuid.UUID(user["id"]),
        source=GOLDEN_MD,
        file_type="md",
        upload_dir=upload_dir,
    )

    status, events = await _chat(client, headers, kb_id, "员工年假有几天？")
    assert status == 200
    done = next(data for name, data in events if name == "done")
    assistant_id = done["message_id"]

    resp = await client.get(
        f"/api/v1/knowledge-bases/{kb_id}/messages",
        headers=headers,
    )
    assert resp.status_code == 200
    messages = resp.json()["messages"]
    assert len(messages) == 2
    assert [m["role"] for m in messages] == ["user", "assistant"]
    assert messages[0]["content"] == "员工年假有几天？"
    assert messages[1]["id"] == assistant_id


# ── A1 · 断线兜底（P1-08）───────────────────────────────────────────


@pytest.mark.asyncio
async def test_chat_disconnect_persists_user_and_partial(
    client,
    register_and_login,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """P1-08：SSE 流中途断开（aclose）→ user 问句 + assistant partial 仍落库。"""
    headers, user = await register_and_login(prefix="a1-disconnect")
    user_id = uuid.UUID(user["id"])
    kb = await create_test_kb(client, headers, user, name="A1 断线库")
    kb_id = uuid.UUID(kb["id"])

    # 慢速拒答流：第一帧 token 后挂起，模拟生成中断线
    async def _slow_no_context(_message: str):
        yield "部分回答"
        await asyncio.sleep(3600)

    monkeypatch.setattr(
        "app.services.rag.generation.stream_no_context_reply",
        _slow_no_context,
    )

    async with SessionLocal() as db:
        thread = await create_kb_thread(
            db, kb_id=kb_id, user_id=user_id, title="断线会话"
        )
        await db.commit()
        thread_id = thread.id

        gen = stream_chat_events(
            db,
            kb_id=kb_id,
            user_id=user_id,
            message="测试问题",
            thread_id=thread_id,
        )
        raw = ""
        async for frame in gen:
            raw += frame
            break  # 收到首帧即模拟客户端断开
        await gen.aclose()

    assert "token" in raw
    async with SessionLocal() as db:
        rows = await list_chat_messages(
            db, kb_id=kb_id, user_id=user_id, thread_id=thread_id
        )

    assert [row.role for row in rows] == [MessageRole.user, MessageRole.assistant]
    assert rows[0].content == "测试问题"
    assert rows[0].status == MessageStatus.completed
    assert rows[1].status == MessageStatus.interrupted
    assert rows[1].content == "部分回答"


# ── A1 · 单一提交编排（finalize_turn）────────────────────────────────


@pytest.mark.asyncio
async def test_finalize_turn_single_commit_user_assistant_audit(
    register_and_login,
) -> None:
    """A1：finalize_turn 一次 commit 完成 user → assistant → 审计。"""
    from app.models.audit_log import AuditLog
    from app.services.audit.chat import audit_message_sent
    from functools import partial

    _, user = await register_and_login(prefix="a1-dwc")
    user_id = uuid.UUID(user["id"])
    thread_id = await _create_personal_thread(user_id)
    assistant_message_id = uuid.uuid4()

    async with SessionLocal() as db:
        thread = await db.get(ChatThread, thread_id)
        assert thread is not None
        returned = await finalize_turn(
            db,
            thread=thread,
            user_id=user_id,
            user_msg=TurnMessage(content="问题"),
            assistant_msg=TurnMessage(
                content="回答",
                citations=[{"chunk_id": str(uuid.uuid4())}],
                message_id=assistant_message_id,
            ),
            common={
                "thread_kind": ThreadKind.workspace,
                "kb_id": None,
                "workspace_kind": WorkspaceKind.personal.value,
                "workspace_org_id": None,
                "workspace_department_key": None,
            },
            audit_events=(
                partial(
                    audit_message_sent,
                    thread=thread,
                    actor_user_id=user_id,
                    assistant_message_id=assistant_message_id,
                    citation_count=1,
                    retrieval_ms=12,
                ),
            ),
        )
        assert returned == assistant_message_id

    # 新 session 验证：消息 + 审计同事务可见
    async with SessionLocal() as db:
        rows = (
            await db.execute(
                select(ChatMessage)
                .where(ChatMessage.thread_id == thread_id)
                .order_by(ChatMessage.created_at, ChatMessage.role)
            )
        ).scalars().all()
        audit = (
            await db.execute(
                select(AuditLog)
                .where(AuditLog.action == "chat.message_sent")
                .where(AuditLog.actor_user_id == user_id)
            )
        ).scalars().all()

    assert len(rows) == 2
    assert rows[0].role == MessageRole.user
    assert rows[1].role == MessageRole.assistant
    assert rows[1].id == assistant_message_id
    assert len(audit) == 1


@pytest.mark.asyncio
async def test_finalize_turn_30_concurrent_no_pool_timeout(
    register_and_login,
) -> None:
    """A1：30 路并发 finalize_turn（独立 session）无连接池 TimeoutError。"""
    _, user = await register_and_login(prefix="a1-concur30")
    user_id = uuid.UUID(user["id"])
    threads: list[uuid.UUID] = []
    async with SessionLocal() as db:
        for _ in range(30):
            thread = await create_workspace_thread(
                db,
                user_id=user_id,
                workspace_kind=WorkspaceKind.personal,
                workspace_org_id=None,
                department_id=None,
            )
            threads.append(thread.id)
        await db.commit()

    async def _one(thread_id: uuid.UUID) -> str:
        async with SessionLocal() as db:
            thread = await db.get(ChatThread, thread_id)
            assert thread is not None
            await finalize_turn(
                db,
                thread=thread,
                user_id=user_id,
                user_msg=TurnMessage(content=f"问题-{thread_id}"),
                assistant_msg=TurnMessage(content="回答", citations=[]),
            )
            return str(thread_id)

    try:
        results = await asyncio.wait_for(
            asyncio.gather(*[_one(t) for t in threads]),
            timeout=90,
        )
    except asyncio.TimeoutError:
        pytest.fail("30 路并发 finalize_turn 超时：连接池不足或阻塞")
    assert len(results) == 30


# ── B1 · run 终态幂等（条件更新）─────────────────────────────────────


@pytest.mark.asyncio
async def test_finish_agent_run_idempotent_terminal_not_overwritten(
    register_and_login,
) -> None:
    """B1-1：重复 finish_agent_run 不覆盖已落终态。"""
    _, user = await register_and_login(prefix="b1-idem")
    user_id = uuid.UUID(user["id"])
    thread_id = await _create_personal_thread(user_id)

    async with SessionLocal() as db:
        assistant = ChatMessage(
            id=uuid.uuid4(),
            thread_kind=ThreadKind.workspace,
            kb_id=None,
            user_id=user_id,
            thread_id=thread_id,
            role=MessageRole.assistant,
            content="回答",
            status=MessageStatus.completed,
            workspace_kind=WorkspaceKind.personal.value,
            workspace_org_id=None,
            workspace_department_key=None,
        )
        db.add(assistant)
        await db.commit()
        assistant_id = assistant.id

        run = await create_agent_run(
            db, thread_id=thread_id, user_id=user_id, max_steps=5
        )
        done = await finish_agent_run(
            db,
            run_id=run.id,
            user_id=user_id,
            status=AgentRunStatus.completed,
            assistant_message_id=assistant_id,
        )
        assert done is not None
        assert done.status == AgentRunStatus.completed
        assert done.finished_at is not None

        again = await finish_agent_run(
            db,
            run_id=run.id,
            user_id=user_id,
            status=AgentRunStatus.capped,
        )
        assert again is not None
        assert again.status == AgentRunStatus.completed, "终态不得被覆盖"
        assert again.assistant_message_id == assistant_id, "终态字段不得被覆盖"
        await db.commit()


@pytest.mark.asyncio
async def test_react_loop_exception_converges_failed_run(
    register_and_login,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """P1-02：tool 执行异常 → run_react_loop 兜底 run=failed + 未收尾 steps=error 落库。"""
    _, user = await register_and_login(prefix="b1-fail")
    user_id = uuid.UUID(user["id"])
    thread_id = await _create_personal_thread(user_id)
    planner = SequencePlanner(
        [ToolCallPlan(tool_name="list_knowledge_bases", args={})]
    )

    async def _boom(*_args, **_kwargs):
        raise RuntimeError("planner-tool-故障")

    monkeypatch.setattr(
        "app.services.agent.runtime.run_list_knowledge_bases",
        _boom,
    )

    async with SessionLocal() as db:
        with pytest.raises(RuntimeError, match="planner-tool-故障"):
            await run_react_loop(
                db,
                user_id=user_id,
                thread_id=thread_id,
                query="列一下库",
                workspace=_personal_workspace(user_id),
                tool_scope=AgentToolScope(),
                planner=planner,
                max_steps=5,
            )

    async with SessionLocal() as db:
        run = (
            await db.execute(
                select(AgentRun)
                .where(AgentRun.user_id == user_id)
                .order_by(AgentRun.created_at.desc())
                .limit(1)
            )
        ).scalars().first()
        assert run is not None
        steps = (
            await db.execute(
                select(AgentStep)
                .where(AgentStep.run_id == run.id)
                .order_by(AgentStep.step_index)
            )
        ).scalars().all()

    assert run.status == AgentRunStatus.failed, "异常兜底须收敛 failed"
    assert run.finished_at is not None
    assert steps, "异常前已创建的 step 应保留"
    assert all(step.status == AgentStepStatus.error for step in steps), (
        "未收尾 step 须置 error"
    )
