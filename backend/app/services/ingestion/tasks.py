"""Celery task 定义 — 异步文档 ingestion。"""
from __future__ import annotations

import logging
import threading
from uuid import UUID

import anyio

from app.services.ingestion.celery_app import celery_app
from app.services.ingestion.pipeline import process_document_ingestion

logger = logging.getLogger(__name__)

# Celery --pool=threads + anyio.run() creates a fresh event loop per task.
# The process-global AsyncEngine/asyncpg pool must not be shared across those
# loops (RuntimeError: Future attached to a different loop). Serialize one
# loop-bound ingest at a time and dispose the pool when the loop ends.
_INGEST_LOOP_LOCK = threading.Lock()


async def _process_document_on_fresh_loop(doc_id: str):
    from app.core.database import engine

    try:
        return await process_document_ingestion(UUID(doc_id))
    finally:
        await engine.dispose()


@celery_app.task(
    bind=True,
    name="ingestion.process_document",
    autoretry_for=(Exception,),
    max_retries=3,
    default_retry_delay=5,
    acks_late=True,
)
def ingest_document_task(self, doc_id: str) -> dict:
    """Celery task：异步执行文档入库管道。

    Args:
        doc_id: Document.id 的字符串形式（UUID）。

    Returns:
        {"status": "completed" | "failed" | "skipped", "doc_id": doc_id}
    """
    logger.info("ingestion task started: doc_id=%s attempt=%d", doc_id, self.request.retries)
    try:
        with _INGEST_LOOP_LOCK:
            outcome = anyio.run(_process_document_on_fresh_loop, doc_id)
        logger.info(
            "ingestion task finished: doc_id=%s outcome=%s",
            doc_id,
            outcome.value,
        )
        return {"status": outcome.value, "doc_id": doc_id}
    except Exception:
        logger.exception("ingestion task failed: doc_id=%s", doc_id)
        raise  # Celery 根据 autoretry_for 自动重试
