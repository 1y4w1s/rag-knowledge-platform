"""共享 Redis 滑动窗口（G2 · 限流键前缀 rl:）。

算法：Lua 原子 ZREMRANGEBYSCORE → ZCARD → 未超限才 ZADD。
score / 比较一律用墙钟 time.time()（禁 monotonic）。
"""

from __future__ import annotations

import logging
import os
import time
import uuid
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)

_BACKEND: str | None = None

# KEYS[1]=key  ARGV: now, window_start, max_req, ttl, member
# return 1=allowed (已写入), 0=denied (未写入)
_SLIDING_WINDOW_LUA = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window_start = tonumber(ARGV[2])
local max_req = tonumber(ARGV[3])
local ttl = tonumber(ARGV[4])
local member = ARGV[5]
redis.call('ZREMRANGEBYSCORE', key, '-inf', window_start)
local n = redis.call('ZCARD', key)
if n >= max_req then
  return 0
end
redis.call('ZADD', key, now, member)
redis.call('EXPIRE', key, ttl)
return 1
"""


def get_rate_limit_backend() -> str:
    """懒读限流后端（memory|redis），代码默认 redis。

    settings.rate_limit_backend（默认 redis）为唯一配置源；RATE_LIMIT_BACKEND env
    显式设置时覆盖（白名单：测试 monkeypatch env 覆盖，compose 部署也走 env）。
    """
    global _BACKEND
    if _BACKEND is None:
        _BACKEND = (
            os.environ.get("RATE_LIMIT_BACKEND")
            or settings.rate_limit_backend
        ).strip().lower() or "redis"
    return _BACKEND


def reset_rate_limit_backend_cache() -> None:
    """测试用：清后端缓存，便于 monkeypatch 环境变量后重读。"""
    global _BACKEND
    _BACKEND = None


def wall_now(now: float | None = None) -> float:
    return now if now is not None else time.time()


async def redis_sliding_allow(
    key: str,
    *,
    max_requests: int,
    window_seconds: int,
    now: float | None = None,
) -> bool:
    """未超限则记一次并返回 True；已达上限返回 False（不写入）。"""
    from app.core.redis import get_redis

    ts = wall_now(now)
    window_start = ts - window_seconds
    member = f"{ts}:{uuid.uuid4().hex}"
    r = await get_redis()
    allowed = await r.eval(
        _SLIDING_WINDOW_LUA,
        1,
        key,
        str(ts),
        str(window_start),
        str(max_requests),
        str(window_seconds),
        member,
    )
    return int(allowed) == 1


async def redis_sliding_record(
    key: str,
    *,
    window_seconds: int,
    now: float | None = None,
) -> None:
    """无条件记一次（登录失败计数用）。"""
    from app.core.redis import get_redis

    ts = wall_now(now)
    window_start = ts - window_seconds
    member = f"{ts}:{uuid.uuid4().hex}"
    r = await get_redis()
    pipe = r.pipeline(transaction=True)
    pipe.zremrangebyscore(key, "-inf", window_start)
    pipe.zadd(key, {member: ts})
    pipe.expire(key, window_seconds)
    await pipe.execute()


async def redis_zcard_in_window(
    key: str,
    *,
    window_seconds: int,
    now: float | None = None,
) -> int:
    """只读：清理过期后返回窗口内条数。"""
    from app.core.redis import get_redis

    ts = wall_now(now)
    window_start = ts - window_seconds
    r = await get_redis()
    pipe = r.pipeline(transaction=True)
    pipe.zremrangebyscore(key, "-inf", window_start)
    pipe.zcard(key)
    _, count = await pipe.execute()
    return int(count)


async def redis_delete_keys(*keys: str) -> None:
    if not keys:
        return
    from app.core.redis import get_redis

    r = await get_redis()
    await r.delete(*keys)


async def redis_get_json(key: str) -> dict[str, Any] | None:
    from app.core.redis import get_redis
    import json

    r = await get_redis()
    raw = await r.get(key)
    if not raw:
        return None
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


async def redis_set_json(key: str, value: dict[str, Any], *, ttl_seconds: int) -> None:
    from app.core.redis import get_redis
    import json

    r = await get_redis()
    await r.set(key, json.dumps(value), ex=max(1, ttl_seconds))
