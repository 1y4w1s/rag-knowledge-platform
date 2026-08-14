"""全库重嵌入：换 embedding 模型后批量更新已有 chunk 向量（Plan-RAG R2-4）。"""

from __future__ import annotations

import asyncio
import logging
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.dialects.postgresql import aggregate_order_by
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import SessionLocal
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.services.ingestion.embedder import (
    current_bge_en_model,
    current_embedding_model,
    embed_texts,
    embedding_input_text,
)

logger = logging.getLogger(__name__)

RE_EMBED_BATCH_SIZE = 25

_re_embed_lock = asyncio.Lock()


def _stale_clause(*, model: str, en_model: str):
    """主列或 EN 列任一为旧模型即视为 stale（parent 由调用方排除）。"""
    return or_(
        DocumentChunk.embedding_model.is_(None),
        DocumentChunk.embedding_model != model,
        and_(
            DocumentChunk.embedding_en.is_not(None),
            or_(
                DocumentChunk.embedding_en_model.is_(None),
                DocumentChunk.embedding_en_model != en_model,
            ),
        ),
    )


async def count_stale_chunks(*, kb_id: UUID | None = None) -> int:
    """需要重嵌的可检索 chunk 数量（parent 除外，含 EN 旧模型）。"""
    model = current_embedding_model()
    en_model = current_bge_en_model()
    async with SessionLocal() as db:
        stmt = (
            select(func.count())
            .select_from(DocumentChunk)
            .where(DocumentChunk.chunk_kind != "parent")
            .where(_stale_clause(model=model, en_model=en_model))
        )
        if kb_id is not None:
            stmt = stmt.where(DocumentChunk.kb_id == kb_id)
        return int((await db.execute(stmt)).scalar_one())


async def count_embedding_en_coverage(*, kb_id: UUID | None = None) -> dict[str, object]:
    """EN 列覆盖度：可检索 chunk 中 embedding_en 非空计数与占比（方案 B 成本评估）。"""
    async with SessionLocal() as db:
        stmt = (
            select(
                func.count(),
                func.count(DocumentChunk.embedding_en),
            )
            .select_from(DocumentChunk)
            .where(DocumentChunk.chunk_kind != "parent")
        )
        if kb_id is not None:
            stmt = stmt.where(DocumentChunk.kb_id == kb_id)
        total, en_non_null = (await db.execute(stmt)).one()

    ratio = round(en_non_null / total, 4) if total else 0.0
    return {
        "searchable_chunks": int(total),
        "embedding_en_chunks": int(en_non_null),
        "embedding_en_coverage": ratio,
    }


async def _english_document_ids(db: AsyncSession, *, kb_id: UUID) -> set[UUID]:
    """只读：kb 内重建全文后 is_mostly_english 判定的 active 文档 id（M0 同口径）。"""
    from app.services.rag.embed_route import is_mostly_english

    full_text = func.coalesce(
        func.string_agg(
            aggregate_order_by(DocumentChunk.content, DocumentChunk.chunk_index),
            " ",
        ),
        "",
    )
    stmt = (
        select(Document.id, full_text)
        .join(DocumentChunk, DocumentChunk.document_id == Document.id)
        .where(Document.kb_id == kb_id)
        .where(Document.deleted_at.is_(None))
        .where(DocumentChunk.chunk_kind != "parent")
        .group_by(Document.id)
    )
    rows = (await db.execute(stmt)).all()
    return {doc_id for doc_id, text in rows if is_mostly_english(text or "")}


async def count_en_gap_chunks(*, kb_id: UUID) -> int:
    """只读：kb 内偏英文档中可检索 chunk 且 EN 列为空的缺口数。"""
    async with SessionLocal() as db:
        doc_ids = await _english_document_ids(db, kb_id=kb_id)
        if not doc_ids:
            return 0
        stmt = (
            select(func.count())
            .select_from(DocumentChunk)
            .where(DocumentChunk.kb_id == kb_id)
            .where(DocumentChunk.chunk_kind != "parent")
            .where(DocumentChunk.embedding_en.is_(None))
            .where(DocumentChunk.document_id.in_(doc_ids))
        )
        return int((await db.execute(stmt)).scalar_one())


async def re_embed_en_gap_chunks(*, kb_id: UUID) -> dict[str, object]:
    """按 kb 补嵌偏英缺口：每批 25、独立 commit、单批异常 break 返回 partial。"""
    if _re_embed_lock.locked():
        return {"status": "skipped", "reason": "already_running"}

    async with _re_embed_lock:
        en_model = current_bge_en_model()
        total_updated = 0
        batch_errors = 0

        async with SessionLocal() as db:
            doc_ids = await _english_document_ids(db, kb_id=kb_id)
        if not doc_ids:
            return {
                "status": "completed",
                "en_model": en_model,
                "updated": 0,
                "errors": 0,
                "kb_id": str(kb_id),
            }

        while True:
            async with SessionLocal() as db:
                stmt = (
                    select(DocumentChunk)
                    .where(DocumentChunk.kb_id == kb_id)
                    .where(DocumentChunk.chunk_kind != "parent")
                    .where(DocumentChunk.embedding_en.is_(None))
                    .where(DocumentChunk.document_id.in_(doc_ids))
                    .order_by(DocumentChunk.created_at)
                    .limit(RE_EMBED_BATCH_SIZE)
                )
                chunks = list((await db.scalars(stmt)).all())
                if not chunks:
                    break

                texts = [
                    embedding_input_text(c.heading_path, c.content) for c in chunks
                ]
                try:
                    vectors = await embed_texts(texts, provider="bge_en")
                except Exception:
                    logger.exception(
                        "en-gap re-embed batch failed at offset %s", total_updated
                    )
                    batch_errors += len(chunks)
                    break

                for chunk, vector in zip(chunks, vectors):
                    chunk.embedding_en = vector
                    chunk.embedding_en_model = en_model

                await db.commit()
                total_updated += len(chunks)
                logger.info("en-gap re-embed progress: %s chunks updated", total_updated)

        status = "completed" if batch_errors == 0 else "partial"
        return {
            "status": status,
            "en_model": en_model,
            "updated": total_updated,
            "errors": batch_errors,
            "kb_id": str(kb_id),
        }


async def re_embed_all_chunks(*, kb_id: UUID | None = None) -> dict[str, object]:
    """BackgroundTask / CLI：对 stale chunks 批量重嵌，直到无剩余或批次失败。

    主列与 EN 列分别按各自当前模型判定，仅重建实际 stale 的列。
    """
    if _re_embed_lock.locked():
        return {"status": "skipped", "reason": "already_running"}

    async with _re_embed_lock:
        model = current_embedding_model()
        en_model = current_bge_en_model()
        total_updated = 0
        batch_errors = 0

        while True:
            async with SessionLocal() as db:
                stmt = (
                    select(DocumentChunk)
                    .where(DocumentChunk.chunk_kind != "parent")
                    .where(_stale_clause(model=model, en_model=en_model))
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
                main_indices = [
                    i
                    for i, chunk in enumerate(chunks)
                    if chunk.embedding_model is None or chunk.embedding_model != model
                ]
                en_indices = [
                    i
                    for i, chunk in enumerate(chunks)
                    if chunk.embedding_en is not None
                    and (
                        chunk.embedding_en_model is None
                        or chunk.embedding_en_model != en_model
                    )
                ]

                try:
                    main_vectors = (
                        await embed_texts([texts[i] for i in main_indices])
                        if main_indices
                        else []
                    )
                    en_vectors = (
                        await embed_texts(
                            [texts[i] for i in en_indices], provider="bge_en"
                        )
                        if en_indices
                        else []
                    )
                except Exception:
                    logger.exception("re-embed batch failed at offset %s", total_updated)
                    batch_errors += len(chunks)
                    break

                main_iter = iter(main_vectors)
                en_iter = iter(en_vectors)
                for i, chunk in enumerate(chunks):
                    if i in main_indices:
                        chunk.embedding = next(main_iter)
                        chunk.embedding_model = model
                    if i in en_indices:
                        chunk.embedding_en = next(en_iter)
                        chunk.embedding_en_model = en_model

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
