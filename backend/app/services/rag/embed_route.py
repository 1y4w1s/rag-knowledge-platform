"""B4：英轨嵌入路由 — 语言检测 + 失败改列回退 + 空英列回主列。

契约：
- 英问优先 bge_en + embedding_en
- bge_en 失败 → 主嵌 + embedding_col=None（禁止 384 向量打 512 列）
- try_embed 返回 None → query_vec=None，禁止 None[0]
- 英列召回 0 条 → 同请求内主嵌 + 主列补召回，并打点
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Awaitable, Callable, Sequence

from app.core.latency import get_tracker
from app.services.ingestion.embedder import try_embed_texts

logger = logging.getLogger(__name__)

EMBEDDING_EN_COL = "embedding_en"
EMBED_EN_FALLBACK_PRIMARY = "embedding_en_fallback_primary"
REASON_EMBEDDING_EN_FAILED = "embedding_en_failed"


@dataclass(frozen=True)
class QueryEmbedRoute:
    """一次 query 的嵌入路由结果。"""

    provider: str | None
    embedding_col: str | None
    query_vec: list[float] | None
    fallback_from_en: bool = False


def is_mostly_english(text: str) -> bool:
    """字母 ASCII 占比 > 0.5 → 偏英（与入库/检索历史口径一致）。"""
    ascii_chars = sum(1 for c in text if c.isascii() and c.isalpha())
    total_chars = sum(1 for c in text if c.isalpha())
    return total_chars > 0 and (ascii_chars / total_chars) > 0.5


def detect_query_lang(query: str) -> tuple[str | None, str | None]:
    """返回 (provider, embedding_col)；非英则为 (None, None)。"""
    if is_mostly_english(query):
        return "bge_en", EMBEDDING_EN_COL
    return None, None


async def resolve_query_embed(
    query: str,
    *,
    allow_embed: bool = True,
) -> QueryEmbedRoute:
    """统一英轨回退：en 失败改主列；None 不崩。"""
    provider, col = detect_query_lang(query)
    if not allow_embed:
        return QueryEmbedRoute(provider=provider, embedding_col=col, query_vec=None)

    if provider == "bge_en":
        vecs = await try_embed_texts([query], provider="bge_en")
        if vecs is not None and vecs:
            return QueryEmbedRoute(
                provider="bge_en",
                embedding_col=EMBEDDING_EN_COL,
                query_vec=vecs[0],
            )
        primary = await try_embed_texts([query])
        if primary is not None and primary:
            logger.info(
                "reason=embedding_en_provider_fallback_primary query_len=%d",
                len(query or ""),
            )
            return QueryEmbedRoute(
                provider=None,
                embedding_col=None,
                query_vec=primary[0],
                fallback_from_en=True,
            )
        return QueryEmbedRoute(
            provider="bge_en",
            embedding_col=None,
            query_vec=None,
            fallback_from_en=True,
        )

    vecs = await try_embed_texts([query])
    if vecs is not None and vecs:
        return QueryEmbedRoute(provider=None, embedding_col=None, query_vec=vecs[0])
    return QueryEmbedRoute(provider=None, embedding_col=None, query_vec=None)


async def vector_recall_en_empty_fallback(
    *,
    query: str,
    query_vec: list[float],
    embedding_col: str | None,
    recall: Callable[..., Awaitable[Sequence]],
) -> list:
    """英列召回空 → 主嵌 + 主列一次补召回。

    ``recall`` 须接受 ``query_vec=`` 与 ``embedding_col=`` 关键字参数。
    """
    rows = list(await recall(query_vec=query_vec, embedding_col=embedding_col))
    if embedding_col != EMBEDDING_EN_COL or rows:
        return rows

    primary = await try_embed_texts([query])
    if primary is None or not primary:
        logger.info(
            "reason=%s status=primary_embed_unavailable query_len=%d",
            EMBED_EN_FALLBACK_PRIMARY,
            len(query or ""),
        )
        return rows

    logger.info(
        "reason=%s status=retry_primary_column query_len=%d",
        EMBED_EN_FALLBACK_PRIMARY,
        len(query or ""),
    )
    get_tracker("retrieval.embedding_en_fallback").record(1)
    return list(await recall(query_vec=primary[0], embedding_col=None))
