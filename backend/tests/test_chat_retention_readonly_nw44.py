"""NW-44：dashboard stats 只读回显 CHAT_RETENTION_DAYS（Admin 特权字段）。"""

import pytest
from httpx import AsyncClient

from tests.conftest import workspace_query
from tests.test_dashboard_cost_nw5 import _create_org_member_and_login


@pytest.mark.asyncio
async def test_personal_stats_include_chat_retention_days(
    client: AsyncClient,
    register_and_login,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "chat_retention_days", 30)
    headers, user = await register_and_login(prefix="nw44-personal")
    resp = await client.get(
        "/api/v1/dashboard/stats",
        headers=headers,
        params=workspace_query(user),
    )
    assert resp.status_code == 200
    assert resp.json()["chat_retention_days"] == 30


@pytest.mark.asyncio
async def test_org_admin_sees_retention_member_gets_null(
    client: AsyncClient,
    register_and_login,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "chat_retention_days", 90)
    admin_headers, admin_user = await register_and_login(
        prefix="nw44-org-admin",
        account_type="enterprise",
        org_name="NW44 保留公司",
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
    assert admin_resp.json()["chat_retention_days"] == 90
    assert member_resp.json()["chat_retention_days"] is None
