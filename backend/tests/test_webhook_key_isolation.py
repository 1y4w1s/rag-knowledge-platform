"""P1-S2 验收：webhook 密钥与 JWT/LLM 等凭证体系隔离（2026-08-09）。"""

from __future__ import annotations

import base64
import hashlib
import json

import pytest
from cryptography.fernet import Fernet, InvalidToken
from httpx import AsyncClient

from app.core.config import settings
from app.services.webhook.security import decrypt_secret, encrypt_secret
from tests.conftest import create_test_kb
from tests.fixtures.audit_events import _count_audit_logs, _latest_audit_log

TEST_WEBHOOK_KEY = "test-only-webhook-encryption-key-0123456789abcdef"
TEST_SAFE_DATABASE_URL = (
    "postgresql+asyncpg://ruige:strong-random-db-password@localhost:5432/ruige"
)

_OTHER_CREDENTIAL_FIELDS = (
    "jwt_secret",
    "deepseek_api_key",
    "tongyi_api_key",
    "smtp_password",
    "orphan_scan_token",
    "re_embed_token",
    "metrics_bearer_token",
)


def _fernet_from(secret: str) -> Fernet:
    key = hashlib.sha256(secret.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def test_dedicated_key_is_set_and_distinct_from_other_credentials() -> None:
    assert settings.webhook_encryption_secret
    for field in _OTHER_CREDENTIAL_FIELDS:
        assert settings.webhook_encryption_secret != getattr(settings, field), field


def test_ciphertext_cannot_be_decrypted_with_jwt_secret() -> None:
    plain = "whsec_isolated_secret_123"
    encrypted = encrypt_secret(plain)
    with pytest.raises(InvalidToken):
        _fernet_from(settings.jwt_secret).decrypt(encrypted.encode())


def test_missing_dedicated_key_fails_closed_without_fallback(monkeypatch) -> None:
    monkeypatch.setattr(settings, "webhook_encryption_secret", "")
    with pytest.raises(RuntimeError, match="WEBHOOK_ENCRYPTION_SECRET"):
        encrypt_secret("whsec_any")
    with pytest.raises(RuntimeError, match="WEBHOOK_ENCRYPTION_SECRET"):
        decrypt_secret("gAAAAABfake_token_that_is_not_valid==")


def test_default_webhook_key_value_fails_closed(monkeypatch) -> None:
    monkeypatch.setattr(
        settings,
        "webhook_encryption_secret",
        "replace-with-a-long-random-string",
    )
    with pytest.raises(RuntimeError, match="WEBHOOK_ENCRYPTION_SECRET"):
        encrypt_secret("whsec_any")


def test_short_webhook_key_fails_closed(monkeypatch) -> None:
    monkeypatch.setattr(settings, "webhook_encryption_secret", "short")
    with pytest.raises(RuntimeError, match="WEBHOOK_ENCRYPTION_SECRET"):
        encrypt_secret("whsec_any")


def test_webhook_key_must_not_equal_jwt_secret(monkeypatch) -> None:
    shared = "same-shared-secret-value-0123456789abcdef"
    monkeypatch.setattr(settings, "webhook_encryption_secret", shared)
    monkeypatch.setattr(settings, "jwt_secret", shared)
    with pytest.raises(RuntimeError, match="WEBHOOK_ENCRYPTION_SECRET"):
        encrypt_secret("whsec_any")


def test_production_guard_rejects_missing_webhook_key(monkeypatch) -> None:
    from app.main import _check_production_guard

    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "webhook_encryption_secret", "")
    monkeypatch.setattr(settings, "database_url", TEST_SAFE_DATABASE_URL)
    with pytest.raises(RuntimeError, match="WEBHOOK_ENCRYPTION_SECRET"):
        _check_production_guard()


def test_production_guard_accepts_dedicated_webhook_key(monkeypatch) -> None:
    from app.main import _check_production_guard

    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "webhook_encryption_secret", TEST_WEBHOOK_KEY)
    monkeypatch.setattr(settings, "database_url", TEST_SAFE_DATABASE_URL)
    _check_production_guard()


def test_roundtrip_under_dedicated_key(monkeypatch) -> None:
    monkeypatch.setattr(settings, "webhook_encryption_secret", TEST_WEBHOOK_KEY)
    plain = "whsec_roundtrip_123!@#"
    assert decrypt_secret(encrypt_secret(plain)) == plain


def test_key_rotation_invalidates_old_ciphertext(monkeypatch) -> None:
    monkeypatch.setattr(settings, "webhook_encryption_secret", TEST_WEBHOOK_KEY)
    encrypted = encrypt_secret("whsec_rotate_me")
    monkeypatch.setattr(
        settings,
        "webhook_encryption_secret",
        TEST_WEBHOOK_KEY + "-rotated",
    )
    with pytest.raises(InvalidToken):
        decrypt_secret(encrypted)


@pytest.mark.asyncio
async def test_create_webhook_audit_marks_dedicated_encryption(
    client: AsyncClient,
    register_and_login,
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "webhook_encryption_secret", TEST_WEBHOOK_KEY)
    headers, user = await register_and_login(prefix="wh-isolation")
    kb = await create_test_kb(client, headers, user)

    before = await _count_audit_logs(action="webhook.create")
    plain_secret = "whsec_audit_isolation_123"
    resp = await client.post(
        f"/api/v1/knowledge-bases/{kb['id']}/webhooks",
        headers=headers,
        json={
            "url": "https://example.com/hook",
            "secret": plain_secret,
            "events": "document.completed",
        },
    )
    assert resp.status_code == 201, resp.text
    after = await _count_audit_logs(action="webhook.create")
    assert after - before == 1

    latest = await _latest_audit_log(action="webhook.create")
    assert latest is not None
    assert str(latest.resource_id) == resp.json()["id"]
    assert latest.details.get("secret_encryption") == "webhook_encryption_secret"
    assert plain_secret not in json.dumps(latest.details)
