"""API Key 认证测试：创建/使用/吊销。"""

from uuid import UUID

import pytest
from httpx import AsyncClient, Response


@pytest.mark.asyncio
async def test_api_key_create_and_list(
    client: AsyncClient,
    register_and_login,
) -> None:
    headers, user = await register_and_login(prefix="api-key-1")
    # 创建 Key
    resp: Response = await client.post(
        "/api/v1/api-keys",
        json={"name": "test-key"},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["name"] == "test-key"
    assert data["raw_key"].startswith("zkan_")
    raw_key = data["raw_key"]

    # 列出 Key
    resp = await client.get("/api/v1/api-keys", headers=headers)
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) >= 1
    # raw_key 不在列表中
    assert all("raw_key" not in item for item in items)


@pytest.mark.asyncio
async def test_api_key_auth_via_bearer(
    client: AsyncClient,
    register_and_login,
) -> None:
    headers, user = await register_and_login(prefix="api-key-2")

    # 创建 Key
    resp = await client.post(
        "/api/v1/api-keys",
        json={"name": "ci-key"},
        headers=headers,
    )
    raw_key = resp.json()["raw_key"]

    # 用 Key 调 API（免登录）
    key_headers = {"Authorization": f"Bearer {raw_key}"}
    resp = await client.get("/api/v1/knowledge-bases", headers=key_headers)
    assert resp.status_code == 200, resp.text


@pytest.mark.asyncio
async def test_api_key_revoke_returns_401(
    client: AsyncClient,
    register_and_login,
) -> None:
    headers, user = await register_and_login(prefix="api-key-3")

    # 创建 Key
    resp = await client.post(
        "/api/v1/api-keys",
        json={"name": "revoke-me"},
        headers=headers,
    )
    raw_key = resp.json()["raw_key"]
    key_id = resp.json()["id"]

    # 撤销
    resp = await client.delete(f"/api/v1/api-keys/{key_id}", headers=headers)
    assert resp.status_code == 204

    # 用已撤销 Key 调 API → 401
    key_headers = {"Authorization": f"Bearer {raw_key}"}
    resp = await client.get("/api/v1/knowledge-bases", headers=key_headers)
    assert resp.status_code == 401, resp.text
