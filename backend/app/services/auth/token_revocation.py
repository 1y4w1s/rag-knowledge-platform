"""R1: 令牌吊销追踪（内存方案，零迁移）。

维护 user_id → password_changed_at 映射。
通过比较 JWT 的 iat（签发时间）与 password_changed_at：
- iat < password_changed_at → 旧 token，拒绝
- iat >= password_changed_at → 有效

单实例部署有效；多副本场景建议换 Redis。
"""

from __future__ import annotations

import time
import threading
from uuid import UUID

_revoked_before: dict[UUID, float] = {}
_lock = threading.Lock()
_TTL = 86400 * 7  # 7 天自动清理


def revoke_user_tokens(user_id: UUID) -> None:
    """用户改密后调用：标记该用户在此时间点前签发的所有 token 失效。"""
    now = time.monotonic()
    with _lock:
        _revoked_before[user_id] = now


def is_token_revoked(user_id: UUID, iat_timestamp: float | None) -> bool:
    """检查 JWT 是否已被吊销。iat_timestamp 来自 JWT payload 的 iat 字段。"""
    if iat_timestamp is None:
        return False
    with _lock:
        revoked_at = _revoked_before.get(user_id)
        if revoked_at is None:
            return False
        # 定期清理过期条目
        _prune_expired()
        return iat_timestamp < revoked_at


def _prune_expired() -> None:
    """清理超过 TTL 的吊销记录（锁外调用需持锁）。"""
    cutoff = time.monotonic() - _TTL
    expired = [uid for uid, ts in _revoked_before.items() if ts < cutoff]
    for uid in expired:
        del _revoked_before[uid]
