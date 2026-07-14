"""文档预览（Wave 2.4）。"""

import uuid
from pathlib import Path

from fastapi import status
from fastapi.responses import FileResponse
from app.core.exceptions import NotFoundError, ConflictError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, KbAction, require_kb_access
from app.models.document import Document
from app.models.enums import AccountType, DocumentStatus, DocumentVisibility, OrgRole

_CONTENT_TYPES: dict[str, str] = {
    "pdf": "application/pdf",
    "txt": "text/plain; charset=utf-8",
    "md": "text/plain; charset=utf-8",
    "docx": (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    ),
    "xlsx": (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    ),
    "pptx": (
        "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    ),
}


def media_type_for_file_type(file_type: str) -> str:
    """按 documents.file_type 返回预览 Content-Type。"""
    return _CONTENT_TYPES.get(file_type, "application/octet-stream")


async def get_document_preview(
    db: AsyncSession,
    current_user: CurrentUser,
    kb_id: uuid.UUID,
    doc_id: uuid.UUID,
) -> FileResponse:
    """返回已完成文档的原始文件流（PDF / 文本等）。"""
    await require_kb_access(
        kb_id=kb_id,
        action=KbAction.read,
        current_user=current_user,
        db=db,
    )

    doc = await db.get(Document, doc_id)
    if doc is None or doc.kb_id != kb_id:
        raise NotFoundError("文档不存在")

    if (
        doc.visibility == DocumentVisibility.admin_only
        and current_user.account_type.value == AccountType.enterprise
        and current_user.org_role == OrgRole.member
    ):
        raise NotFoundError("文档不存在")

    if doc.status != DocumentStatus.completed:
        raise ConflictError("文档尚未入库完成，暂不可预览")

    file_path = Path(doc.storage_path)
    if not file_path.is_file():
        raise NotFoundError("文档文件不存在")

    return FileResponse(
        path=file_path,
        media_type=media_type_for_file_type(doc.file_type),
        filename=doc.filename,
    )
