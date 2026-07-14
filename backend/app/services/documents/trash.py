"""回收站服务：列表/恢复/永久删除。"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.schemas.document import DocumentResponse


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
) -> DocumentResponse:
    """从回收站恢复文档。"""
    doc = await db.scalar(
        select(Document).where(
            Document.id == doc_id,
            Document.kb_id == kb_id,
            Document.deleted_at.is_not(None),
        )
    )
    if doc is None:
        from app.core.exceptions import NotFoundError
        raise NotFoundError("文档不在回收站中")

    doc.deleted_at = None
    await db.flush()
    return DocumentResponse.model_validate(doc)
