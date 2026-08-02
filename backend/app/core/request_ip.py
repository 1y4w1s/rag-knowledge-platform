"""从 HTTP 请求提取可信客户端 IP（EW-A3 审计 · P0-05 XFF 信任链）。

信任模型（需反代配合，见 docker/nginx/default.conf）：
- ``trusted_proxy_count=0``（API 直连）：**完全忽略 X-Forwarded-For**，
  使用 TCP peer（``request.client.host``）——伪造 XFF 无法污染限流/审计 IP。
- ``trusted_proxy_count=N``：信任右数第 N 段（由 N 跳可信反代写入），
  取该段作为客户端 IP。生产默认 nginx 以 ``X-Forwarded-For $remote_addr``
  覆写，单跳部署下唯一段即真实客户端 IP。

安全边界：API 端口必须仅经可信反代可达（docker compose 内网），
否则直连客户端可伪造 XFF。
"""

from __future__ import annotations

from fastapi import Request

from app.core.config import settings


def resolve_client_ip(request: Request) -> str | None:
    """按可信代理链解析客户端 IP（审计 + 限流统一入口）。"""
    forwarded = request.headers.get("x-forwarded-for")
    trust = settings.trusted_proxy_count

    if trust > 0 and forwarded:
        parts = [p.strip() for p in forwarded.split(",") if p.strip()]
        # 右数第 trust 段：由最近的可信反代写入，代表其上一跳（客户端或前级代理）
        idx = len(parts) - trust
        if 0 <= idx < len(parts) and parts[idx]:
            return parts[idx]

    if request.client is not None:
        return request.client.host
    return None


def get_client_ip(request: Request) -> str | None:
    """兼容旧调用点：统一走 ``resolve_client_ip``。"""
    return resolve_client_ip(request)
