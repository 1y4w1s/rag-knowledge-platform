"""知识库列表 limit/offset/q/sort 分页。"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

from app.core.database import SessionLocal
from app.models.document import Document
from app.models.enums import DocumentStatus
from tests.conftest import create_test_kb as _create_kb, workspace_query


async def _seed_kb(
    client: AsyncClient,
    headers: dict[str, str],
    user: dict,
    *,
    name: str,
    description: str | None = None,
) -> dict:
    payload: dict = {"name": name}
    if description is not None:
        payload["description"] = description
    resp = await client.post(
        "/api/v1/knowledge-bases",
        headers=headers,
        params=workspace_query(user),
        json=payload,
    )
    assert resp.status_code == 201
    return resp.json()


@pytest.mark.asyncio
async def test_list_knowledge_bases_default_page_size(
    client: AsyncClient,
    register_and_login,
) -> None:
    headers, user = await register_and_login(prefix="kb-page-default")
    kb = await _create_kb(client, headers, user, name="默认分页库")

    resp = await client.get(
        "/api/v1/knowledge-bases",
        headers=headers,
        params=workspace_query(user),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["limit"] == 24
    assert body["offset"] == 0
    assert body["total"] == 1
    assert len(body["items"]) == 1
    assert body["items"][0]["id"] == kb["id"]


@pytest.mark.asyncio
async def test_list_knowledge_bases_pagination(
    client: AsyncClient,
    register_and_login,
) -> None:
    headers, user = await register_and_login(prefix="kb-page-many")
    names = [f"分页库-{i:02d}" for i in range(30)]
    for name in names:
        await _seed_kb(client, headers, user, name=name)

    page1 = await client.get(
        "/api/v1/knowledge-bases",
        headers=headers,
        params={**workspace_query(user), "limit": 24, "offset": 0},
    )
    assert page1.status_code == 200
    body1 = page1.json()
    assert body1["total"] == 30
    assert body1["limit"] == 24
    assert len(body1["items"]) == 24

    page2 = await client.get(
        "/api/v1/knowledge-bases",
        headers=headers,
        params={**workspace_query(user), "limit": 24, "offset": 24},
    )
    assert page2.status_code == 200
    body2 = page2.json()
    assert body2["total"] == 30
    assert len(body2["items"]) == 6

    all_ids = {item["id"] for item in body1["items"] + body2["items"]}
    assert len(all_ids) == 30


@pytest.mark.asyncio
async def test_list_knowledge_bases_search_by_name(
    client: AsyncClient,
    register_and_login,
) -> None:
    headers, user = await register_and_login(prefix="kb-page-search")
    await _seed_kb(client, headers, user, name="产品手册库", description="对外")
    await _seed_kb(client, headers, user, name="研发规范库", description="含产品流程")

    resp = await client.get(
        "/api/v1/knowledge-bases",
        headers=headers,
        params={**workspace_query(user), "q": "产品"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    names = {item["name"] for item in body["items"]}
    assert names == {"产品手册库", "研发规范库"}


@pytest.mark.asyncio
async def test_list_knowledge_bases_sort_name_asc(
    client: AsyncClient,
    register_and_login,
) -> None:
    headers, user = await register_and_login(prefix="kb-page-sort")
    await _seed_kb(client, headers, user, name="Bravo")
    await _seed_kb(client, headers, user, name="Alpha")

    resp = await client.get(
        "/api/v1/knowledge-bases",
        headers=headers,
        params={**workspace_query(user), "sort": "name_asc", "limit": 100},
    )
    assert resp.status_code == 200
    names = [item["name"] for item in resp.json()["items"]]
    assert names[:2] == ["Alpha", "Bravo"]


@pytest.mark.asyncio
async def test_list_knowledge_bases_sort_needs_attention(
    client: AsyncClient,
    register_and_login,
) -> None:
    headers, user = await register_and_login(prefix="kb-page-attention")
    healthy = await _create_kb(client, headers, user, name="健康库")
    attention = await _create_kb(client, headers, user, name="失败库")
    kb_id = uuid.UUID(attention["id"])
    user_id = uuid.UUID(user["id"])

    async with SessionLocal() as db:
        db.add(
            Document(
                id=uuid.uuid4(),
                kb_id=kb_id,
                filename="bad.txt",
                file_type="txt",
                file_size=1,
                storage_path="/tmp/bad.txt",
                status=DocumentStatus.failed,
                uploaded_by=user_id,
            )
        )
        await db.commit()

    resp = await client.get(
        "/api/v1/knowledge-bases",
        headers=headers,
        params={**workspace_query(user), "sort": "needs_attention", "limit": 100},
    )
    assert resp.status_code == 200
    names = [item["name"] for item in resp.json()["items"]]
    assert names[0] == "失败库"
    assert healthy["id"] in {item["id"] for item in resp.json()["items"]}


@pytest.mark.asyncio
async def test_list_knowledge_bases_offset_beyond_total_returns_empty(
    client: AsyncClient,
    register_and_login,
) -> None:
    headers, user = await register_and_login(prefix="kb-page-empty-offset")
    await _create_kb(client, headers, user, name="唯一库")

    resp = await client.get(
        "/api/v1/knowledge-bases",
        headers=headers,
        params={**workspace_query(user), "limit": 24, "offset": 100},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"] == []
