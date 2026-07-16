"""SMTP 邮件发送服务。"""

from __future__ import annotations

import logging
import smtplib
from email.mime.text import MIMEText

from app.core.config import settings

logger = logging.getLogger(__name__)


async def send_email_smtp(*, to: str, subject: str, html: str) -> None:
    """通过 SMTP 发送邮件。"""
    if not settings.smtp_host:
        logger.warning("SMTP_HOST 未配置，邮件未发送")
        return

    msg = MIMEText(html, "html", "utf-8")
    msg["Subject"] = subject
    msg["From"] = settings.forgot_password_from_email
    msg["To"] = to

    try:
        server = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15)
        if settings.smtp_use_tls:
            server.starttls()
        if settings.smtp_user:
            server.login(settings.smtp_user, settings.smtp_password)
        server.sendmail(settings.forgot_password_from_email, [to], msg.as_string())
        server.quit()
        logger.info("密码重置邮件已发送到 %s", to)
    except Exception as exc:
        logger.error("SMTP 发送失败: %s", exc)
        raise
