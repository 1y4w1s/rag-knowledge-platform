"""文档删除与失败重试（Plan-3A）。"""

from __future__ import annotations

import logging
import uuid

from fastapi import BackgroundTasks
from app.core.exceptions import NotFoundError, ConflictError, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, KbAction, require_kb_access
from app.models.document import Document
from app.models.enums import DocumentStatus
from app.schemas.document import DocumentResponse
from app.services.ingestion.enqueue import enqueue_document_ingestion
from app.services.audit.log import write_audit_log

logger = logging.getLogger(__name__)


async def _get_document_in_kb(
    db: AsyncSession,
    *,
    kb_id: uuid.UUID,
    doc_id: uuid.UUID,
) -> Document:
    doc = await db.scalar(
        select(Document).where(
            Document.id == doc_id,
            Document.kb_id == kb_id,
        )
    )
    if doc is None:
        raise NotFoundError("文档不存在")
    return doc


async def delete_document(
    db: AsyncSession,
    current_user: CurrentUser,
    kb_id: uuid.UUID,
    doc_id: uuid.UUID,
    *,
    ip: str | None = None,
) -> None:
    await require_kb_access(
        kb_id=kb_id,
        action=KbAction.write,
        current_user=current_user,
        db=db,
    )
    doc = await _get_document_in_kb(db, kb_id=kb_id, doc_id=doc_id)
    await _soft_delete_no_commit(
        db, doc, actor_user_id=current_user.id, kb_id=kb_id, ip=ip
    )
    await db.commit()
    logger.info("document soft-deleted: doc_id=%s kb_id=%s filename=%s actor=%s", doc_id, kb_id, doc.filename, current_user.id)


async def _soft_delete_no_commit(
    db: AsyncSession,
    doc: Document,
    *,
    actor_user_id: uuid.UUID,
    kb_id: uuid.UUID,
    ip: str | None = None,
) -> None:
    """软删文档并写审计，但**不提交**。供公开 delete_document 与审批采纳复用。"""
    if doc.status == DocumentStatus.processing:
        raise ConflictError("整理中请稍后再删")

    filename = doc.filename
    await write_audit_log(
        db,
        action="document.delete",
        actor_user_id=actor_user_id,
        resource_type="document",
        resource_id=doc.id,
        kb_id=kb_id,
        metadata={"filename": filename},
        ip=ip,
    )

    # H3：软删只打 deleted_at，保留磁盘直至永久删除 / 过期 purge
    from datetime import datetime, timezone
    doc.deleted_at = datetime.now(timezone.utc)


async def permanently_delete_document(
    db: AsyncSession,
    kb_id: uuid.UUID,
    doc_id: uuid.UUID,
) -> None:
    """回收站内的永久删除（物理删除 DB 记录 + 磁盘文件）。"""
    doc = await _get_document_in_kb(db, kb_id=kb_id, doc_id=doc_id)
    if doc.deleted_at is None:
        raise ValidationError("只能永久删除回收站中的文档")

    storage_path = doc.storage_path
    from app.services.storage.cleaner import remove_document_tree

    await db.delete(doc)
    await db.commit()
    logger.info("document permanently deleted: doc_id=%s kb_id=%s", doc_id, kb_id)

    cleanup = remove_document_tree(
        kb_id=kb_id, doc_id=doc_id, storage_path=storage_path
    )
    audit_action = "storage.cleanup_failed" if cleanup.file_errors + cleanup.tree_errors > 0 else "document.permanently_deleted"
    await write_audit_log(
        db,
        action=audit_action,
        actor_user_id=None,
        resource_type="document",
        resource_id=doc_id,
        kb_id=kb_id,
        metadata={
            "filename": doc.filename,
            "file_errors": cleanup.file_errors,
            "tree_errors": cleanup.tree_errors,
        },
    )
    await db.commit()


async def retry_document(
    db: AsyncSession,
    current_user: CurrentUser,
    kb_id: uuid.UUID,
    doc_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    *,
    ip: str | None = None,
) -> DocumentResponse:
    await require_kb_access(
        kb_id=kb_id,
        action=KbAction.write,
        current_user=current_user,
        db=db,
    )
    doc = await _get_document_in_kb(db, kb_id=kb_id, doc_id=doc_id)

    if doc.status != DocumentStatus.failed:
        raise ValidationError("仅失败文档可重试")

    doc.status = DocumentStatus.queued
    doc.error_message = None
    doc.chunk_count = None
    doc.processing_started_at = None
    doc.processing_completed_at = None
    from app.services.ingestion.progress import clear_progress_fields

    clear_progress_fields(doc)

    await write_audit_log(
        db,
        action="document.retry",
        actor_user_id=current_user.id,
        resource_type="document",
        resource_id=doc_id,
        kb_id=kb_id,
        metadata={"filename": doc.filename},
        ip=ip,
    )
    await db.commit()
    await db.refresh(doc)

    await enqueue_document_ingestion(doc.id, background_tasks)
    return DocumentResponse.model_validate(doc)
