"""检索后压缩：内容去重（Jaccard + jieba） + 过长截断（RAG R6-1）。"""

from __future__ import annotations

import dataclasses
from typing import Sequence

import jieba

from app.services.rag.types import RetrievedChunk

SIMILARITY_THRESHOLD = 0.7  # Jaccard 相似度阈值，超过视为重复
MAX_CHUNK_LENGTH = 1200     # 单 chunk parent_content 最大字符数


def _jaccard_similarity(a: str, b: str) -> float:
    """基于 jieba 词级 token 的 Jaccard 相似度（替代原逐字拆分）。"""
    set_a = set(jieba.lcut(a.lower()))
    set_b = set(jieba.lcut(b.lower()))
    if not set_a or not set_b:
        return 0.0
    return len(set_a & set_b) / len(set_a | set_b)


def _get_chunk_text(chunk: RetrievedChunk) -> str:
    return chunk.parent_content or chunk.content


def dedup_chunks(chunks: Sequence[RetrievedChunk]) -> list[RetrievedChunk]:
    """内容去重：保留第一个出现的相似 chunk。"""
    result: list[RetrievedChunk] = []
    for chunk in chunks:
        text = _get_chunk_text(chunk)
        is_dup = any(
            _jaccard_similarity(text, _get_chunk_text(existing))
            > SIMILARITY_THRESHOLD
            for existing in result
        )
        if not is_dup:
            result.append(chunk)
    return result


def truncate_chunks(chunks: Sequence[RetrievedChunk]) -> list[RetrievedChunk]:
    """过长截断：超过 MAX_CHUNK_LENGTH 的 parent_content 截断到 800 字。

    由于 RetrievedChunk 是 frozen dataclass，使用 dataclasses.replace 创建新实例。
    """
    result: list[RetrievedChunk] = []
    for chunk in chunks:
        text = chunk.parent_content or chunk.content
        if len(text) > MAX_CHUNK_LENGTH:
            truncated = text[:MAX_CHUNK_LENGTH] + "\n…(略)"
            if chunk.parent_content:
                result.append(
                    dataclasses.replace(chunk, parent_content=truncated)
                )
            else:
                result.append(dataclasses.replace(chunk, content=truncated))
        else:
            result.append(chunk)
    return result


def dedup_and_compress(
    chunks: Sequence[RetrievedChunk],
) -> list[RetrievedChunk]:
    """去重 → 截断。"""
    return truncate_chunks(dedup_chunks(chunks))
