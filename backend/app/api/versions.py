"""文档版本管理 API（Wave 7.1）。"""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser, KbAction, get_current_user, require_kb_access
from app.models.document import Document
from app.models.document_version import DocumentVersion
from app.models.enums import DocumentStatus
from app.services.audit.log import write_audit_log
from app.services.ingestion.tasks import ingest_document_task
from app.schemas.document import DocumentResponse
from pydantic import BaseModel
from datetime import datetime


router = APIRouter(prefix="/knowledge-bases/{kb_id}/documents/{doc_id}/versions", tags=["versions"])


class VersionResponse(BaseModel):
    version_number: int
    file_size: int
    created_at: datetime


@router.get("")
async def list_versions(
    kb_id: UUID,
    doc_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[VersionResponse]:
    """查询文档版本历史。"""
    await require_kb_access(kb_id=kb_id, action=KbAction.read, current_user=current_user, db=db)

    doc = await db.get(Document, doc_id)
    if doc is None or doc.kb_id != kb_id:
        raise HTTPException(status_code=404, detail="文档不存在")

    result = await db.execute(
        select(DocumentVersion)
        .where(DocumentVersion.document_id == doc_id)
        .order_by(DocumentVersion.version_number.desc())
    )
    versions = result.scalars().all()

    return [
        VersionResponse(
            version_number=v.version_number,
            file_size=v.file_size,
            created_at=v.created_at,
        )
        for v in versions
    ]


@router.post("/{version_number}/restore", response_model=DocumentResponse)
async def restore_version(
    kb_id: UUID,
    doc_id: UUID,
    version_number: int,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DocumentResponse:
    """回滚到指定历史版本。"""
    await require_kb_access(kb_id=kb_id, action=KbAction.write, current_user=current_user, db=db)

    doc = await db.get(Document, doc_id)
    if doc is None or doc.kb_id != kb_id:
        raise HTTPException(status_code=404, detail="文档不存在")

    result = await db.execute(
        select(DocumentVersion).where(
            DocumentVersion.document_id == doc_id,
            DocumentVersion.version_number == version_number,
        )
    )
    version = result.scalar_one_or_none()
    if version is None:
        raise HTTPException(status_code=404, detail="版本不存在")

    if doc.status == DocumentStatus.processing:
        raise HTTPException(status_code=409, detail="文档正在处理中，请稍后重试")

    # 保存当前版本到版本历史
    old_version = DocumentVersion(
        document_id=doc_id,
        version_number=doc.current_version,
        storage_path=doc.storage_path,
        file_size=doc.file_size,
        content_sha256=doc.content_sha256,
        uploaded_by=current_user.id,
    )
    db.add(old_version)

    # 更新文档指向历史版本的文件
    doc.storage_path = version.storage_path
    doc.file_size = version.file_size
    doc.content_sha256 = version.content_sha256
    doc.current_version += 1
    doc.status = DocumentStatus.queued
    doc.error_message = None
    doc.chunk_count = None
    doc.processing_started_at = None
    doc.processing_completed_at = None

    await write_audit_log(
        db, action="document.version.restore",
        actor_user_id=current_user.id,
        resource_type="document", resource_id=doc_id,
        kb_id=kb_id,
        metadata={"filename": doc.filename, "version": version_number},
    )

    await db.commit()
    await db.refresh(doc)

    # 触发重新 ingestion
    ingest_document_task.delay(str(doc.id))

    return DocumentResponse.model_validate(doc)
