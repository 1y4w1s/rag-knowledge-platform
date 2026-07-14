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
from app.core.deps import CurrentUser, get_current_user
from app.services.auth.api_rate_limit import ApiRateLimitKind, enforce_api_rate_limit
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
) -> DocumentUploadResponse:
    enforce_api_rate_limit(ApiRateLimitKind.upload, current_user.id)

    docs = await upload_documents(
        db,
        current_user,
        kb_id,
        files,
        background_tasks,
        ip=get_client_ip(request),
    )
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
