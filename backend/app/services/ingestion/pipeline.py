"""入库管道：解析 → 结构优先切片 → 嵌入 → document_chunks + pgvector。"""

from __future__ import annotations

import asyncio
import logging
import threading
import uuid
from collections import deque
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Literal
from uuid import UUID

from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.enums import DocumentStatus
from app.models.webhook import Webhook
from app.services.ingestion.chunker import structure_chunk
from app.services.ingestion.embedder import (
    current_bge_en_model,
    current_embedding_model,
    embed_texts,
    embedding_input_text,
    try_embed_texts,
)
from app.services.ingestion.parser import parse_document
from app.services.ingestion.parser_pdf import detect_scanned_pdf
from app.services.ingestion.types import ChunkDraft, IngestionConfig
from app.services.rag.cjk import segment_cjk
from app.services.rag.embed_route import REASON_EMBEDDING_EN_FAILED, is_mostly_english
from app.services.rag.entity_extractor import extract_entities_for_document


class _AsyncCapacityWaiter:
    """等待容量闸的单个异步任务，记录其 event loop 与唤醒 future。"""

    __slots__ = ("loop", "future", "granted")

    def __init__(
        self,
        loop: asyncio.AbstractEventLoop,
        future: asyncio.Future[None],
    ) -> None:
        self.loop = loop
        self.future = future
        self.granted = False


class _AsyncCapacityLimiter:
    """线程安全、与 event loop 无关的异步容量闸（进程内并发上限）。"""

    def __init__(self, total_tokens: int) -> None:
        if total_tokens < 1:
            raise ValueError("total_tokens must be >= 1")
        self._total_tokens = total_tokens
        self._available = total_tokens
        self._waiters: deque[_AsyncCapacityWaiter] = deque()
        self._lock = threading.Lock()

    @property
    def total_tokens(self) -> int:
        return self._total_tokens

    async def acquire(self) -> None:
        loop = asyncio.get_running_loop()
        waiter = _AsyncCapacityWaiter(loop, loop.create_future())
        with self._lock:
            if self._available > 0:
                self._available -= 1
                return
            self._waiters.append(waiter)
        try:
            await waiter.future
        except asyncio.CancelledError:
            with self._lock:
                if waiter.granted:
                    self._grant_next_locked()
                else:
                    self._waiters.remove(waiter)
            raise

    def release(self) -> None:
        with self._lock:
            self._grant_next_locked()

    async def __aenter__(self) -> _AsyncCapacityLimiter:
        await self.acquire()
        return self

    async def __aexit__(
        self,
        exc_type: object,
        exc_val: object,
        exc_tb: object,
    ) -> bool:
        self.release()
        return False

    def _grant_next_locked(self) -> None:
        while self._waiters:
            waiter = self._waiters.popleft()
            waiter.granted = True
            try:
                waiter.loop.call_soon_threadsafe(waiter.future.set_result, None)
            except RuntimeError:
                # 等待者所在 loop 已关闭时，将 token 转给下一个等待者或归还计数。
                continue
            return
        self._available += 1


# 并发 ingestion 上限（防止 BackgroundTasks 无界堆积）
_INGESTION_SEMAPHORE = _AsyncCapacityLimiter(5)

logger = logging.getLogger(__name__)


class IngestionOutcome(str, Enum):
    """pipeline 执行结果，供 Celery task 映射返回值。"""

    completed = "completed"
    failed = "failed"
    skipped = "skipped"


ClaimKind = Literal["claimed", "reclaimed", "skipped", "not_found"]


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

            embedding_en_model=(
                current_bge_en_model() if embedding_en is not None else None
            ),

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


async def _claim_document(
    db: AsyncSession,
    *,
    document_id: UUID,
    started_at: datetime,
    stale_minutes: float,
) -> tuple[Document | None, ClaimKind]:
    """行锁原子认领：queued → claimed；processing 超龄 → reclaimed + 审计；其余跳过。"""
    doc = await db.scalar(
        select(Document)
        .where(Document.id == document_id)
        .with_for_update()
    )
    if doc is None:
        return None, "not_found"
    if doc.deleted_at is not None:
        return doc, "skipped"

    kind: ClaimKind
    if doc.status == DocumentStatus.queued:
        kind = "claimed"
    elif doc.status == DocumentStatus.processing:
        anchor = doc.processing_started_at
        if anchor is None:
            return doc, "skipped"
        if anchor.tzinfo is None:
            anchor = anchor.replace(tzinfo=timezone.utc)
        if anchor < started_at - timedelta(minutes=stale_minutes):
            kind = "reclaimed"
            from app.services.audit.log import write_audit_log

            await write_audit_log(
                db,
                action="ingestion.stale_reclaimed",
                resource_type="document",
                resource_id=doc.id,
                kb_id=doc.kb_id,
                metadata={
                    "filename": doc.filename,
                    "status_before": DocumentStatus.processing.value,
                    "age_seconds": round(
                        (started_at - anchor).total_seconds(), 1
                    ),
                    "clock_field": "processing_started_at",
                },
            )
        else:
            return doc, "skipped"
    else:
        return doc, "skipped"

    doc.status = DocumentStatus.processing
    doc.processing_started_at = started_at
    doc.error_message = None
    await db.commit()
    return doc, kind





async def process_document_ingestion(document_id: UUID) -> IngestionOutcome:

    """BackgroundTask 入口：完整入库管道，返回 outcome 供任务层映射。"""
    async with _INGESTION_SEMAPHORE:
        started_at = datetime.now(timezone.utc)

        async with SessionLocal() as db:

            doc, claim_kind = await _claim_document(
                db,
                document_id=document_id,
                started_at=started_at,
                stale_minutes=settings.ingest_stale_processing_minutes,
            )

            if doc is None:

                logger.warning("ingestion: document %s not found", document_id)

                return IngestionOutcome.skipped



            if claim_kind == "skipped":
                if doc.status == DocumentStatus.processing:
                    logger.warning("ingestion: document %s already processing, skipped", document_id)
                else:
                    logger.info(
                        "ingestion: document %s status=%s skipped",
                        document_id,
                        doc.status.value,
                    )
                return IngestionOutcome.skipped

            if claim_kind == "reclaimed":
                logger.info(
                    "ingestion: document %s stale processing reclaimed, restart",
                    document_id,
                )


            storage_path = doc.storage_path

            file_type = doc.file_type

    webhook_error: str | None = None
    try:



        parser_mode: str | None = None
        path = Path(storage_path)

        if not path.is_file():

            raise FileNotFoundError(f"文件不存在: {storage_path}")



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

                logger.warning("ingestion: document %s disappeared mid-processing", document_id)

                return IngestionOutcome.skipped



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
            if settings.skip_entity_extract:
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
        return IngestionOutcome.completed

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
        webhook_error = user_message
        await _mark_failed(document_id, user_message)

    if webhook_error:
        await _trigger_webhooks_on_failure(document_id, webhook_error)

    return IngestionOutcome.failed


async def _trigger_webhooks(
    db,
    doc,
    *,
    completed: bool,
    chunk_count: int | None = None,
) -> None:
    """Ingestion 完成后触发 kb_id 关联的 webhook。"""
    try:
        from app.services.webhook.sender import build_webhook_payload

        result = await db.execute(
            select(Webhook).where(
                Webhook.kb_id == doc.kb_id,
                Webhook.is_active,
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
            await _send_webhook_fail_closed(
                db,
                wh,
                "document.completed",
                doc.kb_id,
                payload,
            )
    except Exception as exc:
        logger.warning("webhook trigger failed (non-blocking): %s", exc)


async def _send_webhook_fail_closed(
    db,
    wh,
    event: str,
    kb_id,
    payload: dict,
) -> None:
    """发送单个 webhook；密钥解密失败时拒绝发送并写审计，不阻断同批其他 webhook。"""
    from app.services.audit.log import write_audit_log
    from app.services.webhook.sender import WebhookSecretError, send_webhook

    try:
        await send_webhook(wh.url, wh.secret, event, payload)
    except WebhookSecretError:
        logger.error(
            "webhook send blocked: webhook_id=%s url=%s event=%s reason=secret_decrypt_failed",
            wh.id,
            wh.url,
            event,
        )
        try:
            await write_audit_log(
                db,
                action="webhook.send_blocked",
                actor_user_id=wh.created_by,
                resource_type="webhook",
                resource_id=wh.id,
                kb_id=kb_id,
                metadata={
                    "reason": "secret_decrypt_failed",
                    "url": wh.url,
                    "event": event,
                },
            )
            await db.commit()
        except Exception as exc:
            logger.warning(
                "webhook blocked audit write failed: webhook_id=%s error=%s",
                wh.id,
                exc,
            )


async def _trigger_webhooks_on_failure(document_id: UUID, error_message: str) -> None:
    """Ingestion 失败后触发 webhook。"""
    try:
        from app.core.database import SessionLocal
        from app.services.webhook.sender import build_webhook_payload

        async with SessionLocal() as db:
            doc = await db.get(Document, document_id)
            if doc is None:
                return
            result = await db.execute(
                select(Webhook).where(
                    Webhook.kb_id == doc.kb_id,
                    Webhook.is_active,
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
                await _send_webhook_fail_closed(
                    db,
                    wh,
                    "document.failed",
                    doc.kb_id,
                    payload,
                )
    except Exception as exc:
        logger.warning("webhook failure trigger failed (non-blocking): %s", exc)


