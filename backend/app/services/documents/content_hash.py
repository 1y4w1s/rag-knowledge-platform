"""文档内容指纹（EW-D1 / Plan-3E-7）。"""

import hashlib
import uuid

from fastapi import status
from app.core.exceptions import ConflictError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document


def sha256_hex(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


async def assert_content_unique_in_kb(
    db: AsyncSession,
    *,
    kb_id: uuid.UUID,
    content_sha256: str,
) -> None:
    """同一资料库内相同内容指纹不可重复上传。"""
    existing_name = await db.scalar(
        select(Document.filename)
        .where(
            Document.kb_id == kb_id,
            Document.content_sha256 == content_sha256,
        )
        .limit(1)
    )
    if existing_name is not None:
        raise ConflictError(
            detail=f"文件内容已存在，与已有文档「{existing_name}」相同",
        )
