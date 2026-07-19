"""对话 thread 审计钩子（G2-1.4 · plan §7）。"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat_thread import ChatThread
from app.models.enums import ThreadKind
from app.services.audit.log import write_audit_log


def _thread_created_metadata(thread: ChatThread) -> dict[str, str | None]:
    return {
        "thread_id": str(thread.id),
        "thread_kind": thread.thread_kind.value,
        "workspace_kind": thread.workspace_kind,
        "workspace_org_id": (
            str(thread.workspace_org_id) if thread.workspace_org_id else None
        ),
        "workspace_department_key": thread.workspace_department_key,
        "kb_id": str(thread.kb_id) if thread.kb_id else None,
    }


async def audit_thread_created(
    db: AsyncSession,
    *,
    thread: ChatThread,
    actor_user_id: UUID,
) -> None:
    """新建 thread → chat.thread_created（不含消息正文）。"""
    await write_audit_log(
        db,
        action="chat.thread_created",
        actor_user_id=actor_user_id,
        resource_type="chat_thread",
        resource_id=thread.id,
        kb_id=thread.kb_id if thread.thread_kind == ThreadKind.knowledge_base else None,
        metadata=_thread_created_metadata(thread),
    )


async def audit_thread_archived(
    db: AsyncSession,
    *,
    thread: ChatThread,
    actor_user_id: UUID,
) -> None:
    """归档/软删 thread → chat.thread_archived。"""
    await write_audit_log(
        db,
        action="chat.thread_archived",
        actor_user_id=actor_user_id,
        resource_type="chat_thread",
        resource_id=thread.id,
        kb_id=thread.kb_id if thread.thread_kind == ThreadKind.knowledge_base else None,
        metadata={
            "thread_id": str(thread.id),
            "thread_kind": thread.thread_kind.value,
        },
    )


async def audit_message_sent(
    db: AsyncSession,
    *,
    thread: ChatThread,
    actor_user_id: UUID,
    assistant_message_id: UUID,
    citation_count: int,
    retrieval_ms: int | None,
) -> None:
    """发送消息落库后 → chat.message_sent（不含 user 问题全文）。"""
    await write_audit_log(
        db,
        action="chat.message_sent",
        actor_user_id=actor_user_id,
        resource_type="chat_message",
        resource_id=assistant_message_id,
        kb_id=thread.kb_id if thread.thread_kind == ThreadKind.knowledge_base else None,
        metadata={
            "thread_id": str(thread.id),
            "thread_kind": thread.thread_kind.value,
            "message_id": str(assistant_message_id),
            "citation_count": citation_count,
            "retrieval_ms": retrieval_ms,
        },
    )
