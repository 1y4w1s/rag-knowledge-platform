"""全库重嵌入：换 embedding 模型后批量更新已有 chunk 向量（Plan-RAG R2-4）。"""

from __future__ import annotations

import asyncio
import logging
from uuid import UUID

from sqlalchemy import func, select

from app.core.database import SessionLocal
from app.models.document_chunk import DocumentChunk
from app.services.ingestion.embedder import (
    current_embedding_model,
    embed_texts,
    embedding_input_text,
)

logger = logging.getLogger(__name__)

RE_EMBED_BATCH_SIZE = 25

_re_embed_lock = asyncio.Lock()


async def count_stale_chunks(*, kb_id: UUID | None = None) -> int:
    """需要重嵌的可检索 chunk 数量（parent 除外）。"""
    model = current_embedding_model()
    async with SessionLocal() as db:
        stmt = (
            select(func.count())
            .select_from(DocumentChunk)
            .where(DocumentChunk.chunk_kind != "parent")
            .where(
                (DocumentChunk.embedding_model.is_(None))
                | (DocumentChunk.embedding_model != model)
            )
        )
        if kb_id is not None:
            stmt = stmt.where(DocumentChunk.kb_id == kb_id)
        return int((await db.execute(stmt)).scalar_one())


async def re_embed_all_chunks(*, kb_id: UUID | None = None) -> dict[str, object]:
    """BackgroundTask / CLI：对 stale chunks 批量重嵌，直到无剩余或批次失败。"""
    if _re_embed_lock.locked():
        return {"status": "skipped", "reason": "already_running"}

    async with _re_embed_lock:
        model = current_embedding_model()
        total_updated = 0
        batch_errors = 0

        while True:
            async with SessionLocal() as db:
                stmt = (
                    select(DocumentChunk)
                    .where(DocumentChunk.chunk_kind != "parent")
                    .where(
                        (DocumentChunk.embedding_model.is_(None))
                        | (DocumentChunk.embedding_model != model)
                    )
                    .order_by(DocumentChunk.created_at)
                    .limit(RE_EMBED_BATCH_SIZE)
                )
                if kb_id is not None:
                    stmt = stmt.where(DocumentChunk.kb_id == kb_id)

                chunks = list((await db.scalars(stmt)).all())
                if not chunks:
                    break

                texts = [
                    embedding_input_text(c.heading_path, c.content) for c in chunks
                ]
                try:
                    vectors = await embed_texts(texts)
                except Exception:
                    logger.exception("re-embed batch failed at offset %s", total_updated)
                    batch_errors += len(chunks)
                    break

                for chunk, vector in zip(chunks, vectors, strict=True):
                    chunk.embedding = vector
                    chunk.embedding_model = model

                await db.commit()
                total_updated += len(chunks)
                logger.info("re-embed progress: %s chunks updated", total_updated)

        status = "completed" if batch_errors == 0 else "partial"
        return {
            "status": status,
            "embedding_model": model,
            "updated": total_updated,
            "errors": batch_errors,
        }
