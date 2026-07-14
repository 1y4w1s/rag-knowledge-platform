"""Top-K 多库多样性（G-1 H7）：rerank 后保证各库均有代表。"""

from __future__ import annotations

from uuid import UUID

from app.services.rag.relevance import query_overlaps_chunk
from app.services.rag.types import RetrievedChunk


def apply_kb_diversity(
    chunks: list[RetrievedChunk],
    query: str,
    *,
    top_k: int = 5,
) -> list[RetrievedChunk]:
    """若 ≥2 库均有 gate 通过片段，Top-K 每库至少保留 1 条再按原序填满。"""
    if len(chunks) <= 1:
        return chunks[:top_k]

    gate_kb_ids: set[UUID] = set()
    for chunk in chunks:
        if query_overlaps_chunk(query, chunk):
            gate_kb_ids.add(chunk.kb_id)

    if len(gate_kb_ids) < 2:
        return chunks[:top_k]

    selected: list[RetrievedChunk] = []
    selected_ids: set[UUID] = set()
    covered_kbs: set[UUID] = set()

    for chunk in chunks:
        if chunk.kb_id not in gate_kb_ids or chunk.kb_id in covered_kbs:
            continue
        if not query_overlaps_chunk(query, chunk):
            continue
        selected.append(chunk)
        selected_ids.add(chunk.chunk_id)
        covered_kbs.add(chunk.kb_id)
        if len(selected) >= top_k:
            return selected

    for chunk in chunks:
        if chunk.chunk_id in selected_ids:
            continue
        selected.append(chunk)
        selected_ids.add(chunk.chunk_id)
        if len(selected) >= top_k:
            break

    return selected[:top_k]
