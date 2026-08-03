"""Webhook URL SSRF 防护：全地址族（IPv4/IPv6）解析校验（P1-19）。

收敛既有两处校验（api/webhooks.py 创建端 + services/webhook/sender.py 发送端）
为单一实现，避免黑名单漂移。DNS rebinding 需域名二次解析方案，另行评估（T5-05）。
"""
from __future__ import annotations

import ipaddress
from urllib.parse import urlparse

# 域名/主机名黑名单（继承既有实现）：IP 类目标统一交由 ipaddress 层判定
_FORBIDDEN_HOSTS = frozenset({
    "169.254.169.254", "metadata.google.internal", "100.100.100.200",
    "localhost", "127.0.0.1", "0.0.0.0",
    "[::1]", "[0:0:0:0:0:0:0:1]",
})

# IPv4 云元数据地址（独立兜底：100.100.100.200 未被 ipaddress 归类为私网/保留）
_CLOUD_METADATA_IPS = frozenset({
    "169.254.169.254",  # AWS / GCP / Azure IMDS
    "100.100.100.200",  # 阿里云 IMDS
})

# 运营商级 NAT 共享地址段（RFC 6598：既非私网也非公网，不可作为外呼目标）
_CGNAT_NETWORKS = (ipaddress.ip_network("100.64.0.0/10"),)


def _is_forbidden_ip(host: str) -> bool:
    """host 为字面量 IP 时，判定是否属于不可外呼的地址族（含 IPv6 内嵌 IPv4）。"""
    bare = host.split("%", 1)[0].strip("[]")  # 剥 IPv6 zone id 与括号
    try:
        ip = ipaddress.ip_address(bare)
    except ValueError:
        return False  # 域名 → 交由域名层处理
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped  # IPv4 映射 IPv6（::ffff:a.b.c.d）统一按 IPv4 判定
    if isinstance(ip, ipaddress.IPv4Address):
        return (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_unspecified
            or ip.is_reserved
            or str(ip) in _CLOUD_METADATA_IPS
            or any(ip in net for net in _CGNAT_NETWORKS)
        )
    return (
        ip.is_private       # fc00::/7（含 fd00::/8）
        or ip.is_loopback   # ::1 及全写变体
        or ip.is_link_local  # fe80::/10
        or ip.is_multicast
        or ip.is_unspecified
        or ip.is_reserved
    )


def reject_ssrf_target(
    url: str,
    *,
    allowed_schemes: frozenset[str] = frozenset({"https", "http"}),
    allowed_domains: frozenset[str] = frozenset(),
) -> None:
    """校验 webhook URL 不指向内网/回环/链路本地/云元数据地址（全地址族）。"""
    parsed = urlparse(url)
    if parsed.scheme not in allowed_schemes:
        raise ValueError(
            f"Webhook URL 仅支持 {'/'.join(sorted(allowed_schemes))}"
        )
    host = (parsed.hostname or "").lower()
    if not host:
        raise ValueError("Webhook URL 缺少主机名")
    if host in _FORBIDDEN_HOSTS or _is_forbidden_ip(host):
        raise ValueError("Webhook URL 不能指向内网/回环/链路本地或云元数据地址")
    if allowed_domains and not any(
        host == d or host.endswith("." + d) for d in allowed_domains
    ):
        raise ValueError("Webhook URL 域名不在白名单内")
