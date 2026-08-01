"""P0-1 回归：自定义角色端点必须绑定调用者自身 org，禁止跨租户越权（OWASP API1）。

修复前：``require_org_role`` 只校验调用者自身 org_role，不绑定 URL 里的 ``org_id``，
导致 A 组织 admin 把路径 ``org_id`` 换成 B 组织即可枚举/注入/篡改 B 的角色。
修复后：``require_org_scope`` 在依赖注入阶段断言 ``current_user.org_id == org_id``，
越权请求返回 404（不泄露目标组织是否存在）。
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.fixtures.audit_events import _register_org_admin


@pytest.mark.asyncio
async def test_org_admin_cannot_list_other_org_roles(client: AsyncClient) -> None:
    headers_a, user_a = await _register_org_admin(client, prefix="xrole-a", org_name="组织A")
    headers_b, user_b = await _register_org_admin(client, prefix="xrole-b", org_name="组织B")

    org_a = user_a["org_id"]
    org_b = user_b["org_id"]
    assert org_a != org_b

    # A 的 admin 试图列出 B 的角色 → 必须被拒（404，不泄露 B 是否存在）
    resp = await client.get(f"/api/v1/orgs/{org_b}/roles", headers=headers_a)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_org_admin_cannot_create_role_in_other_org(client: AsyncClient) -> None:
    headers_a, user_a = await _register_org_admin(client, prefix="xrole-c", org_name="组织C")
    _, user_b = await _register_org_admin(client, prefix="xrole-d", org_name="组织D")

    org_b = user_b["org_id"]

    # A 的 admin 试图在 B 注入一个 admin 级角色 → 必须被拒（404）
    resp = await client.post(
        f"/api/v1/orgs/{org_b}/roles",
        headers=headers_a,
        json={"name": "injected", "permissions": {"*": "admin"}, "is_admin_level": True},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_org_admin_can_manage_own_org_roles(client: AsyncClient) -> None:
    headers_a, user_a = await _register_org_admin(client, prefix="xrole-e", org_name="组织E")
    org_a = user_a["org_id"]

    # 同 org 内 admin 行为不受影响（修复不应改变正常路径）
    resp = await client.get(f"/api/v1/orgs/{org_a}/roles", headers=headers_a)
    assert resp.status_code == 200
