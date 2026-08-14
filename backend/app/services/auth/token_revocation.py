"""R1: 令牌吊销追踪（双后端：Redis 主用 / memory 回退，零迁移）。

维护 user_id → password_changed_at 映射。
通过比较 JWT 的 iat（签发时间）与 password_changed_at：
- iat < password_changed_at → 旧 token，拒绝
- iat >= password_changed_at → 有效

后端跟随 ``rate_limit_backend``（memory | redis，复用 RATE_LIMIT_BACKEND /
``redis_url`` 基建）：
- memory：仅进程内 dict（单实例默认，与旧实现行为一致）；
- redis：吊销时同步写 Redis（TTL 7 天）并更新本进程缓存；检查时先读缓存，
  未命中再从 Redis 读回并回填缓存；Redis 不可达时回退 memory 并进入冷却，
  避免每次请求都等待连接失败（fail-fast，与限流降级语义一致）。

P1-S3：吊销名单不再只存进程内存——重启 / 多副本共享 Redis 后旧 token 不复活。

P0-04：吊销时间必须用 epoch（``time.time``）而非 monotonic——JWT iat 是
unix 时间戳，monotonic 与 epoch 量纲不同会导致「吊销永不生效」。
"""

from __future__ import annotations

import logging
import time
import threading
from uuid import UUID

logger = logging.getLogger(__name__)

_revoked_before: dict[UUID, float] = {}
_lock = threading.Lock()
_TTL = 86400 * 7  # 7 天自动清理（与 Redis key TTL 一致）

# Redis 不可达后的回退冷却：冷却期内只走内存，避免每次请求重复等待连接失败。
_REDIS_FALLBACK_COOLDOWN_SECONDS = 30.0
_redis_fallback_until: float = 0.0

_KEY_PREFIX = "revoke:user:"


def _revocation_key(user_id: UUID) -> str:
    return f"{_KEY_PREFIX}{user_id}"


def _backend_is_redis() -> bool:
    from app.services.auth.rate_limit_store import get_rate_limit_backend

    return get_rate_limit_backend() == "redis"


def _mark_redis_fallback() -> None:
    global _redis_fallback_until
    _redis_fallback_until = time.time() + _REDIS_FALLBACK_COOLDOWN_SECONDS


def _redis_get_revoked(user_id: UUID) -> float | None:
    """从 Redis 读取吊销时间；失败返回 None（由调用方回退内存）。"""
    if time.time() < _redis_fallback_until:
        return None
    try:
        from app.core.redis import get_sync_redis

        raw = get_sync_redis().get(_revocation_key(user_id))
        if not raw:
            return None
        return float(raw)
    except Exception as e:
        logger.warning("Redis 吊销读取失败，回退内存: %s", e)
        _mark_redis_fallback()
        return None


def _redis_set_revoked(user_id: UUID, revoked_at: float) -> None:
    """持久化吊销到 Redis；失败仅本进程内存生效并进入冷却。"""
    if time.time() < _redis_fallback_until:
        return
    try:
        from app.core.redis import get_sync_redis

        get_sync_redis().set(_revocation_key(user_id), str(revoked_at), ex=_TTL)
    except Exception as e:
        logger.warning("Redis 吊销写入失败，仅本进程生效: %s", e)
        _mark_redis_fallback()


def revoke_user_tokens(user_id: UUID) -> None:
    """用户改密后调用：标记该用户在此时间点前签发的所有 token 失效。"""
    now = time.time()
    with _lock:
        _revoked_before[user_id] = now
    if _backend_is_redis():
        _redis_set_revoked(user_id, now)


def is_token_revoked(user_id: UUID, iat_timestamp: float | None) -> bool:
    """检查 JWT 是否已被吊销。iat_timestamp 来自 JWT payload 的 iat 字段。"""
    if iat_timestamp is None:
        return False
    with _lock:
        # 先清理过期条目再查表，避免用已过期记录的陈旧快照做比较
        _prune_expired()
        revoked_at = _revoked_before.get(user_id)
    if revoked_at is None and _backend_is_redis():
        remote = _redis_get_revoked(user_id)
        if remote is not None:
            with _lock:
                _revoked_before[user_id] = remote
            revoked_at = remote
    if revoked_at is None:
        return False
    return iat_timestamp < revoked_at


def _prune_expired() -> None:
    """清理超过 TTL 的吊销记录（锁外调用需持锁）。"""
    cutoff = time.time() - _TTL
    expired = [uid for uid, ts in _revoked_before.items() if ts < cutoff]
    for uid in expired:
        del _revoked_before[uid]


def reset_token_revocation_state() -> None:
    """测试用：清空进程内吊销缓存与 Redis 回退冷却态。"""
    global _redis_fallback_until
    with _lock:
        _revoked_before.clear()
        _redis_fallback_until = 0.0
