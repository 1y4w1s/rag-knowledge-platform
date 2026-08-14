"""Webhook 回调发送服务（Wave 7.5）。"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import ipaddress
import json
import logging
import socket
import time
from uuid import UUID
from urllib.parse import urlparse

import httpx

from app.services.webhook.security import decrypt_secret
from app.services.webhook.ssrf import reject_ssrf_resolved_ips, reject_ssrf_target

logger = logging.getLogger(__name__)


class WebhookSecretError(RuntimeError):
    """Webhook secret 无法解密时抛出：fail-closed，拒绝发送。"""


def _reject_ssrf_target(url: str) -> None:
    """校验 URL 不指向内网/回环/链路本地/云元数据地址（全地址族），且仅允许 HTTPS。"""
    reject_ssrf_target(url, allowed_schemes=frozenset({"https"}))


async def _resolve_host_ips(host: str, port: int) -> list[str]:
    """解析域名全部 A/AAAA 地址，供发送前 SSRF 校验。"""
    loop = asyncio.get_running_loop()
    infos = await loop.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    return sorted({info[4][0] for info in infos})


async def _reject_ssrf_resolved_targets(url: str) -> None:
    """发送前解析域名并逐 IP 校验，堵住域名指向内网的发送窗口。"""
    parsed = urlparse(url)
    host = (parsed.hostname or "").strip("[]")
    if not host:
        return
    try:
        ipaddress.ip_address(host)
        return  # 字面 IP 已由 _reject_ssrf_target 校验
    except ValueError:
        pass
    try:
        ips = await _resolve_host_ips(host, parsed.port or 443)
    except OSError as exc:
        logger.warning("webhook DNS resolution failed: host=%s error=%s", host, exc)
        raise ValueError("Webhook URL 域名解析失败，无法完成 SSRF 校验") from exc
    reject_ssrf_resolved_ips(ips)


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
    await _reject_ssrf_resolved_targets(url)
    try:
        secret = decrypt_secret(secret)
    except Exception as exc:
        logger.error(
            "webhook send blocked: event=%s url=%s reason=secret_decrypt_failed error=%s",
            event,
            url,
            exc,
        )
        raise WebhookSecretError("webhook secret 解密失败，拒绝发送") from exc
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
