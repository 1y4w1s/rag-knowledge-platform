"""NW-46：dashboard stats 只读回显安全/运营开关（Admin 特权字段）。"""

import pytest
from httpx import AsyncClient

from tests.conftest import workspace_query
from tests.test_dashboard_cost_nw5 import _create_org_member_and_login


@pytest.mark.asyncio
async def test_personal_stats_include_ops_flags(
    client: AsyncClient,
    register_and_login,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.config import settings
    from app.services.auth import rate_limit_store

    monkeypatch.setattr(settings, "citation_redact_enabled", True)
    monkeypatch.setattr(settings, "llm_context_redact_enabled", False)
    monkeypatch.setattr(settings, "kb_quota_max_bytes", 10 * 1024**3)
    monkeypatch.setenv("RATE_LIMIT_BACKEND", "redis")
    rate_limit_store.reset_rate_limit_backend_cache()

    headers, user = await register_and_login(prefix="nw46-personal")
    resp = await client.get(
        "/api/v1/dashboard/stats",
        headers=headers,
        params=workspace_query(user),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["rate_limit_backend"] == "redis"
    assert body["citation_redact_enabled"] is True
    assert body["llm_context_redact_enabled"] is False
    assert body["kb_quota_max_bytes"] == 10 * 1024**3


@pytest.mark.asyncio
async def test_org_admin_sees_ops_flags_member_gets_null(
    client: AsyncClient,
    register_and_login,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.config import settings
    from app.services.auth import rate_limit_store

    monkeypatch.setattr(settings, "citation_redact_enabled", False)
    monkeypatch.setattr(settings, "llm_context_redact_enabled", True)
    monkeypatch.setattr(settings, "kb_quota_max_bytes", 0)
    monkeypatch.setenv("RATE_LIMIT_BACKEND", "memory")
    rate_limit_store.reset_rate_limit_backend_cache()

    admin_headers, admin_user = await register_and_login(
        prefix="nw46-org-admin",
        account_type="enterprise",
        org_name="NW46 开关公司",
    )
    member_headers, _member = await _create_org_member_and_login(
        client,
        org_id=admin_user["org_id"],
    )
    ws = workspace_query(admin_user)

    admin_resp = await client.get(
        "/api/v1/dashboard/stats", headers=admin_headers, params=ws
    )
    member_resp = await client.get(
        "/api/v1/dashboard/stats", headers=member_headers, params=ws
    )
    assert admin_resp.status_code == 200
    assert member_resp.status_code == 200

    admin_body = admin_resp.json()
    assert admin_body["rate_limit_backend"] == "memory"
    assert admin_body["citation_redact_enabled"] is False
    assert admin_body["llm_context_redact_enabled"] is True
    assert admin_body["kb_quota_max_bytes"] == 0

    member_body = member_resp.json()
    assert member_body["rate_limit_backend"] is None
    assert member_body["citation_redact_enabled"] is None
    assert member_body["llm_context_redact_enabled"] is None
    assert member_body["kb_quota_max_bytes"] is None
