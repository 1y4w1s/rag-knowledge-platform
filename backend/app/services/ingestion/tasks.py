"""Celery task 定义 — 异步文档 ingestion。"""
from __future__ import annotations

import anyio
import asyncio
import logging
from uuid import UUID

from app.services.ingestion.celery_app import celery_app
from app.services.ingestion.pipeline import process_document_ingestion

logger = logging.getLogger(__name__)


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
        {"status": "completed", "doc_id": doc_id}
        或 {"status": "failed", "doc_id": doc_id, "error": "..."}
    """
    logger.info("ingestion task started: doc_id=%s attempt=%d", doc_id, self.request.retries)
    try:
        anyio.run(process_document_ingestion, UUID(doc_id))
        logger.info("ingestion task completed: doc_id=%s", doc_id)
        return {"status": "completed", "doc_id": doc_id}
    except Exception as exc:
        logger.exception("ingestion task failed: doc_id=%s", doc_id)
        raise  # Celery 根据 autoretry_for 自动重试
