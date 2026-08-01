"""知识库文档清单 Admin 导出 API（NW-38 / SEC-8）。"""

from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser, require_org_role
from app.models.enums import OrgRole
from app.services.documents.inventory_export import (
    EXPORT_MAX_ROWS,
    collect_kb_inventory,
    render_inventory_csv,
    render_inventory_json,
)

router = APIRouter(prefix="/admin", tags=["admin"])

OrgAdmin = Annotated[CurrentUser, Depends(require_org_role(OrgRole.admin))]


@router.get("/kb-inventory/export")
async def export_kb_inventory(
    admin: OrgAdmin,
    db: Annotated[AsyncSession, Depends(get_db)],
    file_format: Annotated[
        Literal["csv", "json"],
        Query(alias="format"),
    ] = "csv",
    kb_id: Annotated[UUID | None, Query()] = None,
    include_trash: Annotated[bool, Query()] = False,
) -> Response:
    """导出组织可见资料库文档 metadata；默认不含 trash；上限 EXPORT_MAX_ROWS。"""
    items, total_matched, truncated = await collect_kb_inventory(
        db,
        admin,
        max_rows=EXPORT_MAX_ROWS,
        kb_id=kb_id,
        include_trash=include_trash,
    )

    if file_format == "json":
        body = render_inventory_json(
            items,
            total_matched=total_matched,
            truncated=truncated,
            export_limit=EXPORT_MAX_ROWS,
            include_trash=include_trash,
        )
        media = "application/json; charset=utf-8"
        filename = "kb-inventory.json"
    else:
        body = render_inventory_csv(items)
        media = "text/csv; charset=utf-8"
        filename = "kb-inventory.csv"

    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
        "X-Export-Total-Matched": str(total_matched),
        "X-Export-Count": str(len(items)),
        "X-Export-Truncated": "1" if truncated else "0",
        "X-Export-Limit": str(EXPORT_MAX_ROWS),
        "X-Export-Include-Trash": "1" if include_trash else "0",
    }
    return Response(content=body, media_type=media, headers=headers)
