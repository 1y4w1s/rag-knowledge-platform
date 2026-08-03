"""Webhook 回调发送服务（Wave 7.5）。"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from uuid import UUID

import httpx

from app.services.webhook.security import decrypt_secret
from app.services.webhook.ssrf import reject_ssrf_target

logger = logging.getLogger(__name__)


def _reject_ssrf_target(url: str) -> None:
    """校验 URL 不指向内网/回环/链路本地/云元数据地址（全地址族）。"""
    reject_ssrf_target(url)


def _sign_payload(payload: bytes, secret: str) -> str:
    """HMAC-SHA256 签名。"""
    return hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()


async def send_webhook(
    url: str,
    secret: str,
    event: str,
    payload: dict,
    max_retries: int = 3,
) -> bool:
    """发送 webhook 回调，失败重试（指数退避）。

    Returns:
        True 表示发送成功，False 表示最终失败。
    """
    _reject_ssrf_target(url)
    # 尝试解密（兼容已有明文 secret，backfill 后全部加密）
    try:
        secret = decrypt_secret(secret)
    except Exception:
        pass  # 明文 secret，继续使用原值
    body = json.dumps(payload, ensure_ascii=False).encode()
    signature = _sign_payload(body, secret)

    headers = {
        "Content-Type": "application/json",
        "X-Webhook-Event": event,
        "X-Webhook-Signature": signature,
        "User-Agent": "Ruige-Webhook/1.0",
    }

    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(url, content=body, headers=headers)
            if resp.is_success:
                logger.info("webhook sent: event=%s url=%s status=%d", event, url, resp.status_code)
                return True
            logger.warning(
                "webhook attempt %d/%d failed: event=%s url=%s status=%d",
                attempt + 1, max_retries, event, url, resp.status_code,
            )
        except Exception as exc:
            logger.warning(
                "webhook attempt %d/%d error: event=%s url=%s error=%s",
                attempt + 1, max_retries, event, url, exc,
            )

        if attempt < max_retries - 1:
            time.sleep(2 ** attempt)  # 指数退避: 1s, 2s, 4s

    logger.error("webhook failed after %d retries: event=%s url=%s", max_retries, event, url)
    return False


def build_webhook_payload(
    event: str,
    kb_id: UUID,
    doc_id: UUID,
    filename: str,
    status: str,
    chunk_count: int | None = None,
    error: str | None = None,
) -> dict:
    """构建 webhook 回调请求体。"""
    return {
        "event": event,
        "kb_id": str(kb_id),
        "document_id": str(doc_id),
        "filename": filename,
        "status": status,
        "chunk_count": chunk_count,
        "error": error,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
