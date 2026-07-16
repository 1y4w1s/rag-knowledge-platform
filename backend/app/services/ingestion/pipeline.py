"""入库管道：解析 → 结构优先切片 → 嵌入 → document_chunks + pgvector。"""

from __future__ import annotations

import asyncio
import logging

# 并发 ingestion 上限（防止 BackgroundTasks 无界堆积）
_INGESTION_SEMAPHORE = asyncio.Semaphore(5)

import uuid

from datetime import datetime, timezone

from pathlib import Path

from uuid import UUID



from sqlalchemy import delete, text



from app.core.database import SessionLocal

from app.models.document import Document

from app.models.document_chunk import DocumentChunk

from app.models.enums import DocumentStatus

from app.services.ingestion.chunker import structure_chunk

from app.services.ingestion.embedder import (
    current_embedding_model,
    embed_texts,
    embedding_input_text,
    try_embed_texts,
)

from app.services.ingestion.parser import parse_document
from app.services.ingestion.parser_pdf import detect_scanned_pdf

from app.services.ingestion.types import ChunkDraft, IngestionConfig



logger = logging.getLogger(__name__)

_OCR_USER_MESSAGES = frozenset(
    {
        "不支持扫描件",
        "OCR 服务未启用",
        "OCR 未识别到文字",
        "解析后无有效文本内容",
    }
)


def _pdf_parser_mode(path: Path, file_type: str) -> str | None:
    ext = file_type.lower().lstrip(".")
    if ext != "pdf":
        return None
    return "ocr" if detect_scanned_pdf(path) else "pdfplumber"


def _user_facing_ingestion_error(
    exc: BaseException, *, parser_mode: str | None
) -> str:
    """将入库异常转为用户可见中文文案，避免 OCR 失败落成泛化英文/500 描述。"""
    if isinstance(exc, ValueError):
        message = str(exc).strip()
        if message in _OCR_USER_MESSAGES or message.startswith("扫描页数超过上限"):
            return message
        if message.startswith("不支持的文件类型"):
            return message
        return message or "文档处理失败，请稍后重试"

    if isinstance(exc, RuntimeError):
        message = str(exc).strip()
        if message == "OCR 服务未启用":
            return message
        if parser_mode == "ocr":
            return "OCR 处理失败，请确认文件为清晰扫描件或稍后重试"
        return message or "文档处理失败，请稍后重试"

    if isinstance(exc, FileNotFoundError):
        return str(exc).strip() or "文件不存在"

    if parser_mode == "ocr":
        return "OCR 处理失败，请确认文件为清晰扫描件或稍后重试"

    return "文档处理失败，请稍后重试"





async def _mark_failed(document_id: UUID, message: str) -> None:

    async with SessionLocal() as db:

        doc = await db.get(Document, document_id)

        if doc is None:

            return

        doc.status = DocumentStatus.failed

        doc.error_message = message[:2000]

        doc.processing_completed_at = datetime.now(timezone.utc)

        await db.commit()





def _is_searchable(draft: ChunkDraft) -> bool:

    return draft.chunk_kind != "parent"





async def _write_chunks(

    db,

    *,

    doc: Document,

    drafts: list[ChunkDraft],

    vectors: list[list[float]],

) -> int:

    await db.execute(

            delete(DocumentChunk).where(DocumentChunk.document_id == doc.id)

    )



    parent_ids: dict[str, UUID] = {}

    vector_iter = iter(vectors)



    for draft in drafts:

            parent_chunk_id = None

            if draft.parent_group and draft.chunk_kind != "parent":

                parent_chunk_id = parent_ids.get(draft.parent_group)



            embedding = None
            embed_model = None

            if _is_searchable(draft):

                try:
                    embedding = next(vector_iter)
                    embed_model = current_embedding_model()
                except StopIteration:
                    pass



            chunk = DocumentChunk(

            id=uuid.uuid4(),

            document_id=doc.id,

            kb_id=doc.kb_id,

            chunk_index=draft.chunk_index,

            page_number=draft.page_number,

            section_title=draft.section_title,

            heading_path=draft.heading_path,

            content=draft.content,

            parent_chunk_id=parent_chunk_id,

            chunk_kind=draft.chunk_kind,

            embedding_model=embed_model,

            embedding=embedding,

        )

            db.add(chunk)

            await db.flush()



            if draft.chunk_kind == "parent" and draft.parent_group:

                parent_ids[draft.parent_group] = chunk.id



            if not _is_searchable(draft):

                continue



            tsv_source = " ".join(

            part

            for part in (draft.heading_path, draft.section_title, draft.content)

            if part

        )

            await db.execute(

            text(

                "UPDATE document_chunks SET content_tsv = to_tsvector('simple', :tsv_source) "

                "WHERE id = :chunk_id"

            ),

            {"tsv_source": tsv_source, "chunk_id": chunk.id},

        )



    return len(drafts)





async def process_document_ingestion(document_id: UUID) -> None:

    """BackgroundTask 入口：完整入库管道。"""
    async with _INGESTION_SEMAPHORE:
        started_at = datetime.now(timezone.utc)

        async with SessionLocal() as db:

            doc = await db.get(Document, document_id)

            if doc is None:

                logger.warning("ingestion: document %s not found", document_id)

            return



            storage_path = doc.storage_path

            if doc.status == DocumentStatus.processing:
                logger.warning("ingestion: document %s already processing, skipped", document_id)
            return


            file_type = doc.file_type

            doc.status = DocumentStatus.processing

            doc.processing_started_at = started_at

            doc.error_message = None

            await db.commit()



    try:
        parser_mode: str | None = None
        path = Path(storage_path)

        if not path.is_file():

            raise FileNotFoundError(f"文件不存在: {storage_path}")



        config = IngestionConfig()
        parser_mode = _pdf_parser_mode(path, file_type)
        if parser_mode:
            logger.info(
                "ingestion parsing: document=%s ingestion.parser=%s",
                document_id,
                parser_mode,
            )

        blocks = parse_document(path, file_type, pdf_batch_pages=config.pdf_batch_pages)

        drafts = structure_chunk(blocks, config)

        if not drafts:

            raise ValueError("解析后无有效文本内容")



        searchable = [d for d in drafts if _is_searchable(d)]

        embed_inputs = [

            embedding_input_text(d.heading_path, d.content) for d in searchable

        ]

        vectors = await try_embed_texts(embed_inputs)
        if vectors is None:
            logger.warning("embedding degraded: document=%s fallback to FTS-only", document_id)
            vectors = []



        async with SessionLocal() as db:

            doc = await db.get(Document, document_id)

            if doc is None:

                return



            chunk_count = await _write_chunks(db, doc=doc, drafts=drafts, vectors=vectors)

            doc.status = DocumentStatus.completed

            doc.chunk_count = chunk_count

            doc.processing_completed_at = datetime.now(timezone.utc)

            await db.commit()



            logger.info(
            "ingestion completed: document=%s chunks=%s ingestion.parser=%s",
            document_id,
            chunk_count,
            parser_mode or "default",
        )

    except Exception as exc:
            user_message = _user_facing_ingestion_error(exc, parser_mode=parser_mode)
            logger.exception(
            "ingestion failed: document=%s ingestion.parser=%s error=%s",
            document_id,
            parser_mode or "default",
            user_message,
        )
            await _mark_failed(document_id, user_message)


