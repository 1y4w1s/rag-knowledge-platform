"""文档 API 路由（Wave 2.2+）。"""

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Query,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.request_ip import get_client_ip
from app.core.deps import CurrentUser, KbAction, get_current_user, require_kb_access
from app.services.auth.api_rate_limit import ApiRateLimitKind, enforce_api_rate_limit
from app.models.document import Document
from app.models.enums import DocumentVisibility, DocumentVisibility as DocVisEnum
from app.schemas.document import (
    DocumentListResponse,
    DocumentResponse,
    DocumentUploadResponse,
)
from app.services.documents.lifecycle import delete_document, retry_document
from app.services.documents.listing import get_document, list_documents
from app.services.documents.preview import get_document_preview
from app.services.documents.upload import upload_documents

router = APIRouter(
    prefix="/knowledge-bases/{kb_id}/documents",
    tags=["documents"],
)


@router.get("", response_model=DocumentListResponse)
async def get_documents(
    kb_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: Annotated[int | None, Query(ge=1, le=100)] = None,
    offset: Annotated[int | None, Query(ge=0)] = None,
    file_type: Annotated[list[str] | None, Query()] = None,
    status: Annotated[list[str] | None, Query()] = None,
    uploaded_from: Annotated[date | None, Query()] = None,
    uploaded_to: Annotated[date | None, Query()] = None,
) -> DocumentListResponse:
    return await list_documents(
        db,
        current_user,
        kb_id,
        limit=limit,
        offset=offset,
        file_type=file_type,
        status=status,
        uploaded_from=uploaded_from,
        uploaded_to=uploaded_to,
    )


# ── 回收站 ────────────────────────────────────────────
# 注意：GET /trash 必须在 GET /{doc_id} 之前注册，
# 否则 "trash" 被当作 UUID 解析返回 422。


@router.get("/trash", response_model=list[DocumentResponse])
async def get_trash(
    kb_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[DocumentResponse]:
    """列回收站中的文档。"""
    from app.services.documents.trash import list_trash as _list_trash

    await require_kb_access(
        kb_id=kb_id, action=KbAction.read, current_user=current_user, db=db
    )
    return await _list_trash(db, kb_id)


@router.post("/{doc_id}/restore", response_model=DocumentResponse)
async def restore_document_route(
    kb_id: UUID,
    doc_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DocumentResponse:
    """从回收站恢复文档。"""
    from app.services.documents.trash import restore_document as _restore

    await require_kb_access(
        kb_id=kb_id, action=KbAction.write, current_user=current_user, db=db
    )
    return await _restore(db, kb_id, doc_id)


@router.delete("/{doc_id}/permanent", status_code=204)
async def permanently_delete_document_route(
    kb_id: UUID,
    doc_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """永久删除回收站中的文档（物理删除）。"""
    from app.services.documents.lifecycle import (
        permanently_delete_document as _perma_delete,
    )

    await require_kb_access(
        kb_id=kb_id, action=KbAction.write, current_user=current_user, db=db
    )
    await _perma_delete(db, kb_id, doc_id)


@router.get("/{doc_id}", response_model=DocumentResponse)
async def get_document_route(
    kb_id: UUID,
    doc_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DocumentResponse:
    return await get_document(db, current_user, kb_id, doc_id)


@router.post(
    "",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def post_documents(
    kb_id: UUID,
    request: Request,
    background_tasks: BackgroundTasks,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    files: Annotated[list[UploadFile], File(...)],
    visibility: Annotated[DocumentVisibility | None, Query()] = None,
) -> DocumentUploadResponse:
    enforce_api_rate_limit(ApiRateLimitKind.upload, current_user.id)

    docs = await upload_documents(
        db,
        current_user,
        kb_id,
        files,
        background_tasks,
        ip=get_client_ip(request),
        visibility=visibility,
    )
    # 文档上传后清空该 KB 的检索缓存
    from app.services.rag.cache import clear_query_cache
    await clear_query_cache(kb_id=kb_id)
    return DocumentUploadResponse(documents=docs)


@router.delete("/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document_route(
    kb_id: UUID,
    doc_id: UUID,
    request: Request,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    await delete_document(
        db, current_user, kb_id, doc_id, ip=get_client_ip(request)
    )


@router.post("/{doc_id}/retry", response_model=DocumentResponse)
async def retry_document_route(
    kb_id: UUID,
    doc_id: UUID,
    request: Request,
    background_tasks: BackgroundTasks,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DocumentResponse:
    return await retry_document(
        db,
        current_user,
        kb_id,
        doc_id,
        background_tasks,
        ip=get_client_ip(request),
    )


@router.get("/{doc_id}/preview")
async def get_document_preview_route(
    kb_id: UUID,
    doc_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> FileResponse:
    return await get_document_preview(db, current_user, kb_id, doc_id)


# ── 文档可见性 ────────────────────────────────────────



class UpdateVisibilityRequest(BaseModel):
    visibility: DocVisEnum


@router.patch("/{doc_id}/visibility", response_model=DocumentResponse)
async def update_document_visibility(
    kb_id: UUID,
    doc_id: UUID,
    body: UpdateVisibilityRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DocumentResponse:
    """修改文档可见性（仅上传者/团队 Admin/Owner 可操作）。"""
    from app.models.enums import DocumentVisibility, DocumentVisibility as DocVisEnum
    from app.services.documents.listing import get_document

    doc_resp = await get_document(db, current_user, kb_id, doc_id)
    doc = await db.get(Document, doc_id)

    # 权限检查：上传者 或 团队 Admin/Owner 可改
    is_admin = (
        current_user.account_type.value == "enterprise"
        and current_user.org_role.value == "admin"
    )
    if (
        doc.uploaded_by != current_user.id
        and not is_admin
        and not current_user.is_owner
    ):
        from fastapi import HTTPException as FastAPIHTTPException
        raise FastAPIHTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="权限不足，仅文档上传者或团队管理员可修改可见性",
        )

    doc.visibility = body.visibility
    await db.flush()
    return DocumentResponse.model_validate(doc)


