"""对话 thread 保留期 purge（NW-20 · TECH-SEC §SEC-8）。

借 H3 CLI 形态：默认干跑 · --apply · retention_days · max_delete · 假时钟。
硬删整 thread（CASCADE 子表）；不删 audit_logs / 用户 / 知识库。
days<=0 = 禁用（不扫、不写 audit）。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.chat_thread import ChatThread
from app.services.audit.log import write_audit_log

logger = logging.getLogger(__name__)


@dataclass
class ChatRetentionPurgeResult:
    found: int
    deleted: int
    errors: int
    dry_run: bool
    retention_days: int
    disabled: bool = False
    items: list[dict] = field(default_factory=list)


def _activity_expr():
    return func.coalesce(ChatThread.last_message_at, ChatThread.created_at)


async def list_expired_chat_threads(
    db: AsyncSession,
    *,
    older_than: datetime,
    limit: int,
) -> list[ChatThread]:
    """活动龄早于 cutoff 的 thread（active + archived 一并）。"""
    activity = _activity_expr()
    result = await db.scalars(
        select(ChatThread)
        .where(activity < older_than)
        .order_by(activity.asc())
        .limit(limit)
    )
    return list(result.all())


def _thread_item(t: ChatThread) -> dict:
    activity = t.last_message_at or t.created_at
    return {
        "thread_id": str(t.id),
        "status": t.status.value if hasattr(t.status, "value") else str(t.status),
        "last_message_at": (
            t.last_message_at.isoformat() if t.last_message_at else None
        ),
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "activity_at": activity.isoformat() if activity else None,
    }


async def purge_expired_chat_threads(
    db: AsyncSession,
    *,
    dry_run: bool = True,
    retention_days: int | None = None,
    max_delete: int | None = None,
    now: datetime | None = None,
) -> ChatRetentionPurgeResult:
    """过期 thread → 硬删；默认干跑。days<=0 禁用。"""
    days = (
        settings.chat_retention_days if retention_days is None else retention_days
    )
    cap = (
        settings.chat_purge_max_delete if max_delete is None else max_delete
    )

    if days <= 0:
        return ChatRetentionPurgeResult(
            found=0,
            deleted=0,
            errors=0,
            dry_run=dry_run,
            retention_days=days,
            disabled=True,
            items=[],
        )

    clock = now or datetime.now(timezone.utc)
    cutoff = clock - timedelta(days=days)
    threads = await list_expired_chat_threads(db, older_than=cutoff, limit=cap)
    items = [_thread_item(t) for t in threads]

    if dry_run:
        await write_audit_log(
            db,
            action="chat.retention_purged",
            actor_user_id=None,
            resource_type="system",
            metadata={
                "dry_run": True,
                "found": len(threads),
                "deleted": 0,
                "errors": 0,
                "retention_days": days,
            },
        )
        await db.commit()
        return ChatRetentionPurgeResult(
            found=len(threads),
            deleted=0,
            errors=0,
            dry_run=True,
            retention_days=days,
            items=items,
        )

    deleted = 0
    errors = 0
    for t in threads:
        try:
            await db.delete(t)
            await db.flush()
            deleted += 1
        except Exception:
            errors += 1
            logger.exception("chat retention purge failed thread_id=%s", t.id)

    await write_audit_log(
        db,
        action="chat.retention_purged",
        actor_user_id=None,
        resource_type="system",
        metadata={
            "dry_run": False,
            "found": len(threads),
            "deleted": deleted,
            "errors": errors,
            "retention_days": days,
        },
    )
    await db.commit()
    return ChatRetentionPurgeResult(
        found=len(threads),
        deleted=deleted,
        errors=errors,
        dry_run=False,
        retention_days=days,
        items=items,
    )
