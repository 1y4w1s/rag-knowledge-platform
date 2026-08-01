"""知识库文档清单导出（NW-38 / SEC-8）。仅文档 metadata，无正文/路径/对话。"""

from __future__ import annotations

import csv
import io
import json
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser
from app.core.exceptions import ForbiddenError
from app.models.document import Document
from app.models.knowledge_base import KnowledgeBase
from app.models.user import User

EXPORT_MAX_ROWS = 5000
ExportFormat = Literal["csv", "json"]

# 白名单列；禁止 content / body / storage_path / chunk 正文
CSV_COLUMNS = (
    "kb_id",
    "kb_name",
    "doc_id",
    "filename",
    "file_type",
    "file_size",
    "status",
    "visibility",
    "chunk_count",
    "uploaded_by",
    "uploaded_by_email",
    "created_at",
    "updated_at",
    "current_version",
    "content_sha256",
    "in_trash",
    "deleted_at",
)


@dataclass(frozen=True)
class InventoryRow:
    kb_id: uuid.UUID
    kb_name: str
    doc_id: uuid.UUID
    filename: str
    file_type: str
    file_size: int
    status: str
    visibility: str
    chunk_count: int | None
    uploaded_by: uuid.UUID | None
    uploaded_by_email: str | None
    created_at: datetime
    updated_at: datetime
    current_version: int
    content_sha256: str | None
    in_trash: bool
    deleted_at: datetime | None


def _enum_value(value: Any) -> str:
    return value.value if hasattr(value, "value") else str(value)


def _row_dict(item: InventoryRow) -> dict[str, str]:
    return {
        "kb_id": str(item.kb_id),
        "kb_name": item.kb_name,
        "doc_id": str(item.doc_id),
        "filename": item.filename,
        "file_type": item.file_type,
        "file_size": str(item.file_size),
        "status": item.status,
        "visibility": item.visibility,
        "chunk_count": "" if item.chunk_count is None else str(item.chunk_count),
        "uploaded_by": str(item.uploaded_by) if item.uploaded_by else "",
        "uploaded_by_email": item.uploaded_by_email or "",
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
        "current_version": str(item.current_version),
        "content_sha256": item.content_sha256 or "",
        "in_trash": "true" if item.in_trash else "false",
        "deleted_at": item.deleted_at.isoformat() if item.deleted_at else "",
    }


def render_inventory_csv(items: list[InventoryRow]) -> str:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=CSV_COLUMNS, extrasaction="ignore")
    writer.writeheader()
    for item in items:
        writer.writerow(_row_dict(item))
    return buf.getvalue()


def render_inventory_json(
    items: list[InventoryRow],
    *,
    total_matched: int,
    truncated: bool,
    export_limit: int,
    include_trash: bool,
) -> str:
    payload = {
        "kind": "kb_inventory_export",
        "format": "json",
        "include_trash": include_trash,
        "total_matched": total_matched,
        "exported": len(items),
        "export_limit": export_limit,
        "truncated": truncated,
        "items": [
            {
                "kb_id": str(item.kb_id),
                "kb_name": item.kb_name,
                "doc_id": str(item.doc_id),
                "filename": item.filename,
                "file_type": item.file_type,
                "file_size": item.file_size,
                "status": item.status,
                "visibility": item.visibility,
                "chunk_count": item.chunk_count,
                "uploaded_by": str(item.uploaded_by) if item.uploaded_by else None,
                "uploaded_by_email": item.uploaded_by_email,
                "created_at": item.created_at.isoformat(),
                "updated_at": item.updated_at.isoformat(),
                "current_version": item.current_version,
                "content_sha256": item.content_sha256,
                "in_trash": item.in_trash,
                "deleted_at": (
                    item.deleted_at.isoformat() if item.deleted_at else None
                ),
            }
            for item in items
        ],
    }
    return json.dumps(payload, ensure_ascii=False)


async def collect_kb_inventory(
    db: AsyncSession,
    admin: CurrentUser,
    *,
    max_rows: int,
    kb_id: uuid.UUID | None = None,
    include_trash: bool = False,
) -> tuple[list[InventoryRow], int, bool]:
    """按 org 可见资料库拉取文档 metadata；返回 (rows, total_matched, truncated)。"""
    assert admin.org_id is not None
    org_id = admin.org_id
    cap = max(1, max_rows)

    filters: list[Any] = [KnowledgeBase.owner_org_id == org_id]

    if kb_id is not None:
        kb = await db.get(KnowledgeBase, kb_id)
        if kb is None or kb.owner_org_id != org_id:
            raise ForbiddenError("无权访问该知识库")
        filters.append(Document.kb_id == kb_id)

    if not include_trash:
        filters.append(Document.deleted_at.is_(None))

    where = and_(*filters)

    total = int(
        await db.scalar(
            select(func.count())
            .select_from(Document)
            .join(KnowledgeBase, Document.kb_id == KnowledgeBase.id)
            .where(where)
        )
        or 0
    )

    result = await db.execute(
        select(Document, KnowledgeBase.name)
        .join(KnowledgeBase, Document.kb_id == KnowledgeBase.id)
        .where(where)
        .order_by(Document.created_at.desc(), Document.id.desc())
        .limit(cap)
    )
    pairs = list(result.all())

    uploader_ids = {doc.uploaded_by for doc, _ in pairs if doc.uploaded_by}
    email_by_id: dict[uuid.UUID, str] = {}
    if uploader_ids:
        users = await db.scalars(select(User).where(User.id.in_(uploader_ids)))
        email_by_id = {u.id: u.email for u in users.all()}

    items: list[InventoryRow] = []
    for doc, kb_name in pairs:
        in_trash = doc.deleted_at is not None
        items.append(
            InventoryRow(
                kb_id=doc.kb_id,
                kb_name=kb_name,
                doc_id=doc.id,
                filename=doc.filename,
                file_type=doc.file_type,
                file_size=doc.file_size,
                status=_enum_value(doc.status),
                visibility=_enum_value(doc.visibility),
                chunk_count=doc.chunk_count,
                uploaded_by=doc.uploaded_by,
                uploaded_by_email=(
                    email_by_id.get(doc.uploaded_by) if doc.uploaded_by else None
                ),
                created_at=doc.created_at,
                updated_at=doc.updated_at,
                current_version=doc.current_version,
                content_sha256=doc.content_sha256,
                in_trash=in_trash,
                deleted_at=doc.deleted_at if include_trash else None,
            )
        )

    return items, total, total > cap
