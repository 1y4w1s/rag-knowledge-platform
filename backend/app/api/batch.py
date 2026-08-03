"""批处理操作 API — 批量删除 / 重新 ingestion。"""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser, KbAction, get_current_user, require_kb_access
from app.services.audit.log import write_audit_log
from app.models.document import Document
from app.models.enums import DocumentStatus
from app.services.ingestion.enqueue import enqueue_document_ingestion
from pydantic import BaseModel, field_validator

router = APIRouter(prefix="/batch", tags=["batch"])


class BatchDeleteRequest(BaseModel):
    kb_id: UUID
    doc_ids: list[UUID]

    @field_validator("doc_ids")
    @classmethod
    def limit_doc_ids(cls, v: list[UUID]) -> list[UUID]:
        if len(v) > 200:
            raise ValueError("批量操作每次最多 200 个文档")
        return v


class BatchReIngestRequest(BaseModel):
    kb_id: UUID
    doc_ids: list[UUID]

    @field_validator("doc_ids")
    @classmethod
    def limit_doc_ids(cls, v: list[UUID]) -> list[UUID]:
        if len(v) > 200:
            raise ValueError("批量操作每次最多 200 个文档")
        return v


class BatchResult(BaseModel):
    total: int
    succeeded: int
    failed: int
    errors: list[dict]


@router.post("/delete")
async def batch_delete(
    body: BatchDeleteRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    """批量软删文档。跳过 processing 状态的文档。"""
    await require_kb_access(
        kb_id=body.kb_id,
        action=KbAction.write,
        current_user=current_user,
        db=db,
    )

    result = await db.execute(
        select(Document).where(
            Document.kb_id == body.kb_id,
            Document.id.in_(body.doc_ids),
            Document.deleted_at.is_(None),
        )
    )
    docs = result.scalars().all()

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    skipped = 0
    for doc in docs:
        if doc.status == DocumentStatus.processing:
            skipped += 1
            continue
        doc.deleted_at = now
        await write_audit_log(
            db, action="document.delete",
            actor_user_id=current_user.id,
            resource_type="document", resource_id=doc.id,
            kb_id=body.kb_id,
            metadata={"filename": doc.filename, "batch": True},
        )

    await db.commit()
    return Response(status_code=204)


@router.post("/re-ingest")
async def batch_re_ingest(
    body: BatchReIngestRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    background_tasks: BackgroundTasks,
) -> BatchResult:
    """批量重置文档状态为 queued 并触发重新 ingestion。"""
    await require_kb_access(
        kb_id=body.kb_id,
        action=KbAction.write,
        current_user=current_user,
        db=db,
    )

    result = await db.execute(
        select(Document).where(
            Document.kb_id == body.kb_id,
            Document.id.in_(body.doc_ids),
            Document.deleted_at.is_(None),
        )
    )
    docs = result.scalars().all()

    succeeded = 0
    failed = 0
    errors: list[dict] = []
    pending_ids: list[UUID] = []

    for doc in docs:
        if doc.status == DocumentStatus.processing:
            failed += 1
            errors.append({"doc_id": str(doc.id), "error": "文档正在处理中"})
            continue

        # 重置状态
        doc.status = DocumentStatus.queued
        doc.error_message = None
        doc.chunk_count = None
        doc.processing_started_at = None
        doc.processing_completed_at = None
        from app.services.ingestion.progress import clear_progress_fields

        clear_progress_fields(doc)

        await write_audit_log(
            db, action="document.retry",
            actor_user_id=current_user.id,
            resource_type="document", resource_id=doc.id,
            kb_id=body.kb_id,
            metadata={"filename": doc.filename, "batch": True},
        )

        pending_ids.append(doc.id)
        succeeded += 1

    await db.commit()
    for doc_id in pending_ids:
        await enqueue_document_ingestion(doc_id, background_tasks)

    return BatchResult(
        total=len(docs),
        succeeded=succeeded,
        failed=failed,
        errors=errors,
    )
