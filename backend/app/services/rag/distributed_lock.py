"""B3 · 统一锁抽象：Redis SETNX + TTL（多 worker）/ 进程内注册表（单 worker 回退）。

设计（masterplan 主题 B 步骤 5 · T4 H6/H8/P1-07/P1-09）：
- ``LOCK_BACKEND=memory``（默认）：**显式单 worker** 语义——进程内注册表，
  带 TTL 持有上限（30min 兜底自动过期，H6/L28）与 token 账本；
- ``LOCK_BACKEND=redis``：Redis ``SET NX EX``（原子获取 + TTL 自动过期），
  release 用 token 比较删除（Lua 语义，防误释放他人锁）——多 worker 部署必须启用；
- 进程内 token 账本：SSE 流在同一进程内 acquire/release，release 无需跨进程传 token。

单 worker 部署期间以 memory 为默认即 masterplan 允许的
「显式单 worker + 文档注明」退化；多 worker 必须 ``LOCK_BACKEND=redis``。
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)

LOCK_TTL_SECONDS_DEFAULT = 30 * 60

# key -> (expires_at_monotonic, token)；token 账本供 release 校验（redis 比较删除 / 内存语义一致）
_registry: dict[str, tuple[float, str]] = {}
_registry_lock = asyncio.Lock()


def _use_redis_backend() -> bool:
    return settings.lock_backend == "redis"


async def _acquire_memory(key: str, ttl_seconds: int, token: str) -> bool:
    async with _registry_lock:
        now = time.monotonic()
        entry = _registry.get(key)
        if entry is not None and entry[0] > now:
            return False
        _registry[key] = (now + ttl_seconds, token)
        return True


async def _release_memory(key: str, token: str | None) -> None:
    async with _registry_lock:
        entry = _registry.get(key)
        if entry is None:
            return
        if token is not None and entry[1] != token:
            # 非持有者尝试释放：忽略（防误释放）
            return
        _registry.pop(key, None)


async def _acquire_redis(key: str, ttl_seconds: int, token: str) -> bool:
    from app.core.redis import get_redis

    redis = await get_redis()
    ok = await redis.set(key, token, nx=True, ex=ttl_seconds)
    return bool(ok)


async def _release_redis(key: str, token: str | None) -> None:
    """token 比较删除：仅当当前值 == 持有 token 才 DEL（防误释放他人锁）。"""
    from app.core.redis import get_redis

    redis = await get_redis()
    if token is None:
        await redis.delete(key)
        return
    # 比较删除（Lua 保证原子；redis-py 2.x 无内置 compare-and-delete）
    script = """
    if redis.call('get', KEYS[1]) == ARGV[1] then
        return redis.call('del', KEYS[1])
    else
        return 0
    end
    """
    await redis.eval(script, 1, key, token)


async def acquire_lock(
    key: str,
    *,
    ttl_seconds: int = LOCK_TTL_SECONDS_DEFAULT,
    token: str | None = None,
) -> bool:
    """非阻塞获取锁。返回 False 表示已被持有（TTL 未过期）。"""
    token = token or uuid.uuid4().hex
    if _use_redis_backend():
        try:
            return await _acquire_redis(key, ttl_seconds, token)
        except Exception:
            logger.exception("Redis 锁获取失败，按未持有处理: key=%s", key)
            return False
    return await _acquire_memory(key, ttl_seconds, token)


async def release_lock(key: str, token: str | None = None) -> None:
    """释放锁（幂等；redis 后端按 token 比较删除）。"""
    if _use_redis_backend():
        try:
            await _release_redis(key, token)
        except Exception:
            logger.exception("Redis 锁释放失败（TTL 兜底自动过期）: key=%s", key)
        return
    await _release_memory(key, token)


def _lock_owner_token(key: str) -> str | None:
    """测试/扩展用：当前进程内该 key 的持有 token（无锁返回 None）。"""
    entry = _registry.get(key)
    return entry[1] if entry is not None else None


def reset_lock_registry() -> None:
    """测试隔离：清空进程内锁注册表。"""
    _registry.clear()


__all__ = [
    "LOCK_TTL_SECONDS_DEFAULT",
    "acquire_lock",
    "release_lock",
    "reset_lock_registry",
]
