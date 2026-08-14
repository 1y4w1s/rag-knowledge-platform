"""Forgot password / reset password service using SMTP."""
from __future__ import annotations

import hashlib
import hmac
import logging
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from jwt.exceptions import InvalidTokenError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import ValidationError
from app.models.user import User
from app.services.auth.email import send_email_smtp
from app.services.auth.password import hash_password, validate_password_strength

logger = logging.getLogger(__name__)

RESET_TOKEN_KEY_PREFIX = "password_reset:"

# P2-S2：重置令牌使用域分隔派生密钥，不再与登录令牌共用 jwt_secret
_RESET_TOKEN_KEY_DOMAIN = b"ruige:password-reset:v1"


def _reset_token_secret() -> str:
    """返回重置令牌专用签名密钥（从 jwt_secret 派生，域分隔防串用）。"""
    return hmac.new(
        settings.jwt_secret.encode("utf-8"),
        _RESET_TOKEN_KEY_DOMAIN,
        hashlib.sha256,
    ).hexdigest()


# M4：已消耗的密码重置 token（内存集合，定期清理过期项）
_consumed_tokens: dict[str, float] = {}
_consumed_lock = threading.Lock()
_CONSUMED_CLEANUP_INTERVAL = 300  # 每 5 分钟清理一次
_last_cleanup = time.monotonic()


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _mark_token_consumed(token: str, ttl_seconds: int) -> None:
    """将 token 标记为已消耗，在 ttl_seconds 后自动过期。"""
    global _last_cleanup
    h = _token_hash(token)
    expires_at = time.monotonic() + ttl_seconds
    with _consumed_lock:
        _consumed_tokens[h] = expires_at
        # 定期清理过期项
        now = time.monotonic()
        if now - _last_cleanup > _CONSUMED_CLEANUP_INTERVAL:
            expired = [k for k, v in _consumed_tokens.items() if v < now]
            for k in expired:
                del _consumed_tokens[k]
            _last_cleanup = now


def _is_token_consumed(token: str) -> bool:
    h = _token_hash(token)
    with _consumed_lock:
        expires_at = _consumed_tokens.get(h)
        if expires_at is None:
            return False
        if time.monotonic() > expires_at:
            del _consumed_tokens[h]
            return False
        return True


# ── DB 持久化（重启不可重放） ──


async def _mark_token_consumed_db(
    db: AsyncSession, user_id: uuid.UUID, token: str
) -> None:
    """将 token 标记为已消耗（写入数据库，由调用方在同一事务内提交）。"""
    from app.models.password_reset import PasswordResetToken

    token_hash = hashlib.sha256(token.encode()).hexdigest()
    record = PasswordResetToken(
        user_id=user_id,
        token_hash=token_hash,
        used_at=datetime.now(timezone.utc),
    )
    db.add(record)


async def _is_token_consumed_db(db: AsyncSession, token: str) -> bool:
    """检查 token 是否已被消耗（查数据库）。"""
    from app.models.password_reset import PasswordResetToken

    token_hash = hashlib.sha256(token.encode()).hexdigest()
    result = await db.execute(
        select(PasswordResetToken).where(
            PasswordResetToken.token_hash == token_hash
        ).limit(1)
    )
    return result.scalar_one_or_none() is not None


def _generate_reset_token(user_id: uuid.UUID) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.forgot_password_token_expire_minutes
    )
    return jwt.encode(
        {"sub": str(user_id), "exp": expire, "type": "password_reset"},
        _reset_token_secret(),
        algorithm="HS256",
    )


def _verify_reset_token(token: str) -> uuid.UUID | None:
    try:
        payload = jwt.decode(token, _reset_token_secret(), algorithms=["HS256"])
        if payload.get("type") != "password_reset":
            return None
        return uuid.UUID(payload["sub"])
    except (InvalidTokenError, ValueError, KeyError):
        return None


async def send_password_reset_email(
    db: AsyncSession,
    *,
    identifier: str,
) -> str:
    """Find user by email/username, generate token, send email via SMTP."""
    user = await db.scalar(
        select(User).where(
            (User.email == identifier) | (User.username == identifier)
        )
    )
    if user is None:
        return "如果该邮箱已注册，您将收到密码重置邮件"

    token = _generate_reset_token(user.id)

    if not settings.smtp_host:
        logger.warning("SMTP_HOST 未配置，密码重置邮件未发送")
        return "如果该邮箱已注册，您将收到密码重置邮件"

    reset_url = f"{settings.forgot_password_reset_url}?token={token}"

    try:
        await send_email_smtp(
            to=user.email,
            subject="重置您的睿阁密码",
            html=f"""
            <p>您好，</p>
            <p>请点击以下链接重置密码（链接有效期 {settings.forgot_password_token_expire_minutes} 分钟）：</p>
            <p><a href="{reset_url}">{reset_url}</a></p>
            <p>如果这不是您本人操作，请忽略此邮件。</p>
            """,
        )
    except Exception:
        # P2-S4：SMTP 故障也返回统一口径，避免通过响应文案枚举邮箱
        logger.warning("密码重置邮件发送失败，按统一口径响应: user_id=%s", user.id)
        return "如果该邮箱已注册，您将收到密码重置邮件"

    return "如果该邮箱已注册，您将收到密码重置邮件"


async def reset_password(
    db: AsyncSession,
    *,
    token: str,
    new_password: str,
) -> None:
    """Verify reset token and set new password."""
    user_id = _verify_reset_token(token)
    if user_id is None:
        raise ValidationError("重置链接无效或已过期")

    validate_password_strength(new_password)

    if _is_token_consumed(token):
        raise ValidationError("重置链接已使用，请重新申请")

    # P2-S4：行锁串行化同一用户的并发重置，避免“查已用→改密→写已用”竞态
    result = await db.execute(
        select(User).where(User.id == user_id).with_for_update()
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise ValidationError("重置链接无效或已过期")

    # 获取行锁后再次校验，并发败方在此看到胜方已提交的消耗记录
    if await _is_token_consumed_db(db, token):
        raise ValidationError("重置链接已使用，请重新申请")

    user.password_hash = hash_password(new_password)
    await _mark_token_consumed_db(db, user_id, token)
    await db.commit()
    _mark_token_consumed(token, settings.forgot_password_token_expire_minutes * 60)

    from app.services.auth.token_revocation import revoke_user_tokens
    revoke_user_tokens(user_id)

    logger.info("password reset success: user_id=%s", user_id)
