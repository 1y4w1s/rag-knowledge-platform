"""文档预览（Wave 2.4）。"""

import uuid
from pathlib import Path

from fastapi import status
from fastapi.responses import FileResponse, PlainTextResponse
from app.core.exceptions import NotFoundError, ConflictError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, KbAction, require_kb_access
from app.models.document import Document
from app.models.enums import AccountType, DocumentStatus, DocumentVisibility, OrgRole

_EXTRACTABLE: frozenset[str] = frozenset({"txt", "md", "docx"})


def _extract_text(file_path: Path, file_type: str) -> str | None:
    if file_type == "docx":
        try:
            from docx import Document as DocxDocument
            doc = DocxDocument(str(file_path))
            paras = [p.text for p in doc.paragraphs if p.text.strip()]
            return "\n".join(paras) if paras else None
        except Exception:
            return None
    return None

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
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
}


def media_type_for_file_type(file_type: str) -> str:
    """按 documents.file_type 返回预览 Content-Type。"""
    return _CONTENT_TYPES.get(file_type, "application/octet-stream")


# 浏览器可内嵌预览的类型（PDF + 图片）→ Content-Disposition: inline
_INLINE_TYPES: frozenset[str] = frozenset({"pdf", "png", "jpg", "jpeg", "txt", "md"})


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

    if doc.status not in (DocumentStatus.completed, DocumentStatus.failed):
        raise ConflictError("文档尚未入库完成，暂不可预览")

    file_path = Path(doc.storage_path)
    if not file_path.is_file():
        raise NotFoundError("文档文件不存在")

    if doc.file_type in _EXTRACTABLE:
        text = _extract_text(file_path, doc.file_type)
        if text is not None:
            return PlainTextResponse(text)

    # PDF / 图片 → 浏览器内嵌显示，不下载
    if doc.file_type in _INLINE_TYPES:
        return FileResponse(
            path=file_path,
            media_type=media_type_for_file_type(doc.file_type),
            headers={
                "Content-Disposition": f'inline; filename="{doc.filename}"'
            },
        )

    return FileResponse(
        path=file_path,
        media_type=media_type_for_file_type(doc.file_type),
        filename=doc.filename,
    )
