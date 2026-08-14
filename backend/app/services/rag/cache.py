"""检索查询缓存（双后端：memory / redis）。

2026-07-18 重构：全 async-native（移除 asyncio.run anti-pattern）。

用法：
    CACHE_BACKEND=memory   # 默认，进程内 LRU
    CACHE_BACKEND=redis    # Redis，多副本共享

    await set_query_cache(kb_id, user_message, chunks)
    chunks = await get_query_cache(kb_id, user_message)
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from collections import OrderedDict
from typing import Any
from uuid import UUID

from app.core.config import settings
from app.services.rag.types import RetrievedChunk

logger = logging.getLogger(__name__)

# ── 后端选择 ──

_CACHE_BACKEND: str | None = None


def _get_backend() -> str:
    global _CACHE_BACKEND
    if _CACHE_BACKEND is None:
        # C1 收口：原 CACHE_BACKEND env → settings.cache_backend
        _CACHE_BACKEND = settings.cache_backend
    return _CACHE_BACKEND


# ── Memory 后端 ──

_cache: OrderedDict[str, tuple[float, list]] = OrderedDict()
_MAX_SIZE: int = 5000
_TTL_SECONDS: int = 300


def _effective_ttl() -> int:
    """从配置读取 TTL（同时允许 env 覆盖 for 单测）。"""
    from app.core.config import settings
    return settings.query_cache_ttl_seconds


def _effective_max_size() -> int:
    from app.core.config import settings
    return settings.query_cache_max_size


def _chunk_to_redis_dict(chunk: Any) -> dict[str, Any]:
    """RetrievedChunk -> JSON 可序列化 dict（P0-2：Redis 后端真正可写）。"""
    if not isinstance(chunk, RetrievedChunk):
        raise TypeError(f"query cache chunks must be RetrievedChunk, got {type(chunk)!r}")
    return chunk.to_dict()


def _cache_key(kb_id: UUID, query: str, hide_admin_only: bool = False) -> str:
    # 带上 rewrite / clause-route / rerank 策略，避免开/关后命中错误缓存
    from app.services.rag.planner import (
        effective_query_rewrite_policy,
        effective_rerank_policy,
    )

    rw_pol = effective_query_rewrite_policy()
    rw = {"off": "off", "always": "always", "conditional": "cond"}.get(rw_pol, rw_pol)
    cr = "1" if settings.clause_route_enabled else "0"
    pol = effective_rerank_policy()
    rr = {"off": "off", "always": "always", "conditional": "cond"}.get(pol, pol)
    gr = "1" if settings.graph_recall_enabled else "0"
    raw = (
        f"{kb_id}|{query.strip().lower()}|rw={rw}|cr={cr}|rr={rr}"
        f"|ho={1 if hide_admin_only else 0}|gr={gr}"
    )
    # 键带可搜索前缀 q:{kb_id}:，供 clear_query_cache(kb_id) 精确前缀失效（P1-12）
    return f"q:{kb_id}:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


async def get_query_cache(
    kb_id: UUID, query: str, hide_admin_only: bool = False
) -> list | None:
    """返回缓存的检索结果，过期或未命中返回 None。"""
    key = _cache_key(kb_id, query, hide_admin_only=hide_admin_only)

    if _get_backend() == "redis":
        try:
            from app.core.redis import get_redis
            r = await get_redis()
            data = await r.get(key)
            if data:
                cached_at, raw_chunks = json.loads(data)
                if time.monotonic() - cached_at < _effective_ttl():
                    chunks = [RetrievedChunk.from_dict(c) for c in raw_chunks]
                    _inc_cache_hit("query_chunks")
                    return chunks
        except Exception as e:
            logger.warning("Redis 读取失败，回退 memory: %s", e)

    entry = _cache.get(key)
    if entry is None:
        _inc_cache_miss("query_chunks")
        return None
    ts, chunks = entry
    if time.monotonic() - ts > _effective_ttl():
        del _cache[key]
        _inc_cache_miss("query_chunks")
        return None
    _inc_cache_hit("query_chunks")
    return chunks


async def set_query_cache(
    kb_id: UUID, query: str, chunks: list, hide_admin_only: bool = False
) -> None:
    """写入查询缓存。"""
    key = _cache_key(kb_id, query, hide_admin_only=hide_admin_only)

    if _get_backend() == "redis":
        try:
            from app.core.redis import get_redis
            r = await get_redis()
            data = json.dumps([time.monotonic(), [_chunk_to_redis_dict(c) for c in chunks]])
            await r.setex(key, _effective_ttl(), data)
            return
        except Exception as e:
            logger.warning("Redis 写入失败，回退 memory: %s", e)

    _cache[key] = (time.monotonic(), chunks)
    if len(_cache) > _effective_max_size():
        _cache.popitem(last=False)


async def clear_query_cache(kb_id: UUID | None = None) -> int:
    """清空缓存（可选按 kb_id 维度）。返回清除条目数。"""
    cleared = 0

    if _get_backend() == "redis":
        try:
            from app.core.redis import get_redis
            r = await get_redis()
            if kb_id:
                pattern = f"q:{kb_id}:*"
            else:
                pattern = "q:*"
            keys = [key async for key in r.scan_iter(match=pattern, count=500)]
            if keys:
                await r.delete(*keys)
                cleared = len(keys)
            logger.info("Redis 缓存清空: %d 条", cleared)
            return cleared
        except Exception as e:
            logger.warning("Redis 清空失败: %s", e)

    if kb_id:
        prefix = f"q:{kb_id}:"
        keys = [k for k in _cache if k.startswith(prefix)]
        for k in keys:
            del _cache[k]
        cleared = len(keys)
    else:
        cleared = len(_cache)
        _cache.clear()
    logger.info("Memory 缓存清空: %d 条", cleared)
    return cleared


async def invalidate_kb_caches(kb_id: UUID) -> tuple[int, int]:
    """文档/可见性变更后失效该 KB 的查询 chunk 缓存与 LLM 响应缓存（P1-12 接线点）。

    返回 (query_cleared, llm_cleared) 条数。两条缓存都依赖 kb 内容与可见性，
    文档增删/恢复/可见性变更后必须同时失效，否则 TTL 窗口内会命中旧 chunk / 旧回答。
    """
    query_cleared = await clear_query_cache(kb_id=kb_id)
    llm_cleared = await llm_response_cache.clear(kb_id=str(kb_id))
    logger.info(
        "invalidate_kb_caches kb_id=%s query=%d llm=%d",
        kb_id, query_cleared, llm_cleared,
    )
    return query_cleared, llm_cleared


# ── 开关 ──

_QUERY_CACHE_ENABLED: bool = True


def query_cache_enabled() -> bool:
    return _QUERY_CACHE_ENABLED


def set_query_cache_enabled(enabled: bool) -> None:
    global _QUERY_CACHE_ENABLED
    _QUERY_CACHE_ENABLED = enabled
    if not enabled:
        import asyncio
        asyncio.create_task(clear_query_cache())


# ── LLM 响应缓存 ──────────────────────────────────────────────────

_CACHE_HIT_TOTAL: dict[str, int] = {}


def _reset_cache_hit_counters() -> None:
    """仅测试用。"""
    _CACHE_HIT_TOTAL.clear()


def cache_hit_snapshot() -> dict[str, int]:
    """返回 {kind: count}，kind=query_chunks|llm_response。"""
    return dict(_CACHE_HIT_TOTAL)


def _inc_cache_hit(kind: str) -> None:
    _CACHE_HIT_TOTAL[kind] = _CACHE_HIT_TOTAL.get(kind, 0) + 1


def _inc_cache_miss(kind: str) -> None:
    _CACHE_HIT_TOTAL[f"{kind}_miss"] = _CACHE_HIT_TOTAL.get(f"{kind}_miss", 0) + 1


class AsyncLLMResponseCache:
    """LLM 响应缓存（精确匹配 messages 列表）。

    双后端：memory（默认，进程内 LRU）/ redis（多副本共享）。
    key = sha256(kb_id/workspace + messages_json)，自动含 chunk 内容差异。
    写入点在 LLM 成功返回后；拒答不缓存。
    """

    def __init__(self) -> None:
        self._memory: OrderedDict[str, tuple[float, dict]] = OrderedDict()

    def _backend(self) -> str:
        return _get_backend()

    def _cache_key(
        self,
        kb_id: str | None,
        workspace: str,
        messages: list[dict[str, str]],
        user_id: str | None = None,
    ) -> str:
        prefix = kb_id or f"ws:{workspace}"
        # P1-13：键必须含 user 维度，不同用户相同问题不共享 LLM 响应缓存
        raw = (
            f"{prefix}|u={user_id or '-'}|"
            f"{json.dumps(messages, ensure_ascii=False, sort_keys=True)}"
        )
        return f"llm:{prefix}:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()

    async def get(
        self,
        kb_id: str | None,
        workspace: str,
        messages: list[dict[str, str]],
        user_id: str | None = None,
    ) -> dict | None:
        """返回 {content, citations, confidence} 或 None。"""
        ttl = settings.llm_response_cache_ttl_seconds
        if ttl <= 0:
            return None
        key = self._cache_key(kb_id, workspace, messages, user_id=user_id)

        if self._backend() == "redis":
            try:
                from app.core.redis import get_redis
                r = await get_redis()
                data = await r.get(key)
                if data:
                    cached_at, payload = json.loads(data)
                    if time.monotonic() - cached_at < ttl:
                        _inc_cache_hit("llm_response")
                        return payload
            except Exception as e:
                logger.warning("Redis LLM 缓存读失败，回退 memory: %s", e)

        entry = self._memory.get(key)
        if entry is None:
            _inc_cache_miss("llm_response")
            return None
        ts, payload = entry
        if time.monotonic() - ts > ttl:
            del self._memory[key]
            _inc_cache_miss("llm_response")
            return None
        _inc_cache_hit("llm_response")
        return payload

    async def set(
        self,
        kb_id: str | None,
        workspace: str,
        messages: list[dict[str, str]],
        payload: dict,
        user_id: str | None = None,
    ) -> None:
        """写入 LLM 响应缓存。payload = {content, citations, confidence}。"""
        ttl = settings.llm_response_cache_ttl_seconds
        if ttl <= 0:
            return
        key = self._cache_key(kb_id, workspace, messages, user_id=user_id)

        if self._backend() == "redis":
            try:
                from app.core.redis import get_redis
                r = await get_redis()
                data = json.dumps([time.monotonic(), payload])
                await r.setex(key, ttl, data)
                return
            except Exception as e:
                logger.warning("Redis LLM 缓存写失败，回退 memory: %s", e)

        self._memory[key] = (time.monotonic(), payload)
        if len(self._memory) > _effective_max_size():
            self._memory.popitem(last=False)

    async def clear(self, kb_id: str | None = None) -> int:
        """清空 LLM 响应缓存（可选按 kb_id 前缀）。返回清除条目数。"""
        cleared = 0
        if self._backend() == "redis":
            try:
                from app.core.redis import get_redis
                r = await get_redis()
                prefix = f"llm:{kb_id}:" if kb_id else "llm:"
                keys = [key async for key in r.scan_iter(match=f"{prefix}*", count=500)]
                if keys:
                    await r.delete(*keys)
                    cleared = len(keys)
                return cleared
            except Exception as e:
                logger.warning("Redis LLM 缓存清空失败: %s", e)
                return 0

        if kb_id:
            prefix = f"llm:{kb_id}:"
            keys = [k for k in self._memory if k.startswith(prefix)]
            for k in keys:
                del self._memory[k]
            cleared = len(keys)
        else:
            cleared = len(self._memory)
            self._memory.clear()
        logger.info("LLM 响应缓存清空: %d 条", cleared)
        return cleared


# 全局单例
llm_response_cache = AsyncLLMResponseCache()
