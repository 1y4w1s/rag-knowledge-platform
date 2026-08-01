"""文档入库入队：开发 eager/BackgroundTasks；生产 Celery delay。

G1：统一 upload / retry / adopt / batch / versions，避免半切。
"""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import BackgroundTasks

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.document import Document
from app.models.enums import DocumentStatus
from app.services.ingestion.pipeline import process_document_ingestion
from app.services.ingestion.tasks import ingest_document_task

logger = logging.getLogger(__name__)

_ENQUEUE_FAIL_MSG = "任务队列不可用，请稍后重试或联系管理员"


async def _mark_ingest_enqueue_failed(document_id: UUID) -> None:
    """delay 失败：仅当仍为 queued 时标 failed（F-log）。"""
    async with SessionLocal() as db:
        doc = await db.get(Document, document_id)
        if doc is None or doc.status != DocumentStatus.queued:
            return
        doc.status = DocumentStatus.failed
        doc.error_message = _ENQUEUE_FAIL_MSG
        await db.commit()


async def _celery_delay(document_id: UUID) -> None:
    try:
        ingest_document_task.delay(str(document_id))
    except Exception:
        logger.exception("ingestion Celery enqueue failed: doc_id=%s", document_id)
        await _mark_ingest_enqueue_failed(document_id)


async def enqueue_document_ingestion(
    document_id: UUID,
    background_tasks: BackgroundTasks | None = None,
) -> None:
    """按开关入队 ``process_document_ingestion``。

    - eager（默认）：须有 ``BackgroundTasks``，否则只打日志、不入队（A-bt）。
    - 非 eager：有 BT 时延后 delay（便于 adopt 在 commit 前调用）；无 BT 则立即 delay。
    - delay 抛错 → 文档 queued→failed（F-log）。
    """
    if settings.celery_task_always_eager_local:
        if background_tasks is None:
            logger.warning(
                "ingestion enqueue skipped: eager mode requires BackgroundTasks doc_id=%s",
                document_id,
            )
            return
        background_tasks.add_task(process_document_ingestion, document_id)
        return

    if background_tasks is not None:
        background_tasks.add_task(_celery_delay, document_id)
        return

    await _celery_delay(document_id)


__all__ = ["enqueue_document_ingestion"]
