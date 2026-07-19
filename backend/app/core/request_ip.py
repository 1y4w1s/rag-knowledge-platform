"""从 HTTP 请求提取客户端 IP（EW-A3 审计用）。"""

from __future__ import annotations

from fastapi import Request


def get_client_ip(request: Request) -> str | None:
    """优先 X-Forwarded-For 首段，否则 request.client.host。"""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        candidate = forwarded.split(",")[0].strip()
        if candidate:
            return candidate
    if request.client is not None:
        return request.client.host
    return None
