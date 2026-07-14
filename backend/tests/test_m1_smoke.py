"""M1 Smoke: 资料库列表 count + 搜索过滤。"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

from tests.conftest import create_test_kb as _create_kb

pytestmark = pytest.mark.asyncio


async def test_kb_list_count_after_seed(
    client: AsyncClient,
    register_and_login,
) -> None:
    """创建一批资料库后列表 total ≥ 预期值。"""
    headers, user = await register_and_login(prefix="m1-smoke-count")
    total = 5
    for i in range(total):
        await _create_kb(
            client, headers, user,
            name=f"M1 冒烟测试库-{i:03d}",
        )

    # 获取团队 workspace query param
    from tests.conftest import workspace_query
    params = workspace_query(user)
    resp = await client.get("/api/v1/knowledge-bases", params=params, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= total, (
        f"Expected >= {total} KBs, got {data['total']}"
    )


async def test_kb_search_by_name(
    client: AsyncClient,
    register_and_login,
) -> None:
    """资料库按名称搜索 ?q=产品 应返回匹配的库。"""
    headers, user = await register_and_login(prefix="m1-smoke-search")

    await _create_kb(
        client, headers, user,
        name="产品路线图",
        description="产品侧规划文档",
    )
    await _create_kb(
        client, headers, user,
        name="市场推广方案",
        description="市场部活动方案",
    )
    await _create_kb(
        client, headers, user,
        name="研发技术规范",
        description="后端架构文档",
    )

    from tests.conftest import workspace_query
    params = workspace_query(user)
    params["q"] = "产品"
    resp = await client.get("/api/v1/knowledge-bases", params=params, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    names = [item["name"] for item in data["items"]]
    assert "产品路线图" in names, f"Expected '产品路线图' in search results: {names}"
    assert "市场推广方案" not in names, (
        f"'市场推广方案' should not match '产品': {names}"
    )
