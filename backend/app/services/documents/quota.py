"""NW-25 · 单库 uploads 容量硬闸（非计费）。

used = SUM(documents.file_size 含 trash) + SUM(document_versions.file_size 同库)。
落盘前 assert；0 = 关闭总闸。不扫盘、不改检索。
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.exceptions import ValidationError
from app.models.document import Document
from app.models.document_version import DocumentVersion
from app.services.audit.log import write_audit_log


def _format_bytes(n: int) -> str:
    if n >= 1024**3:
        return f"{n / (1024**3):.2f} GiB"
    if n >= 1024**2:
        return f"{n / (1024**2):.2f} MiB"
    if n >= 1024:
        return f"{n / 1024:.1f} KiB"
    return f"{n} B"


async def used_bytes_for_kb(db: AsyncSession, kb_id: uuid.UUID) -> int:
    """单库账面占用：当前文档（含软删）+ 版本历史。"""
    doc_sum = await db.scalar(
        select(func.coalesce(func.sum(Document.file_size), 0)).where(
            Document.kb_id == kb_id
        )
    )
    ver_sum = await db.scalar(
        select(func.coalesce(func.sum(DocumentVersion.file_size), 0))
        .select_from(DocumentVersion)
        .join(Document, Document.id == DocumentVersion.document_id)
        .where(Document.kb_id == kb_id)
    )
    return int(doc_sum or 0) + int(ver_sum or 0)


async def _audit_quota_rejected(
    *,
    kb_id: uuid.UUID,
    used: int,
    limit: int,
    additional_bytes: int,
    actor_user_id: uuid.UUID | None,
    filename: str | None,
    ip: str | None,
) -> None:
    """独立会话提交，避免请求路径因 422 回滚丢掉撞限记录。"""
    async with SessionLocal() as audit_db:
        await write_audit_log(
            audit_db,
            action="document.quota_rejected",
            actor_user_id=actor_user_id,
            resource_type="knowledge_base",
            resource_id=kb_id,
            kb_id=kb_id,
            metadata={
                "used_bytes": used,
                "limit_bytes": limit,
                "additional_bytes": additional_bytes,
                "filename": filename,
            },
            ip=ip,
        )
        await audit_db.commit()


async def assert_kb_quota_allows(
    db: AsyncSession,
    kb_id: uuid.UUID,
    additional_bytes: int,
    *,
    actor_user_id: uuid.UUID | None = None,
    filename: str | None = None,
    ip: str | None = None,
) -> None:
    """落盘前：used + additional ≤ limit；超限 → ValidationError 422。"""
    limit = int(settings.kb_quota_max_bytes)
    if limit <= 0 or additional_bytes <= 0:
        return

    used = await used_bytes_for_kb(db, kb_id)
    if used + additional_bytes <= limit:
        return

    await _audit_quota_rejected(
        kb_id=kb_id,
        used=used,
        limit=limit,
        additional_bytes=additional_bytes,
        actor_user_id=actor_user_id,
        filename=filename,
        ip=ip,
    )
    raise ValidationError(
        detail=(
            f"本资料库容量已达上限（已用 {_format_bytes(used)} / "
            f"上限 {_format_bytes(limit)}）。"
            "请永久删除回收站或不需要的文档后再试。"
        ),
    )


__all__ = [
    "assert_kb_quota_allows",
    "used_bytes_for_kb",
]
