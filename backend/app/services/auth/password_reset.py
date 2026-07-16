"""Forgot password / reset password service using SMTP."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import RateLimitError, ValidationError
from app.models.user import User
from app.services.auth.email import send_email_smtp
from app.services.auth.password import hash_password

logger = __import__("logging").getLogger(__name__)

RESET_TOKEN_KEY_PREFIX = "password_reset:"


def _generate_reset_token(user_id: uuid.UUID) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.forgot_password_token_expire_minutes
    )
    return jwt.encode(
        {"sub": str(user_id), "exp": expire, "type": "password_reset"},
        settings.jwt_secret,
        algorithm="HS256",
    )


def _verify_reset_token(token: str) -> uuid.UUID | None:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        if payload.get("type") != "password_reset":
            return None
        return uuid.UUID(payload["sub"])
    except (JWTError, ValueError, KeyError):
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
        return "邮件发送失败，请稍后重试"

    return "如果该邮箱已注册，您将收到密码重置邮件"


async def reset_password(
    db: AsyncSession,
    *,
    token: str,
    new_password: str,
) -> None:
    """Verify reset token and set new password."""
    from app.services.auth.service import MIN_PASSWORD_LEN, _validate_password

    user_id = _verify_reset_token(token)
    if user_id is None:
        raise ValidationError("重置链接无效或已过期")

    if len(new_password) < MIN_PASSWORD_LEN:
        raise ValidationError(f"密码至少 {MIN_PASSWORD_LEN} 位")

    _validate_password(new_password)

    user = await db.get(User, user_id)
    if user is None:
        raise ValidationError("重置链接无效或已过期")

    user.password_hash = hash_password(new_password)
    await db.commit()
