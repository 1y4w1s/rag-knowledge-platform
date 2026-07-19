"""共享 HTTP 客户端（连接池复用 + 资源防控）。

每个外部服务一个共享 AsyncClient，避免每次请求新建 TCP 连接。
连接池大小由 `settings.http_max_connections` 控制。
"""

from __future__ import annotations

import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# ── 共享客户端（惰性初始化） ──────────────────────────────────────────

_deepseek_client: httpx.AsyncClient | None = None
_tongyi_client: httpx.AsyncClient | None = None


def _make_client(timeout: float) -> httpx.AsyncClient:
    limits = httpx.Limits(
        max_connections=settings.http_max_connections,
        max_keepalive_connections=settings.http_max_connections,
        keepalive_expiry=30.0,
    )
    return httpx.AsyncClient(timeout=timeout, limits=limits)


def get_deepseek_client() -> httpx.AsyncClient:
    global _deepseek_client
    if _deepseek_client is None:
        _deepseek_client = _make_client(settings.llm_timeout_seconds + 5.0)
        logger.info("初始化 DeepSeek HTTP 客户端（连接池=%d）", settings.http_max_connections)
    return _deepseek_client


def get_tongyi_client() -> httpx.AsyncClient:
    global _tongyi_client
    if _tongyi_client is None:
        max_timeout = max(
            settings.embed_timeout_seconds,
            settings.rerank_timeout_seconds,
        ) + 5.0
        _tongyi_client = _make_client(max_timeout)
        logger.info("初始化通义 HTTP 客户端（连接池=%d）", settings.http_max_connections)
    return _tongyi_client


async def close_all_clients() -> None:
    """应用关闭时释放所有连接。"""
    global _deepseek_client, _tongyi_client
    if _deepseek_client is not None:
        await _deepseek_client.aclose()
        _deepseek_client = None
    if _tongyi_client is not None:
        await _tongyi_client.aclose()
        _tongyi_client = None
    logger.info("HTTP 客户端已关闭")
