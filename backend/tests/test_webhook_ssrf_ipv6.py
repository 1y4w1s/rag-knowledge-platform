"""P1-19 验收：webhook URL 全地址族（IPv4/IPv6）SSRF 校验（2026-08-02）。"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.api import webhooks as webhooks_api
from app.services.webhook import sender as webhook_sender
from app.services.webhook.security import encrypt_secret


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

    @pytest.mark.parametrize("url", PUBLIC_URLS)
    def test_send_allows_public_targets(self, url: str) -> None:
        webhook_sender._reject_ssrf_target(url)  # 不抛异常

    def test_send_rejects_http_plaintext(self) -> None:
        """发送端与创建端统一仅 HTTPS，http 明文在出站前即被拒绝。"""
        with pytest.raises(ValueError):
            webhook_sender._reject_ssrf_target("http://example.com/hook")

    @pytest.mark.parametrize("url", FORBIDDEN_URLS)
    def test_send_webhook_blocks_before_http(self, url: str) -> None:
        """send_webhook 在创建出站客户端前拒绝非法目标，不发起任何请求。"""
        with pytest.raises(ValueError):
            with patch.object(
                webhook_sender.httpx, "AsyncClient", autospec=True
            ) as client:
                asyncio.run(
                    webhook_sender.send_webhook(
                        url, encrypt_secret("whsec_dummy_secret_123"), "document.completed", {}
                    )
                )
        client.assert_not_called()

    def test_send_webhook_proceeds_for_public_target(self) -> None:
        """公网 URL 不被误伤：send_webhook 正常创建出站客户端并发送。"""
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
                        encrypt_secret("whsec_dummy_secret_123"),
                        "document.completed",
                        {},
                    )
                )
        assert ok is True
        client_cls.assert_called_once()
        client.post.assert_awaited_once()

    def test_send_webhook_rejects_http_before_http_client(self) -> None:
        """http 明文 URL 在创建出站客户端前即被拒绝，不发起任何请求。"""
        with pytest.raises(ValueError):
            with patch.object(
                webhook_sender.httpx, "AsyncClient", autospec=True
            ) as client:
                asyncio.run(
                    webhook_sender.send_webhook(
                        "http://example.com/hook",
                        encrypt_secret("whsec_dummy_secret_123"),
                        "document.completed",
                        {},
                    )
                )
        client.assert_not_called()


class TestSendSideResolvedIPs:
    """M3：发送前域名解析逐 IP 校验，堵住域名指向内网/云元数据的发送窗口。"""

    @pytest.mark.parametrize(
        "resolved_ips",
        [
            ["127.0.0.1"],
            ["10.1.2.3"],
            ["169.254.169.254"],
            ["100.100.100.200"],
            ["192.168.1.9", "93.184.216.34"],  # 任一命中即拒绝
            ["::1"],
            ["[fd00::1]"],
            ["::ffff:10.1.2.3"],
        ],
    )
    def test_send_webhook_rejects_domain_resolving_to_internal(
        self, resolved_ips: list[str]
    ) -> None:
        with patch.object(
            webhook_sender, "_resolve_host_ips", AsyncMock(return_value=resolved_ips)
        ):
            with pytest.raises(ValueError):
                with patch.object(
                    webhook_sender.httpx, "AsyncClient", autospec=True
                ) as client:
                    asyncio.run(
                        webhook_sender.send_webhook(
                            "https://evil.example.com/hook",
                            encrypt_secret("whsec_dummy_secret_123"),
                            "document.completed",
                            {},
                        )
                    )
        client.assert_not_called()

    def test_send_webhook_allows_domain_resolving_to_public_ip(self) -> None:
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
                        "https://public.example.com/hook",
                        encrypt_secret("whsec_dummy_secret_123"),
                        "document.completed",
                        {},
                    )
                )
        assert ok is True
        client_cls.assert_called_once()
        client.post.assert_awaited_once()

    def test_send_webhook_fails_closed_when_dns_resolution_errors(self) -> None:
        with patch.object(
            webhook_sender,
            "_resolve_host_ips",
            AsyncMock(side_effect=OSError("dns boom")),
        ):
            with pytest.raises(ValueError):
                with patch.object(
                    webhook_sender.httpx, "AsyncClient", autospec=True
                ) as client:
                    asyncio.run(
                        webhook_sender.send_webhook(
                            "https://unresolvable.example.com/hook",
                            encrypt_secret("whsec_dummy_secret_123"),
                            "document.completed",
                            {},
                        )
                    )
        client.assert_not_called()
