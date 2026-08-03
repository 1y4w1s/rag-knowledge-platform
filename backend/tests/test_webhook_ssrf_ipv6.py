"""P1-19 验收：webhook URL 全地址族（IPv4/IPv6）SSRF 校验（2026-08-02）。"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.api import webhooks as webhooks_api
from app.services.webhook import sender as webhook_sender


# 不可外呼目标：IPv6 私网/链路本地/回环 + IPv4 映射 IPv6 + IPv4 内网/回环/元数据
FORBIDDEN_URLS = [
    # IPv6 私网（fc00::/7，含 fd00::/8 与 fd12 段）
    "https://[fd00::1]/hook",
    "https://[fd12:3456::1]/hook",
    # IPv6 链路本地（fe80::/10，含 zone id 变体）
    "https://[fe80::1]/hook",
    "https://[fe80::1%25eth0]/hook",
    # IPv6 回环（::1 及全写变体）
    "https://[::1]/hook",
    "https://[0:0:0:0:0:0:0:1]/hook",
    # IPv4 映射 IPv6（::ffff:a.b.c.d）
    "https://[::ffff:127.0.0.1]/hook",
    "https://[::ffff:10.1.2.3]/hook",
    "https://[::ffff:169.254.169.254]/hook",
    "https://[::ffff:100.100.100.200]/hook",
    # IPv4 私网/回环/未指定/链路本地/云元数据
    "https://10.0.0.1/hook",
    "https://172.16.0.1/hook",
    "https://192.168.1.1/hook",
    "https://127.0.0.1/hook",
    "https://0.0.0.0/hook",
    "https://169.254.169.254/hook",
    "https://100.100.100.200/hook",
    # 域名层黑名单（既有行为保留）
    "https://localhost/hook",
    "https://metadata.google.internal/hook",
]

PUBLIC_URLS = [
    "https://example.com/hook",
    "https://1.1.1.1/hook",
    "https://8.8.8.8/hook",
    "https://[2606:4700:4700::1111]/hook",
    "https://[2001:4860:4860::8888]/hook",
]


class TestCreateSide:
    """创建端（api/webhooks.py 挂点）校验。"""

    @pytest.mark.parametrize("url", FORBIDDEN_URLS)
    def test_create_rejects_private_and_ipv6_targets(self, url: str) -> None:
        with pytest.raises(ValueError):
            webhooks_api._reject_ssrf_target(url)

    @pytest.mark.parametrize("url", PUBLIC_URLS)
    def test_create_allows_public_targets(self, url: str) -> None:
        assert webhooks_api._reject_ssrf_target(url) == url

    def test_create_rejects_non_https(self) -> None:
        with pytest.raises(ValueError):
            webhooks_api._reject_ssrf_target("http://example.com/hook")


class TestSendSide:
    """发送端（services/webhook/sender.py 挂点）校验。"""

    @pytest.mark.parametrize("url", FORBIDDEN_URLS)
    def test_send_rejects_private_and_ipv6_targets(self, url: str) -> None:
        with pytest.raises(ValueError):
            webhook_sender._reject_ssrf_target(url)

    @pytest.mark.parametrize("url", PUBLIC_URLS + ["http://example.com/hook"])
    def test_send_allows_public_targets(self, url: str) -> None:
        webhook_sender._reject_ssrf_target(url)  # 不抛异常

    @pytest.mark.parametrize("url", FORBIDDEN_URLS)
    def test_send_webhook_blocks_before_http(self, url: str) -> None:
        """send_webhook 在创建出站客户端前拒绝非法目标，不发起任何请求。"""
        with pytest.raises(ValueError):
            with patch.object(
                webhook_sender.httpx, "AsyncClient", autospec=True
            ) as client:
                asyncio.run(
                    webhook_sender.send_webhook(
                        url, "whsec_dummy_secret_123", "document.completed", {}
                    )
                )
        client.assert_not_called()

    def test_send_webhook_proceeds_for_public_target(self) -> None:
        """公网 URL 不被误伤：send_webhook 正常创建出站客户端并发送。"""
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
                    "whsec_dummy_secret_123",
                    "document.completed",
                    {},
                )
            )
        assert ok is True
        client_cls.assert_called_once()
        client.post.assert_awaited_once()
