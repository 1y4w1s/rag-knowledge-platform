"""资料库名称唯一性校验（同一工作区内不可重名，忽略大小写）。"""

from uuid import UUID

from fastapi import status
from app.core.exceptions import ValidationError, ConflictError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge_base import KnowledgeBase
from app.services.workspace.scope import WorkspaceScope


async def assert_kb_name_available(
    db: AsyncSession,
    scope: WorkspaceScope,
    name: str,
    *,
    exclude_kb_id: UUID | None = None,
) -> str:
    """返回 trim 后的名称；冲突时 409。"""
    normalized = name.strip()
    if not normalized:
        raise ValidationError("名称不能为空")

    stmt = select(KnowledgeBase.id).where(
        func.lower(func.btrim(KnowledgeBase.name)) == normalized.lower(),
        scope.kb_owner_clause(),
    )

    if exclude_kb_id is not None:
        stmt = stmt.where(KnowledgeBase.id != exclude_kb_id)

    if await db.scalar(stmt.limit(1)) is not None:
        raise ConflictError("该名称的资料库已存在，请换一个名称")

    return normalized
