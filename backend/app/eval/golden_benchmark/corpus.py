"""Retrieval corpus fingerprinting for PRE/POST entity-extraction skip equivalence."""

from __future__ import annotations

import hashlib
import json
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.models.document_chunk import DocumentChunk


async def collect_corpus_fingerprint(db: AsyncSession, kb_id: UUID) -> dict[str, Any]:
    """Fingerprint searchable chunk corpus for a KB (retrieval-relevant fields only)."""
    chunk_rows = await db.execute(
        select(DocumentChunk)
        .where(DocumentChunk.kb_id == kb_id)
        .order_by(DocumentChunk.document_id, DocumentChunk.chunk_index)
    )
    chunks = chunk_rows.scalars().all()

    doc_rows = await db.execute(
        select(Document.id, Document.filename)
        .where(Document.kb_id == kb_id)
        .order_by(Document.id)
    )
    documents = doc_rows.all()

    chunk_records: list[dict[str, Any]] = []
    for chunk in chunks:
        chunk_records.append(
            {
                "chunk_index": chunk.chunk_index,
                "content_hash": hashlib.sha256(chunk.content.encode("utf-8")).hexdigest(),
                "chunk_kind": chunk.chunk_kind,
                "page_number": chunk.page_number,
                "section_title": chunk.section_title,
                "heading_path": chunk.heading_path,
                "has_embedding": chunk.embedding is not None,
                "has_embedding_en": chunk.embedding_en is not None,
                "embedding_model": chunk.embedding_model,
            }
        )

    corpus_hash = hashlib.sha256(
        json.dumps(chunk_records, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()

    return {
        "kb_id": str(kb_id),
        "chunk_count": len(chunks),
        "embedding_row_count": sum(1 for c in chunks if c.embedding is not None),
        "embedding_en_row_count": sum(1 for c in chunks if c.embedding_en is not None),
        "searchable_document_ids": [str(doc_id) for doc_id, _ in documents],
        "document_filenames": [filename for _, filename in documents],
        "chunk_content_hashes": [r["content_hash"] for r in chunk_records],
        "corpus_fingerprint_sha256": corpus_hash,
    }


def corpora_equivalent(pre: dict[str, Any], post: dict[str, Any]) -> bool:
    keys = (
        "chunk_count",
        "embedding_row_count",
        "embedding_en_row_count",
        "chunk_content_hashes",
        "corpus_fingerprint_sha256",
    )
    return all(pre.get(k) == post.get(k) for k in keys)
