"""文档删除与失败重试（Plan-3A）。"""

from __future__ import annotations

import uuid

from fastapi import BackgroundTasks, status
from app.core.exceptions import NotFoundError, ConflictError, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, KbAction, require_kb_access
from app.models.document import Document
from app.models.enums import DocumentStatus
from app.schemas.document import DocumentResponse
from app.services.ingestion.pipeline import process_document_ingestion
from app.services.audit.log import write_audit_log
from app.services.storage.cleaner import remove_document_tree


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

    if doc.status == DocumentStatus.processing:
        raise ConflictError("整理中请稍后再删")

    storage_path = doc.storage_path
    filename = doc.filename

    await write_audit_log(
        db,
        action="document.delete",
        actor_user_id=current_user.id,
        resource_type="document",
        resource_id=doc_id,
        kb_id=kb_id,
        metadata={"filename": filename},
        ip=ip,
    )
    await db.delete(doc)
    await db.commit()

    cleanup = remove_document_tree(
        kb_id=kb_id, doc_id=doc_id, storage_path=storage_path
    )
    if cleanup.file_errors + cleanup.tree_errors > 0:
        await write_audit_log(
            db,
            action="storage.cleanup_failed",
            actor_user_id=current_user.id,
            resource_type="document",
            resource_id=doc_id,
            kb_id=kb_id,
            metadata={
                "filename": filename,
                "file_errors": cleanup.file_errors,
                "tree_errors": cleanup.tree_errors,
            },
            ip=ip,
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

    background_tasks.add_task(process_document_ingestion, doc.id)
    return DocumentResponse.model_validate(doc)
