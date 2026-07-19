"""API Key 认证：生成、哈希、验证（API Key 管理）。"""

from __future__ import annotations

import hashlib
import secrets
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import TokenClaims
from app.models.api_key import ApiKey
from app.models.enums import AccountType
from app.models.user import User

API_KEY_PREFIX = "zkan_"
API_KEY_LENGTH = 32  # hex chars after prefix


def _random_api_key() -> str:
    """生成 ``zkan_`` + 32 位随机 hex。"""
    return API_KEY_PREFIX + secrets.token_hex(API_KEY_LENGTH // 2)


def hash_api_key(raw_key: str) -> str:
    """SHA-256 哈希 API Key（不存明文）。"""
    return hashlib.sha256(raw_key.encode()).hexdigest()


def generate_api_key() -> tuple[str, str, str]:
    """生成 (raw_key, prefix, key_hash)。

    - raw_key：仅展示一次（创建响应中返回）
    - prefix：前 8 位（含 "zkan_"），用于用户识别
    - key_hash：SHA-256，存入 DB
    """
    raw = _random_api_key()
    prefix = raw[:8]
    return raw, prefix, hash_api_key(raw)


async def authenticate_api_key(
    db: AsyncSession,
    token_str: str,
) -> TokenClaims | None:
    """尝试验证 API Key，成功返回 TokenClaims，失败返回 None。

    验证步骤：
    1. 必须 ``zkan_`` 开头（避免与 JWT 混淆）
    2. SHA-256 哈希后查 ``api_keys`` 表
    3. 校验 is_active 和 expires_at
    4. 更新 last_used_at
    5. 查 User 表获取 account_type
    """
    if not token_str.startswith(API_KEY_PREFIX):
        return None

    key_hash = hash_api_key(token_str)
    result = await db.execute(
        select(ApiKey).where(
            ApiKey.key_hash == key_hash,
            ApiKey.is_active.is_(True),
        )
    )
    api_key = result.scalar_one_or_none()
    if api_key is None:
        return None

    # 检查是否过期
    if api_key.expires_at is not None:
        from datetime import datetime, timezone

        if datetime.now(timezone.utc) > api_key.expires_at:
            api_key.is_active = False
            await db.flush()
            return None

    # 更新 last_used_at
    from datetime import datetime, timezone

    api_key.last_used_at = datetime.now(timezone.utc)
    await db.flush()

    # 查 User 获取 account_type
    user = await db.get(User, api_key.user_id)
    if user is None:
        return None

    return TokenClaims(
        user_id=api_key.user_id,
        account_type=user.account_type,
    )
