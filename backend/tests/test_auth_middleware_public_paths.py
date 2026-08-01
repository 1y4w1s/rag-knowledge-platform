"""F1：中间件默认拒绝 + 显式白名单 行为锁定。

核心回归：任何不在显式白名单内的路径（含非 /api/v1 前缀的新路由）都必须要求 JWT，
不再因「非 /api/v1 前缀」而被反向默认放行。
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.core.config import settings
from app.core.security import _is_public_path


# ── 单元层：直接验证 _is_public_path 白名单逻辑 ──────────────────────
def test_default_deny_unknown_root_path() -> None:
    """非白名单的根级路径必须被拒绝（修复前会因反向默认公开而匿名可达）。"""
    assert _is_public_path("/some-future-route") is False
    assert _is_public_path("/openapi.json/debug") is False


def test_default_deny_unknown_api_path() -> None:
    """任何 /api/v1 下的业务路径均需 JWT（白名单未列出即拒绝）。"""
    assert _is_public_path("/api/v1/knowledge-bases") is False
    assert _is_public_path("/api/v1/internal-reverse-default") is False


def test_health_prefix_public() -> None:
    assert _is_public_path("/health") is True
    assert _is_public_path("/health/live") is True
    assert _is_public_path("/health/ready") is True
    assert _is_public_path("/health/detailed") is True


def test_metrics_public() -> None:
    """/metrics 由路由级静态令牌鉴权（P0-3），全局中间件免用户 JWT。"""
    assert _is_public_path("/metrics") is True


def test_internal_prefix_not_public() -> None:
    """F2：/api/v1/internal/* 已移出白名单，默认拒绝（须路由级 JWT + 静态令牌）。"""
    assert _is_public_path("/api/v1/internal/re-embed") is False
    assert _is_public_path("/api/v1/internal/orphan-scan") is False


async def test_internal_requires_jwt(client: "AsyncClient") -> None:
    """无 JWT 访问内部端点 → 401（F2 前会因白名单豁免而匿名可达）。"""
    resp = await client.post("/api/v1/internal/re-embed")
    assert resp.status_code == 401
    resp2 = await client.post("/api/v1/internal/orphan-scan")
    assert resp2.status_code == 401


def test_docs_public_in_dev(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "environment", "development")
    assert _is_public_path("/openapi.json") is True
    assert _is_public_path("/docs") is True
    assert _is_public_path("/redoc") is True


def test_openapi_blocked_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    """生产环境 OpenAPI Schema 不再匿名公开（R3）。"""
    monkeypatch.setattr(settings, "environment", "production")
    assert _is_public_path("/openapi.json") is False


# ── 集成层：经 ASGI 客户端验证默认拒绝确实拦截请求 ──────────────────
async def test_unknown_root_path_requires_jwt(client: "AsyncClient") -> None:
    """根级未知路径无 token → 401（而非被反向默认放行）。"""
    resp = await client.get("/some-future-route")
    assert resp.status_code == 401


async def test_business_api_requires_jwt(client: "AsyncClient") -> None:
    """业务路径无 token → 401（保持原有行为，验证未回归）。"""
    resp = await client.get("/api/v1/knowledge-bases")
    assert resp.status_code == 401
