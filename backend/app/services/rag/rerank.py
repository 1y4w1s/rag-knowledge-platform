"""Rerank Top-N（Plan-RAG R3-2）：RRF 候选精排后取 Top-K。"""

from __future__ import annotations

import logging
import re

import httpx

from app.core.config import settings
from app.services.ingestion.embedder import embedding_input_text
from app.services.rag.types import RetrievedChunk

logger = logging.getLogger(__name__)

TONGYI_RERANK_URL = (
    "https://dashscope.aliyuncs.com/compatible-api/v1/reranks"
)
DEFAULT_RERANK_MODEL = "qwen3-rerank"
RERANK_INSTRUCT = (
    "Given a web search query, retrieve relevant passages that answer the query."
)

_CJK_RUN = re.compile(r"[\u4e00-\u9fff]+")
_LATIN_TERM = re.compile(r"[A-Za-z0-9_]{4,}")


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
        "model": settings.rerank_model or DEFAULT_RERANK_MODEL,
        "query": query,
        "documents": documents,
        "top_n": min(top_n, len(documents)),
        "instruct": RERANK_INSTRUCT,
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(TONGYI_RERANK_URL, headers=headers, json=payload)
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


async def rerank_chunks(
    query: str,
    chunks: list[RetrievedChunk],
    *,
    top_k: int,
) -> list[RetrievedChunk]:
    """对 RRF 候选重排；失败或单条时保持原顺序。"""
    if not settings.rerank_enabled or len(chunks) <= 1:
        return chunks[:top_k]

    documents = [chunk_rerank_text(c) for c in chunks]
    provider = settings.rerank_provider.lower()

    try:
        if provider == "mock" or (provider == "tongyi" and not settings.tongyi_api_key):
            ordered_indices = _mock_rerank_indices(query, documents)
        elif provider == "tongyi":
            api_indices = await _rerank_tongyi(query, documents, top_n=top_k)
            ordered_indices = api_indices if api_indices else list(range(len(chunks)))
        else:
            raise ValueError(f"不支持的 rerank 提供商: {settings.rerank_provider}")
    except Exception:
        logger.exception("rerank 失败，回落 RRF 顺序")
        return chunks[:top_k]

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
