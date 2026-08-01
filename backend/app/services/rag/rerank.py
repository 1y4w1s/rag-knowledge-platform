"""Rerank Top-N（Plan-RAG R3-2 / A2）：RRF 候选精排后取 Top-K。

真路径默认 BGE（fastembed ONNX TextCrossEncoder）；失败回落 RRF 顺序。
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

from app.core.config import settings
from app.core.http_client import get_tongyi_client
from app.core.retry import async_retry
from app.services.ingestion.embedder import embedding_input_text
from app.services.rag.types import RetrievedChunk

logger = logging.getLogger(__name__)

TONGYI_RERANK_URL = (
    "https://dashscope.aliyuncs.com/compatible-api/v1/reranks"
)
DEFAULT_TONGYI_RERANK_MODEL = "qwen3-rerank"
DEFAULT_BGE_RERANK_MODEL = "BAAI/bge-reranker-base"
RERANK_INSTRUCT = (
    "Given a web search query, retrieve relevant passages that answer the query."
)

_CJK_RUN = re.compile(r"[\u4e00-\u9fff]+")
_LATIN_TERM = re.compile(r"[A-Za-z0-9_]{4,}")

_bge_encoder: Any | None = None


def _significant_terms(query: str) -> list[str]:
    terms = _LATIN_TERM.findall(query)
    for run in _CJK_RUN.findall(query):
        if len(run) == 1:
            terms.append(run)
            continue
        for size in (2, 3):
            if len(run) < size:
                continue
            for i in range(len(run) - size + 1):
                terms.append(run[i : i + size])
    return terms


def chunk_rerank_text(chunk: RetrievedChunk) -> str:
    """与嵌入/生成对齐：标题路径 + 正文（parent 优先）。"""
    body = chunk.parent_content or chunk.content
    return embedding_input_text(chunk.heading_path, body)


def _mock_rerank_indices(query: str, documents: list[str]) -> list[int]:
    terms = _significant_terms(query)
    if not terms:
        return list(range(len(documents)))

    scored: list[tuple[int, float]] = []
    for idx, doc in enumerate(documents):
        hits = sum(1 for term in terms if term in doc)
        scored.append((idx, hits / len(terms)))

    scored.sort(key=lambda item: (-item[1], item[0]))
    return [idx for idx, _score in scored]


def _get_bge_encoder() -> Any:
    """懒加载 TextCrossEncoder（进程内单例）。"""
    global _bge_encoder
    if _bge_encoder is not None:
        return _bge_encoder

    from fastembed.rerank.cross_encoder import TextCrossEncoder

    model_name = settings.rerank_model or DEFAULT_BGE_RERANK_MODEL
    kwargs: dict[str, Any] = {
        "model_name": model_name,
        "providers": ["CPUExecutionProvider"],
        "lazy_load": True,
    }
    cache_dir = (settings.bge_rerank_cache_dir or "").strip()
    if cache_dir:
        kwargs["cache_dir"] = cache_dir

    _bge_encoder = TextCrossEncoder(**kwargs)
    return _bge_encoder


def _bge_score_sync(query: str, documents: list[str]) -> list[float]:
    encoder = _get_bge_encoder()
    scores = list(encoder.rerank(query, documents))
    if len(scores) != len(documents):
        raise RuntimeError(
            f"BGE rerank 分数数量异常: got={len(scores)} expected={len(documents)}"
        )
    return [float(s) for s in scores]


async def _rerank_bge(
    query: str,
    documents: list[str],
    *,
    top_n: int,
) -> list[int] | None:
    """BGE cross-encoder 精排；返回按相关性降序的文档下标。"""
    if not documents:
        return []

    scores = await asyncio.to_thread(_bge_score_sync, query, documents)
    ranked = sorted(range(len(documents)), key=lambda i: (-scores[i], i))
    return ranked[: min(top_n, len(ranked))]


async def _rerank_tongyi(
    query: str,
    documents: list[str],
    *,
    top_n: int,
) -> list[int] | None:
    if not settings.tongyi_api_key:
        raise RuntimeError("未配置 TONGYI_API_KEY，无法调用通义 rerank")

    headers = {
        "Authorization": f"Bearer {settings.tongyi_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": settings.rerank_model or DEFAULT_TONGYI_RERANK_MODEL,
        "query": query,
        "documents": documents,
        "top_n": min(top_n, len(documents)),
        "instruct": RERANK_INSTRUCT,
    }

    client = get_tongyi_client()
    resp = await asyncio.wait_for(
        client.post(TONGYI_RERANK_URL, headers=headers, json=payload),
        timeout=settings.rerank_timeout_seconds,
    )
    resp.raise_for_status()
    data = resp.json()

    results = data.get("results")
    if not isinstance(results, list):
        raise RuntimeError(f"通义 rerank 响应异常: {data}")

    ordered: list[int] = []
    for item in results:
        if not isinstance(item, dict) or "index" not in item:
            continue
        ordered.append(int(item["index"]))
    return ordered or None


def _apply_order(
    chunks: list[RetrievedChunk],
    ordered_indices: list[int],
    *,
    top_k: int,
) -> list[RetrievedChunk]:
    seen: set[int] = set()
    reranked: list[RetrievedChunk] = []
    for idx in ordered_indices:
        if idx < 0 or idx >= len(chunks) or idx in seen:
            continue
        seen.add(idx)
        reranked.append(chunks[idx])
        if len(reranked) >= top_k:
            break

    for idx, chunk in enumerate(chunks):
        if idx not in seen:
            reranked.append(chunk)
        if len(reranked) >= top_k:
            break

    return reranked[:top_k]


async def rerank_chunks(
    query: str,
    chunks: list[RetrievedChunk],
    *,
    top_k: int,
) -> list[RetrievedChunk]:
    """对 RRF 候选重排；失败或单条时保持原顺序。

    是否调用由 retrieval 闸门决定；此处仅当有效策略为 off 时早退
    （兼容旧调用方：RERANK_ENABLED 桥接见 effective_rerank_policy）。
    """
    from app.services.rag.planner import effective_rerank_policy

    if effective_rerank_policy() == "off" or len(chunks) <= 1:
        return chunks[:top_k]

    documents = [chunk_rerank_text(c) for c in chunks]
    provider = settings.rerank_provider.lower()

    try:
        if provider == "mock":
            ordered_indices = _mock_rerank_indices(query, documents)
        elif provider == "bge":
            api_indices = await async_retry(
                _rerank_bge,
                query,
                documents,
                top_n=len(documents),
                max_retries=settings.retry_max_attempts,
                base_delay=settings.retry_base_delay,
                breaker_name="bge_rerank",
            )
            ordered_indices = api_indices if api_indices else list(range(len(chunks)))
        elif provider == "tongyi":
            if not settings.tongyi_api_key:
                ordered_indices = _mock_rerank_indices(query, documents)
            else:
                api_indices = await async_retry(
                    _rerank_tongyi,
                    query,
                    documents,
                    top_n=top_k,
                    max_retries=settings.retry_max_attempts,
                    base_delay=settings.retry_base_delay,
                    breaker_name="tongyi_rerank",
                )
                ordered_indices = (
                    api_indices if api_indices else list(range(len(chunks)))
                )
        else:
            raise ValueError(f"不支持的 rerank 提供商: {settings.rerank_provider}")
    except Exception:
        logger.exception("rerank 失败，回落 RRF 顺序")
        return chunks[:top_k]

    return _apply_order(chunks, ordered_indices, top_k=top_k)
