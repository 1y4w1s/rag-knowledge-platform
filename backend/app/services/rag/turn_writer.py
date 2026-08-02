"""A1 · 对话写入统一编排（DWC, Dialog Write Contract）——单一提交。

固定提交顺序：**user 消息 → assistant 消息 → run 终态 → 审计事件 → 一次 db.commit()**。
chat / kb_threads / ask_threads / agent 渲染路径最终都收敛到此入口（本窗先收敛 chat 路径，
agent 三渲染路径由 A2 窗收敛）。

配套语义：
- **断线/异常兜底**（P1-08）：SSE generator 在 try/finally 中调用 finalize_turn，客户端
  断开仍落库；
- **消息顺序契约**（P0-10）：user 恒在 assistant 之前——预提交的 pending assistant 在
  finalize 时刷新 created_at，避免早于 user 造成列表顺序颠倒（列表排序按
  (created_at, role) 二次键，user=0 < assistant=1）；
- **run 终态幂等**（B1-1）：经 finish_agent_run 条件更新（仅 running 可写终态），重复
  finish 不覆盖已落终态。
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat_message import ChatMessage
from app.models.chat_thread import ChatThread
from app.models.enums import AgentRunStatus, MessageRole, MessageStatus
from app.services.agent.runs import finish_agent_run
from app.services.rag.thread_persistence import (
    maybe_autotitle_thread_from_first_message,
    touch_thread,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True, slots=True)
class TurnMessage:
    """一轮对话中的单条消息（finalize_turn 输入）。

    message_id 语义：传入预提交的 pending assistant / 已落库 user 行 id 时，
    finalize_turn 原地 finalize 而不重复插入（幂等）。
    """

    content: str
    citations: list[dict[str, Any]] | None = None
    status: MessageStatus = MessageStatus.completed
    message_id: UUID | None = None
    retrieval_duration_ms: int | None = None


# 审计事件 = 「接收 db 的协程回调」（functools.partial 或闭包），在 commit 前统一 flush。
AuditEvent = Callable[[AsyncSession], Awaitable[None]]


async def finalize_turn(
    db: AsyncSession,
    *,
    thread: ChatThread,
    user_id: UUID,
    user_msg: TurnMessage,
    assistant_msg: TurnMessage,
    common: dict[str, Any] | None = None,
    run_id: UUID | None = None,
    run_status: AgentRunStatus | None = None,
    audit_events: Sequence[AuditEvent] = (),
) -> UUID:
    """user → assistant → run 终态 → 审计 → **一次 commit**（单一提交契约）。

    返回 assistant message id。调用方须保证同一轮只调一次（SSE generator 的
    try/finally 兜底路径与正常路径互斥）。
    """
    common = common or {}
    now = _utcnow()

    # ── 1) user 消息（恒在 assistant 之前）────────────────────────────
    if user_msg.message_id is not None:
        user_row = await db.get(ChatMessage, user_msg.message_id)
        if user_row is None:
            user_row = ChatMessage(
                id=user_msg.message_id,
                **common,
                thread_id=thread.id,
                user_id=user_id,
                role=MessageRole.user,
                content=user_msg.content,
                status=user_msg.status,
                citations=user_msg.citations,
                created_at=now,
            )
            db.add(user_row)
        elif user_row.status == MessageStatus.pending:
            # 预提交的 pending user 行 → 原地完成化
            user_row.status = user_msg.status
            user_row.content = user_msg.content
            user_row.citations = user_msg.citations
            user_row.created_at = now
    else:
        user_row = ChatMessage(
            **common,
            thread_id=thread.id,
            user_id=user_id,
            role=MessageRole.user,
            content=user_msg.content,
            status=user_msg.status,
            citations=user_msg.citations,
            created_at=now,
        )
        db.add(user_row)

    # ── 2) assistant 消息（pending → 原地 finalize；否则新建）────────────
    if assistant_msg.message_id is not None:
        assistant_row = await db.get(ChatMessage, assistant_msg.message_id)
        if assistant_row is None:
            assistant_row = ChatMessage(
                id=assistant_msg.message_id,
                **common,
                thread_id=thread.id,
                user_id=user_id,
                role=MessageRole.assistant,
                content=assistant_msg.content,
                status=assistant_msg.status,
                citations=assistant_msg.citations,
                retrieval_duration_ms=assistant_msg.retrieval_duration_ms,
                created_at=now,
            )
            db.add(assistant_row)
        else:
            # pending → finalize：内容/引用/状态 + 刷新 created_at 保序（P0-10）
            assistant_row.content = assistant_msg.content
            assistant_row.citations = assistant_msg.citations or []
            assistant_row.status = assistant_msg.status
            if assistant_msg.retrieval_duration_ms is not None:
                assistant_row.retrieval_duration_ms = assistant_msg.retrieval_duration_ms
            assistant_row.created_at = now
    else:
        assistant_row = ChatMessage(
            id=uuid.uuid4(),
            **common,
            thread_id=thread.id,
            user_id=user_id,
            role=MessageRole.assistant,
            content=assistant_msg.content,
            status=assistant_msg.status,
            citations=assistant_msg.citations,
            retrieval_duration_ms=assistant_msg.retrieval_duration_ms,
            created_at=now,
        )
        db.add(assistant_row)

    assistant_id = assistant_row.id

    # 首问自动标题 + thread touch
    await maybe_autotitle_thread_from_first_message(db, thread, user_msg.content)
    await touch_thread(db, thread.id)

    # ── 3) run 终态（条件更新幂等：仅 running 可写）─────────────────────
    if run_id is not None and run_status is not None:
        await finish_agent_run(
            db,
            run_id=run_id,
            user_id=user_id,
            status=run_status,
            assistant_message_id=assistant_id,
        )

    # ── 4) 审计事件（与消息/run 同事务）────────────────────────────────
    for event in audit_events:
        await event(db)

    # ── 5) 单一提交 ───────────────────────────────────────────────────
    await db.commit()
    return assistant_id
