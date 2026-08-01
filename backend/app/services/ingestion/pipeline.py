"""入库管道：解析 → 结构优先切片 → 嵌入 → document_chunks + pgvector。"""

from __future__ import annotations

import asyncio
import os
from app.services.rag.cjk import segment_cjk
import logging

# 并发 ingestion 上限（防止 BackgroundTasks 无界堆积）
_INGESTION_SEMAPHORE = asyncio.Semaphore(5)

import uuid

from datetime import datetime, timezone

from pathlib import Path

from uuid import UUID



from sqlalchemy import delete, select, text



from app.core.database import SessionLocal

from app.models.document import Document

from app.models.document_chunk import DocumentChunk

from app.models.enums import DocumentStatus

from app.models.webhook import Webhook

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
from app.services.rag.embed_route import REASON_EMBEDDING_EN_FAILED, is_mostly_english
from app.services.rag.entity_extractor import extract_entities_for_document


logger = logging.getLogger(__name__)

_PASSTHROUGH_MESSAGES = frozenset(
    {
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
    from app.services.ingestion.ocr_errors import (
        OCR_RUNTIME_ERROR,
        OCR_USER_MESSAGES,
        OcrFailure,
        message_for,
        reason_from_exception,
    )

    if isinstance(exc, OcrFailure):
        return str(exc).strip() or message_for(exc.reason)

    reason = reason_from_exception(exc)
    if reason is not None:
        text = str(exc).strip()
        # 超页数等动态文案保留原句；其余走字典统一口径
        if reason == "ocr_page_limit" and text.startswith("扫描页数超过上限"):
            return text
        return message_for(reason)

    if isinstance(exc, ValueError):
        message = str(exc).strip()
        if message in _PASSTHROUGH_MESSAGES or message in OCR_USER_MESSAGES.values():
            return message
        if message.startswith("扫描页数超过上限"):
            return message
        if message.startswith("不支持的文件类型"):
            return message
        return message or "文档处理失败，请稍后重试"

    if isinstance(exc, RuntimeError):
        message = str(exc).strip()
        if parser_mode == "ocr":
            return message_for(OCR_RUNTIME_ERROR)
        return message or "文档处理失败，请稍后重试"

    if isinstance(exc, FileNotFoundError):
        return str(exc).strip() or "文件不存在"

    if parser_mode == "ocr":
        return message_for(OCR_RUNTIME_ERROR)

    return "文档处理失败，请稍后重试"


def _ingestion_failure_reason(exc: BaseException, *, parser_mode: str | None) -> str | None:
    from app.services.ingestion.ocr_errors import reason_from_exception

    reason = reason_from_exception(exc)
    if reason is not None:
        return reason
    if parser_mode == "ocr":
        return "ocr_runtime_error"
    return None





async def _mark_failed(document_id: UUID, message: str) -> None:

    async with SessionLocal() as db:

        doc = await db.get(Document, document_id)

        if doc is None:

            return

        doc.status = DocumentStatus.failed

        doc.error_message = message[:2000]

        doc.processing_completed_at = datetime.now(timezone.utc)

        from app.services.ingestion.progress import clear_progress_fields

        clear_progress_fields(doc)

        await db.commit()





def _is_searchable(draft: ChunkDraft) -> bool:

    return draft.chunk_kind != "parent"





async def _write_chunks(

    db,

    *,

    doc: Document,

    drafts: list[ChunkDraft],

    vectors: list[list[float]],
    vectors_en: list[list[float]] | None = None,

) -> int:

    await db.execute(

            delete(DocumentChunk).where(DocumentChunk.document_id == doc.id)

    )



    parent_ids: dict[str, UUID] = {}

    vector_iter = iter(vectors)
    vector_en_iter = iter(vectors_en) if vectors_en else None
    vector_en_iter = iter(vectors_en) if vectors_en else None



    for draft in drafts:

            parent_chunk_id = None

            if draft.parent_group and draft.chunk_kind != "parent":

                parent_chunk_id = parent_ids.get(draft.parent_group)



            embedding = None
            embed_model = None
            embedding_en = None

            if _is_searchable(draft):

                try:
                    embedding = next(vector_iter)
                    embed_model = current_embedding_model()
                    if vector_en_iter:
                        embedding_en = next(vector_en_iter, None)
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

            embedding_en=embedding_en,

        )

            db.add(chunk)

            await db.flush()



            if draft.chunk_kind == "parent" and draft.parent_group:

                parent_ids[draft.parent_group] = chunk.id



            if not _is_searchable(draft):

                continue



            tsv_source = segment_cjk(" ".join(

            part

            for part in (draft.heading_path, draft.section_title, draft.content)

            if part

        ))

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



        from app.core.config import settings
        from app.services.ingestion.progress import (
            STAGE_CHUNKING,
            STAGE_EMBEDDING,
            STAGE_PARSING,
            ProgressThrottler,
            percent_for_ocr_page,
            set_completed_progress,
            update_document_progress,
        )

        config = IngestionConfig(
            max_chars=settings.chunk_max_chars,
            table_chunk_split_enabled=settings.table_chunk_split_enabled,
            table_parent_max_chars=settings.table_parent_max_chars,
            table_row_overlap=settings.table_row_overlap,
        )
        parser_mode = _pdf_parser_mode(path, file_type)
        if parser_mode:
            logger.info(
                "ingestion parsing: document=%s ingestion.parser=%s",
                document_id,
                parser_mode,
            )

        await update_document_progress(
            document_id, stage=STAGE_PARSING, percent=10
        )

        loop = asyncio.get_running_loop()
        throttler = ProgressThrottler(0.5)

        def on_page(page_number: int, page_count: int) -> None:
            if not throttler.allow(page_number, page_count):
                return
            fut = asyncio.run_coroutine_threadsafe(
                update_document_progress(
                    document_id,
                    stage=STAGE_PARSING,
                    percent=percent_for_ocr_page(page_number, page_count),
                    detail=f"第 {page_number}/{page_count} 页",
                ),
                loop,
            )
            fut.result(timeout=60)

        blocks = await asyncio.to_thread(
            parse_document,
            path,
            file_type,
            pdf_batch_pages=config.pdf_batch_pages,
            on_page=on_page,
        )

        await update_document_progress(
            document_id, stage=STAGE_CHUNKING, percent=50
        )
        drafts = structure_chunk(blocks, config)

        if not drafts:

            raise ValueError("解析后无有效文本内容")



        searchable = [d for d in drafts if _is_searchable(d)]

        embed_inputs = [

            embedding_input_text(d.heading_path, d.content) for d in searchable

        ]

        await update_document_progress(
            document_id, stage=STAGE_EMBEDDING, percent=70
        )
        vectors = await try_embed_texts(embed_inputs)
        if vectors is None:
            logger.warning("embedding degraded: document=%s fallback to FTS-only", document_id)
            vectors = []

        await update_document_progress(
            document_id, stage=STAGE_EMBEDDING, percent=90
        )

        async with SessionLocal() as db:

            doc = await db.get(Document, document_id)

            if doc is None:

                return



            vectors_en = None
            full_text = " ".join(d.content for d in drafts if d.content)
            if is_mostly_english(full_text):
                try:
                    vectors_en = await embed_texts(embed_inputs, provider="bge_en")
                except Exception as e:
                    logger.warning(
                        "embedding_en failed: document=%s reason=%s err=%s",
                        document_id,
                        REASON_EMBEDDING_EN_FAILED,
                        e,
                    )
                    vectors_en = None

            chunk_count = await _write_chunks(db, doc=doc, drafts=drafts, vectors=vectors, vectors_en=vectors_en)

            # D1 GraphRAG：实体抽取（临时跳过：OOM 保护，评测 Hit@3 不需要实体图谱；恢复时删除此跳过）
            if os.environ.get("SKIP_ENTITY_EXTRACT") == "1":
                doc.entity_extracted_at = datetime.now(timezone.utc)
            else:
                await extract_entities_for_document(db, doc)
                doc.entity_extracted_at = datetime.now(timezone.utc)

            doc.status = DocumentStatus.completed

            doc.chunk_count = chunk_count

            doc.processing_completed_at = datetime.now(timezone.utc)

            set_completed_progress(doc)

            await db.commit()

            # 触发 webhook（不阻塞 ingestion）
            await _trigger_webhooks(db, doc, completed=True, chunk_count=chunk_count)

            logger.info(
            "ingestion completed: document=%s chunks=%s ingestion.parser=%s",
            document_id,
            chunk_count,
            parser_mode or "default",
        )

    except Exception as exc:
            user_message = _user_facing_ingestion_error(exc, parser_mode=parser_mode)
            fail_reason = _ingestion_failure_reason(exc, parser_mode=parser_mode)
            logger.exception(
            "ingestion failed: document=%s ingestion.parser=%s reason=%s error=%s",
            document_id,
            parser_mode or "default",
            fail_reason or "unknown",
            user_message,
        )
            await _mark_failed(document_id, user_message)

    webhook_error = user_message if "exc" in dir() else None
    if webhook_error:
        await _trigger_webhooks_on_failure(document_id, webhook_error)


async def _trigger_webhooks(
    db,
    doc,
    *,
    completed: bool,
    chunk_count: int | None = None,
) -> None:
    """Ingestion 完成后触发 kb_id 关联的 webhook。"""
    try:
        from app.services.webhook.sender import send_webhook, build_webhook_payload

        result = await db.execute(
            select(Webhook).where(
                Webhook.kb_id == doc.kb_id,
                Webhook.is_active == True,
                Webhook.events.contains("document.completed"),
            )
        )
        for wh in result.scalars().all():
            payload = build_webhook_payload(
                event="document.completed",
                kb_id=doc.kb_id,
                doc_id=doc.id,
                filename=doc.filename,
                status="completed",
                chunk_count=chunk_count,
            )
            await send_webhook(wh.url, wh.secret, "document.completed", payload)
    except Exception as exc:
        logger.warning("webhook trigger failed (non-blocking): %s", exc)


async def _trigger_webhooks_on_failure(document_id: UUID, error_message: str) -> None:
    """Ingestion 失败后触发 webhook。"""
    try:
        from app.core.database import SessionLocal
        from app.services.webhook.sender import send_webhook, build_webhook_payload

        async with SessionLocal() as db:
            doc = await db.get(Document, document_id)
            if doc is None:
                return
            result = await db.execute(
                select(Webhook).where(
                    Webhook.kb_id == doc.kb_id,
                    Webhook.is_active == True,
                    Webhook.events.contains("document.completed"),
                )
            )
            for wh in result.scalars().all():
                payload = build_webhook_payload(
                    event="document.failed",
                    kb_id=doc.kb_id,
                    doc_id=doc.id,
                    filename=doc.filename,
                    status="failed",
                    error=error_message,
                )
                await send_webhook(wh.url, wh.secret, "document.failed", payload)
    except Exception as exc:
        logger.warning("webhook failure trigger failed (non-blocking): %s", exc)


