"""嵌入提供方 readiness 轻探测（NW-8）。

结果仅供 /health/detailed 展示；不参与整体 status（对称 OCR）。
"""

from __future__ import annotations

import asyncio
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)

# 短于业务 embed_timeout，避免 detailed 被冷启动拖死
EMBED_HEALTH_TIMEOUT_SECONDS = 3.0


async def probe_embed_readiness() -> dict:
    """返回 ``{provider, ready, reason}``；reason ∈ ok|key_missing|timeout|error。"""
    provider = (settings.embedding_provider or "bge").lower()

    if provider == "tongyi" and not settings.tongyi_api_key:
        return {"provider": provider, "ready": False, "reason": "key_missing"}

    if provider == "mock":
        return {"provider": provider, "ready": True, "reason": "ok"}

    try:
        from app.services.ingestion.embedder import try_embed_texts

        vecs = await asyncio.wait_for(
            try_embed_texts(["ping"]),
            timeout=EMBED_HEALTH_TIMEOUT_SECONDS,
        )
    except TimeoutError:
        return {"provider": provider, "ready": False, "reason": "timeout"}
    except Exception:
        logger.debug("embed health probe failed provider=%s", provider, exc_info=True)
        return {"provider": provider, "ready": False, "reason": "error"}

    if not vecs:
        return {"provider": provider, "ready": False, "reason": "error"}
    return {"provider": provider, "ready": True, "reason": "ok"}
