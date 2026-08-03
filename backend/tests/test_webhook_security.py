"""P1-A 验收测试。"""
from __future__ import annotations

import pytest

from app.core.database import SessionLocal
from app.models.webhook import Webhook
from app.services.webhook.security import decrypt_secret, encrypt_secret
from tests.conftest import create_test_kb


class TestCryptography:
    def test_encrypt_decrypt_roundtrip(self) -> None:
        plain = "whsec_abc123!@#XYZ"
        encrypted = encrypt_secret(plain)
        assert encrypted != plain
        assert decrypt_secret(encrypted) == plain

    def test_same_plain_different_ciphertext(self) -> None:
        results = {encrypt_secret("whsec_constant") for _ in range(3)}
        assert len(results) == 3

    def test_ciphertext_not_readable(self) -> None:
        encrypted = encrypt_secret("my-secret-key-42")
        assert "my-secret-key-42" not in encrypted

    def test_decrypt_invalid_token_raises(self) -> None:
        from cryptography.fernet import InvalidToken
        with pytest.raises(InvalidToken):
            decrypt_secret("gAAAAABfake_token_that_is_not_valid==")

    def test_decrypt_plaintext_fallback(self) -> None:
        with pytest.raises(Exception):
            decrypt_secret("whsec_plaintext_not_encrypted")

    def test_long_secret(self) -> None:
        plain = "x" * 128
        assert decrypt_secret(encrypt_secret(plain)) == plain


@pytest.mark.skip(reason="需要真实 PostgreSQL 数据库，CI 中运行")
class TestWebhookAPISecretEncryption:
    """集成测试（需要真实 DB 和 JWT_SECRET 环境变量）。"""

    @pytest.fixture(autouse=True)
    async def setup(self, register_and_login, client):
        headers, user = await register_and_login(prefix="wh-p1a")
        kb = await create_test_kb(client, headers, user)
        self.headers = headers
        self.user = user
        self.kb_id = kb["id"]
        self.client = client

    async def test_create_webhook_secret_is_encrypted_in_db(self) -> None:
        plain_secret = "whsec_my_test_secret_123"
        resp = await self.client.post(
            f"/api/v1/knowledge-bases/{self.kb_id}/webhooks",
            headers=self.headers,
            json={
                "url": "https://example.com/webhook",
                "secret": plain_secret,
                "events": "document.completed",
            },
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        wh_id = data["id"]
        assert "secret" not in data

        async with SessionLocal() as db:
            wh = await db.get(Webhook, wh_id)

        assert wh is not None
        assert wh.secret != plain_secret
        assert decrypt_secret(wh.secret) == plain_secret

    async def test_list_webhooks_no_secret(self) -> None:
        await self.client.post(
            f"/api/v1/knowledge-bases/{self.kb_id}/webhooks",
            headers=self.headers,
            json={
                "url": "https://example.com/list-test",
                "secret": "whsec_list_test_123",
                "events": "document.completed",
            },
        )
        resp = await self.client.get(
            f"/api/v1/knowledge-bases/{self.kb_id}/webhooks",
            headers=self.headers,
        )
        assert resp.status_code == 200
        for item in resp.json():
            assert "secret" not in item

    async def test_create_with_minimal_secret(self) -> None:
        resp = await self.client.post(
            f"/api/v1/knowledge-bases/{self.kb_id}/webhooks",
            headers=self.headers,
            json={
                "url": "https://httpbin.org/post",
                "secret": "abc123!@",
                "events": "document.completed",
            },
        )
        assert resp.status_code == 201, resp.text

    async def test_same_plain_differs_in_db(self) -> None:
        plain = "whsec_nonce_test"
        secrets: set[str] = set()
        for _ in range(2):
            resp = await self.client.post(
                f"/api/v1/knowledge-bases/{self.kb_id}/webhooks",
                headers=self.headers,
                json={
                    "url": "https://example.com/nonce-test",
                    "secret": plain,
                    "events": "document.completed",
                },
            )
            assert resp.status_code == 201, resp.text
            wh_id = resp.json()["id"]
            async with SessionLocal() as db:
                wh = await db.get(Webhook, wh_id)
            assert wh is not None
            secrets.add(wh.secret)
        assert len(secrets) == 2

    async def test_delete_webhook(self) -> None:
        resp = await self.client.post(
            f"/api/v1/knowledge-bases/{self.kb_id}/webhooks",
            headers=self.headers,
            json={
                "url": "https://example.com/to-delete",
                "secret": "whsec_delete_me",
                "events": "document.completed",
            },
        )
        assert resp.status_code == 201, resp.text
        wh_id = resp.json()["id"]
        del_resp = await self.client.delete(
            f"/api/v1/knowledge-bases/{self.kb_id}/webhooks/{wh_id}",
            headers=self.headers,
        )
        assert del_resp.status_code == 204
        list_resp = await self.client.get(
            f"/api/v1/knowledge-bases/{self.kb_id}/webhooks",
            headers=self.headers,
        )
        ids = [item["id"] for item in list_resp.json()]
        assert wh_id not in ids
