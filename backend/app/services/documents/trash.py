"""回收站服务：列表/恢复/过期 purge（H3）。"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import ConflictError, NotFoundError
from app.models.document import Document
from app.schemas.document import DocumentResponse
from app.services.audit.log import write_audit_log

logger = logging.getLogger(__name__)


async def list_trash(
    db: AsyncSession,
    kb_id: uuid.UUID,
) -> list[DocumentResponse]:
    """列回收站中的文档（已软删，按删除时间倒序）。"""
    result = await db.scalars(
        select(Document)
        .where(Document.kb_id == kb_id)
        .where(Document.deleted_at.is_not(None))
        .order_by(Document.deleted_at.desc())
    )
    return [DocumentResponse.model_validate(doc) for doc in result.all()]


async def restore_document(
    db: AsyncSession,
    kb_id: uuid.UUID,
    doc_id: uuid.UUID,
    *,
    actor_user_id: uuid.UUID | None = None,
    ip: str | None = None,
) -> DocumentResponse:
    """从回收站恢复文档（H3：commit + audit；同名 active → 409）。"""
    doc = await db.scalar(
        select(Document).where(
            Document.id == doc_id,
            Document.kb_id == kb_id,
            Document.deleted_at.is_not(None),
        )
    )
    if doc is None:
        raise NotFoundError("文档不在回收站中")

    await _restore_no_commit(db, doc, actor_user_id=actor_user_id, kb_id=kb_id, ip=ip)
    await db.commit()
    await db.refresh(doc)
    return DocumentResponse.model_validate(doc)


async def _restore_no_commit(
    db: AsyncSession,
    doc: Document,
    *,
    actor_user_id: uuid.UUID | None = None,
    kb_id: uuid.UUID,
    ip: str | None = None,
) -> None:
    """恢复文档并写审计，但**不提交**。供公开 restore_document 与审批采纳复用。"""
    clash = await db.scalar(
        select(Document.id).where(
            Document.kb_id == kb_id,
            Document.id != doc.id,
            Document.deleted_at.is_(None),
            func.lower(Document.filename) == doc.filename.lower(),
        ).limit(1)
    )
    if clash is not None:
        raise ConflictError("库中已有同名文档，请先处理后再恢复")

    if doc.storage_path and not Path(doc.storage_path).is_file():
        logger.warning(
            "restore document %s: storage file missing path=%s",
            doc.id,
            doc.storage_path,
        )

    doc.deleted_at = None
    await write_audit_log(
        db,
        action="document.restore",
        actor_user_id=actor_user_id,
        resource_type="document",
        resource_id=doc.id,
        kb_id=kb_id,
        metadata={"filename": doc.filename},
        ip=ip,
    )


@dataclass(frozen=True)
class TrashPurgeResult:
    found: int
    deleted: int
    errors: int
    dry_run: bool
    items: list[dict]


async def list_expired_trash(
    db: AsyncSession,
    *,
    older_than: datetime,
    limit: int,
) -> list[Document]:
    """过期回收站文档（deleted_at < older_than），按删除时间升序。"""
    result = await db.scalars(
        select(Document)
        .where(Document.deleted_at.is_not(None))
        .where(Document.deleted_at < older_than)
        .order_by(Document.deleted_at.asc())
        .limit(limit)
    )
    return list(result.all())


async def purge_expired_trash(
    db: AsyncSession,
    *,
    dry_run: bool = True,
    retention_days: int | None = None,
    max_delete: int | None = None,
    now: datetime | None = None,
) -> TrashPurgeResult:
    """过期 trash → permanent 同源清盘；默认干跑。"""
    days = settings.trash_retention_days if retention_days is None else retention_days
    cap = settings.trash_purge_max_delete if max_delete is None else max_delete
    clock = now or datetime.now(timezone.utc)
    cutoff = clock - timedelta(days=days)

    docs = await list_expired_trash(db, older_than=cutoff, limit=cap)
    items = [
        {
            "id": str(d.id),
            "kb_id": str(d.kb_id),
            "filename": d.filename,
            "deleted_at": d.deleted_at.isoformat() if d.deleted_at else None,
        }
        for d in docs
    ]

    if dry_run:
        await write_audit_log(
            db,
            action="document.trash_purged",
            actor_user_id=None,
            resource_type="system",
            metadata={
                "dry_run": True,
                "found": len(docs),
                "deleted": 0,
                "errors": 0,
                "retention_days": days,
            },
        )
        await db.commit()
        return TrashPurgeResult(
            found=len(docs),
            deleted=0,
            errors=0,
            dry_run=True,
            items=items,
        )

    from app.services.documents.lifecycle import permanently_delete_document

    deleted = 0
    errors = 0
    for d in docs:
        try:
            await permanently_delete_document(db, d.kb_id, d.id)
            deleted += 1
        except Exception:
            errors += 1
            logger.exception("trash purge failed doc_id=%s", d.id)

    await write_audit_log(
        db,
        action="document.trash_purged",
        actor_user_id=None,
        resource_type="system",
        metadata={
            "dry_run": False,
            "found": len(docs),
            "deleted": deleted,
            "errors": errors,
            "retention_days": days,
        },
    )
    await db.commit()
    return TrashPurgeResult(
        found=len(docs),
        deleted=deleted,
        errors=errors,
        dry_run=False,
        items=items,
    )
