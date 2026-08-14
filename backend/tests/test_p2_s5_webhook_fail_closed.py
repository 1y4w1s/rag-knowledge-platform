"""P2-S5 验收：webhook 发送端密钥解密失败 fail-closed（2026-08-09）。"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.config import settings
from app.services.ingestion import pipeline
from app.services.webhook import sender as webhook_sender
from app.services.webhook.security import encrypt_secret

_TEST_WEBHOOK_KEY = "test-only-webhook-encryption-key-0123456789abcdef"
_OTHER_WEBHOOK_KEY = "another-webhook-encryption-key-0123456789abcdef"


def _run_send(secret: str) -> None:
    asyncio.run(
        webhook_sender.send_webhook(
            "https://example.com/hook",
            secret,
            "document.completed",
            {"event": "document.completed"},
        )
    )


class TestSendWebhookFailClosed:
    def test_decrypt_failure_blocks_send_without_http(self, monkeypatch) -> None:
        ciphertext = encrypt_secret("whsec_rotated_secret_123")
        monkeypatch.setattr(settings, "webhook_encryption_secret", _OTHER_WEBHOOK_KEY)
        with pytest.raises(webhook_sender.WebhookSecretError):
            with patch.object(
                webhook_sender.httpx, "AsyncClient", autospec=True
            ) as client:
                _run_send(ciphertext)
        client.assert_not_called()

    def test_plaintext_secret_fails_closed(self) -> None:
        with pytest.raises(webhook_sender.WebhookSecretError):
            with patch.object(
                webhook_sender.httpx, "AsyncClient", autospec=True
            ) as client:
                _run_send("whsec_plaintext_not_encrypted")
        client.assert_not_called()

    def test_decrypt_failure_logs_blocked_reason(
        self,
        monkeypatch,
        caplog,
    ) -> None:
        ciphertext = encrypt_secret("whsec_rotated_secret_123")
        monkeypatch.setattr(settings, "webhook_encryption_secret", _OTHER_WEBHOOK_KEY)
        with pytest.raises(webhook_sender.WebhookSecretError):
            with patch.object(
                webhook_sender.httpx, "AsyncClient", autospec=True
            ):
                _run_send(ciphertext)
        assert "reason=secret_decrypt_failed" in caplog.text

    def test_valid_encrypted_secret_signs_with_plaintext(self) -> None:
        plain = "whsec_sign_check_123"
        encrypted = encrypt_secret(plain)
        with patch.object(
            webhook_sender, "_resolve_host_ips", AsyncMock(return_value=["93.184.216.34"])
        ):
            with patch.object(
                webhook_sender.httpx, "AsyncClient", autospec=True
            ) as client_cls:
                client = client_cls.return_value.__aenter__.return_value
                client.post = AsyncMock(
                    return_value=SimpleNamespace(is_success=True, status_code=200)
                )
                ok = asyncio.run(
                    webhook_sender.send_webhook(
                        "https://example.com/hook",
                        encrypted,
                        "document.completed",
                        {"event": "document.completed"},
                    )
                )
        assert ok is True
        call = client.post.await_args
        assert call is not None
        body = call.kwargs["content"]
        expected = hmac.new(plain.encode(), body, hashlib.sha256).hexdigest()
        assert call.kwargs["headers"]["X-Webhook-Signature"] == expected


@pytest.mark.asyncio
async def test_trigger_webhooks_blocked_secret_writes_audit_and_continues(
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "webhook_encryption_secret", _OTHER_WEBHOOK_KEY)
    bad_ciphertext = encrypt_secret("whsec_rotated_secret_123")
    monkeypatch.setattr(settings, "webhook_encryption_secret", _TEST_WEBHOOK_KEY)

    bad_wh = SimpleNamespace(
        id=uuid.uuid4(),
        url="https://example.com/bad",
        secret=bad_ciphertext,
        created_by=uuid.uuid4(),
    )
    good_wh = SimpleNamespace(
        id=uuid.uuid4(),
        url="https://example.com/good",
        secret=encrypt_secret("whsec_good_123"),
        created_by=uuid.uuid4(),
    )
    doc = SimpleNamespace(kb_id=uuid.uuid4(), id=uuid.uuid4(), filename="测试.pdf")
    db = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = [bad_wh, good_wh]
    db.execute = AsyncMock(return_value=result)

    with patch.object(
        webhook_sender, "_resolve_host_ips", AsyncMock(return_value=["93.184.216.34"])
    ):
        with patch.object(
            webhook_sender.httpx, "AsyncClient", autospec=True
        ) as client_cls:
            client = client_cls.return_value.__aenter__.return_value
            client.post = AsyncMock(
                return_value=SimpleNamespace(is_success=True, status_code=200)
            )
            with patch(
                "app.services.audit.log.write_audit_log",
                new=AsyncMock(),
            ) as write_audit:
                await pipeline._trigger_webhooks(
                    db,
                    doc,
                    completed=True,
                    chunk_count=3,
                )

    write_audit.assert_awaited_once()
    audit_kwargs = write_audit.await_args.kwargs
    assert audit_kwargs["action"] == "webhook.send_blocked"
    assert audit_kwargs["actor_user_id"] == bad_wh.created_by
    assert audit_kwargs["resource_type"] == "webhook"
    assert audit_kwargs["resource_id"] == bad_wh.id
    assert audit_kwargs["kb_id"] == doc.kb_id
    assert audit_kwargs["metadata"] == {
        "reason": "secret_decrypt_failed",
        "url": bad_wh.url,
        "event": "document.completed",
    }
    client.post.assert_awaited_once()  # 仅 good webhook 真正出站，坏密钥不阻断同批
