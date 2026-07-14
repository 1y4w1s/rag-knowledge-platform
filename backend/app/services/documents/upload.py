"""文档上传与列表（Wave 2.2）。"""

import uuid
from pathlib import Path

import asyncio
from fastapi import BackgroundTasks, UploadFile, status
from app.core.exceptions import ValidationError, ConflictError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import CurrentUser, KbAction, require_kb_access
from app.models.document import Document
from app.models.enums import DocumentStatus, DocumentVisibility
from app.schemas.document import DocumentResponse
from app.services.audit.log import write_audit_log
from app.services.documents.content_hash import (
    assert_content_unique_in_kb,
    sha256_hex,
)
from app.services.ingestion.pipeline import process_document_ingestion

# 并发控制：最多 5 个文档同时处理
_INGESTION_SEMAPHORE = asyncio.Semaphore(5)

ALLOWED_EXTENSIONS: frozenset[str] = frozenset({".pdf", ".txt", ".md", ".docx", ".xlsx", ".pptx", ".png", ".jpg", ".jpeg"})


def _extension(filename: str | None) -> str:
    if not filename:
        return ""
    return Path(filename).suffix.lower()


def _validate_extension(filename: str | None) -> str:
    ext = _extension(filename)
    if ext not in ALLOWED_EXTENSIONS:
        raise ValidationError(
            detail=f"不支持的文件类型，仅允许: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )
    return ext.lstrip(".")


async def _read_upload_with_size_limit(upload: UploadFile) -> bytes:
    chunks: list[bytes] = []
    total = 0
    max_bytes = settings.upload_max_bytes

    while True:
        chunk = await upload.read(1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise ValidationError(
                detail=f"单文件不能超过 {max_bytes // (1024 * 1024)}MB",
            )
        chunks.append(chunk)

    return b"".join(chunks)


async def _assert_filename_available(
    db: AsyncSession,
    *,
    kb_id: uuid.UUID,
    filename: str,
) -> str:
    """同一资料库内文件名不可重复（忽略大小写）。"""
    safe_name = Path(filename).name.strip()
    if not safe_name:
        raise ValidationError("文件名无效")
    existing = await db.scalar(
        select(Document.id)
        .where(
            Document.kb_id == kb_id,
            func.lower(Document.filename) == safe_name.lower(),
        )
        .limit(1)
    )
    if existing is not None:
        raise ConflictError(
            detail=f"资料库中已存在同名文件「{safe_name}」",
        )
    return safe_name


def _storage_dir(kb_id: uuid.UUID, doc_id: uuid.UUID) -> Path:
    return Path(settings.upload_dir) / str(kb_id) / str(doc_id)


async def upload_documents(
    db: AsyncSession,
    current_user: CurrentUser,
    kb_id: uuid.UUID,
    files: list[UploadFile],
    background_tasks: BackgroundTasks,
    *,
    ip: str | None = None,
    visibility: DocumentVisibility | None = None,
) -> list[DocumentResponse]:
    if not files:
        raise ValidationError("请至少上传一个文件")

    await require_kb_access(
        kb_id=kb_id,
        action=KbAction.write,
        current_user=current_user,
        db=db,
    )

    created: list[DocumentResponse] = []
    batch_names: set[str] = set()
    batch_hashes: set[str] = set()

    for upload in files:
        original_name = upload.filename or "unnamed"
        file_type = _validate_extension(upload.filename)
        content = await _read_upload_with_size_limit(upload)
        display_name = Path(original_name).name.strip()
        if not display_name:
            raise ValidationError("文件名无效")
        if len(content) == 0:
            raise ValidationError(
                detail=f"文件「{display_name}」为空（0 字节），请添加内容后再上传",
            )
        content_hash = sha256_hex(content)
        if content_hash in batch_hashes:
            raise ValidationError(
                detail=f"本次选择了内容相同的文件「{display_name}」，请去掉重复项后重试",
            )
        batch_hashes.add(content_hash)
        name_key = display_name.lower()
        if name_key in batch_names:
            raise ValidationError(
                detail=f"本次选择了重复文件「{display_name}」，请去掉重复项后重试",
            )
        batch_names.add(name_key)
        display_name = await _assert_filename_available(
            db,
            kb_id=kb_id,
            filename=original_name,
        )
        await assert_content_unique_in_kb(
            db,
            kb_id=kb_id,
            content_sha256=content_hash,
        )

        doc_id = uuid.uuid4()
        storage_dir = _storage_dir(kb_id, doc_id)
        storage_dir.mkdir(parents=True, exist_ok=True)

        stored_name = f"{uuid.uuid4()}.{file_type}"
        storage_path = storage_dir / stored_name
        storage_path.write_bytes(content)

        doc = Document(
            id=doc_id,
            kb_id=kb_id,
            filename=display_name,
            file_type=file_type,
            file_size=len(content),
            content_sha256=content_hash,
            storage_path=str(storage_path),
            status=DocumentStatus.queued,
            uploaded_by=current_user.id,
            visibility=visibility or DocumentVisibility.everyone,
        )
        db.add(doc)
        await db.flush()

        await write_audit_log(
            db,
            action="document.upload",
            actor_user_id=current_user.id,
            resource_type="document",
            resource_id=doc_id,
            kb_id=kb_id,
            metadata={"filename": display_name},
            ip=ip,
        )

        async with _INGESTION_SEMAPHORE:
            background_tasks.add_task(process_document_ingestion, doc.id)
        created.append(DocumentResponse.model_validate(doc))

    await db.commit()
    return created
