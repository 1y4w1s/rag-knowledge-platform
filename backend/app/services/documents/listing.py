"""单库文档列表分页（EW-E2）与高级筛选（R1-4）。"""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import status
from app.core.exceptions import NotFoundError
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, KbAction, require_kb_access
from app.models.document import Document
from app.models.enums import DocumentVisibility, OrgRole
from app.schemas.document import DocumentListResponse, DocumentResponse
from app.services.documents.filters import (
    apply_document_list_filters,
    build_filter_conditions,
    normalize_file_types,
    normalize_statuses,
    validate_uploaded_range,
)

DEFAULT_LIMIT = 50
MAX_LIMIT = 100


def normalize_limit(raw: int | None) -> int:
    if raw is None:
        return DEFAULT_LIMIT
    return min(max(raw, 1), MAX_LIMIT)


def normalize_offset(raw: int | None) -> int:
    if raw is None:
        return 0
    return max(raw, 0)


async def list_documents(
    db: AsyncSession,
    current_user: CurrentUser,
    kb_id: uuid.UUID,
    *,
    limit: int | None = None,
    offset: int | None = None,
    file_type: list[str] | None = None,
    status: list[str] | None = None,
    uploaded_from: date | None = None,
    uploaded_to: date | None = None,
) -> DocumentListResponse:
    await require_kb_access(
        kb_id=kb_id,
        action=KbAction.read,
        current_user=current_user,
        db=db,
    )

    validate_uploaded_range(uploaded_from, uploaded_to)

    capped_limit = normalize_limit(limit)
    capped_offset = normalize_offset(offset)
    file_types = normalize_file_types(file_type)
    statuses = normalize_statuses(status)
    filter_conditions = build_filter_conditions(
        file_types=file_types,
        statuses=statuses,
        uploaded_from=uploaded_from,
        uploaded_to=uploaded_to,
    )

    # 文档级可见性：member 看不到 admin_only 文档
    if (
        current_user.account_type.value == "enterprise"
        and current_user.org_role == "member"
    ):
        filter_conditions.append(Document.visibility == DocumentVisibility.everyone)

    count_stmt = (
        select(func.count())
        .select_from(Document)
        .where(Document.kb_id == kb_id)
        .where(Document.deleted_at.is_(None))
    )
    if filter_conditions:
        count_stmt = count_stmt.where(and_(*filter_conditions))
    total = await db.scalar(count_stmt)
    total_count = int(total or 0)

    stmt = apply_document_list_filters(
        select(Document).where(Document.kb_id == kb_id),
        file_types=file_types,
        statuses=statuses,
        uploaded_from=uploaded_from,
        uploaded_to=uploaded_to,
    )
    # visibility 过滤不能走 apply_document_list_filters，单独加
    stmt = stmt.where(Document.deleted_at.is_(None))
    if (
        current_user.account_type.value == "enterprise"
        and current_user.org_role == "member"
    ):
        stmt = stmt.where(Document.visibility == DocumentVisibility.everyone)
    stmt = (
        stmt.order_by(Document.created_at.desc())
        .limit(capped_limit)
        .offset(capped_offset)
    )
    result = await db.scalars(stmt)
    items = [DocumentResponse.model_validate(doc) for doc in result.all()]

    return DocumentListResponse(
        items=items,
        total=total_count,
        limit=capped_limit,
        offset=capped_offset,
    )


async def get_document(
    db: AsyncSession,
    current_user: CurrentUser,
    kb_id: uuid.UUID,
    doc_id: uuid.UUID,
) -> DocumentResponse:
    await require_kb_access(
        kb_id=kb_id,
        action=KbAction.read,
        current_user=current_user,
        db=db,
    )
    doc = await db.scalar(
        select(Document).where(
            Document.id == doc_id,
            Document.kb_id == kb_id,
            Document.deleted_at.is_(None),
        )
    )
    if doc is None:
        raise NotFoundError("文档不存在")
    # 文档级可见性：member 不能直接访问 admin_only 文档
    if (
        doc.visibility == DocumentVisibility.admin_only
        and current_user.account_type.value == "enterprise"
        and current_user.org_role == "member"
    ):
        raise NotFoundError("文档不存在")
    return DocumentResponse.model_validate(doc)
