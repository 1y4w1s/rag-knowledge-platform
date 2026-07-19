"""G3-1.2：list_knowledge_bases tool · ≤24 · scope_label。"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

from app.core.database import SessionLocal
from app.schemas.auth import UserPublic
from app.services.agent.tools.list_knowledge_bases import (
    AGENT_MAX_LIMIT,
    build_result_summary,
    normalize_agent_limit,
    run_list_knowledge_bases,
)
from app.services.org.scope import resolve_org_scope_for_workspace
from app.services.workspace.scope import resolve_workspace
from tests.conftest import create_test_kb, workspace_query


def test_normalize_agent_limit_defaults_and_caps() -> None:
    assert normalize_agent_limit(None) == 24
    assert normalize_agent_limit(10) == 10
    assert normalize_agent_limit(100) == AGENT_MAX_LIMIT
    assert normalize_agent_limit(0) == 1


def test_build_result_summary_matches_preview() -> None:
    assert build_result_summary(4, "OrgScope") == "可见库 4 个 · OrgScope"
    assert build_result_summary(1, "personal") == "可见库 1 个 · personal"


@pytest.mark.asyncio
async def test_list_knowledge_bases_personal_scope_label(
    client: AsyncClient,
    register_and_login,
) -> None:
    headers, user = await register_and_login(prefix="g3-list-kb-personal")
    kb = await create_test_kb(client, headers, user, name="个人可见库")

    async with SessionLocal() as db:
        current_user = UserPublic.model_validate(user)
        workspace = await resolve_workspace(db, current_user, "personal")
        result = await run_list_knowledge_bases(db, workspace)

    assert result.ok is True
    assert result.data.scope_label == "personal"
    assert result.summary == "可见库 1 个 · personal"
    assert len(result.data.items) == 1
    item = result.data.items[0]
    assert item.kb_id == uuid.UUID(kb["id"])
    assert item.name == "个人可见库"
    assert item.document_count == 0
    assert item.updated_at is not None


@pytest.mark.asyncio
async def test_list_knowledge_bases_org_scope_label(
    client: AsyncClient,
    register_and_login,
) -> None:
    headers, user = await register_and_login(
        prefix="g3-list-kb-org",
        account_type="enterprise",
        org_name="G3 List Org",
    )
    await create_test_kb(client, headers, user, name="团队库 A")

    async with SessionLocal() as db:
        current_user = UserPublic.model_validate(user)
        org_id = str(user["org_id"])
        workspace = await resolve_workspace(db, current_user, org_id)
        org_scope = await resolve_org_scope_for_workspace(db, current_user, workspace)
        result = await run_list_knowledge_bases(db, workspace, org_scope=org_scope)

    assert result.ok is True
    assert result.data.scope_label == "OrgScope"
    assert "OrgScope" in result.summary
    assert result.data.total >= 1


@pytest.mark.asyncio
async def test_list_knowledge_bases_respects_agent_limit_cap(
    client: AsyncClient,
    register_and_login,
) -> None:
    headers, user = await register_and_login(prefix="g3-list-kb-cap")
    for i in range(30):
        await create_test_kb(client, headers, user, name=f"批量库-{i:02d}")

    async with SessionLocal() as db:
        current_user = UserPublic.model_validate(user)
        workspace = await resolve_workspace(db, current_user, "personal")
        result = await run_list_knowledge_bases(db, workspace, limit=100)

    assert result.ok is True
    assert len(result.data.items) <= AGENT_MAX_LIMIT
    assert len(result.data.items) == 24
    assert result.data.total == 30


@pytest.mark.asyncio
async def test_list_knowledge_bases_search_by_q(
    client: AsyncClient,
    register_and_login,
) -> None:
    headers, user = await register_and_login(prefix="g3-list-kb-q")
    await create_test_kb(client, headers, user, name="人事制度库")
    await create_test_kb(client, headers, user, name="财务报销库")

    async with SessionLocal() as db:
        current_user = UserPublic.model_validate(user)
        workspace = await resolve_workspace(db, current_user, "personal")
        result = await run_list_knowledge_bases(db, workspace, q="人事")

    assert result.ok is True
    assert result.data.total == 1
    assert result.data.items[0].name == "人事制度库"


@pytest.mark.asyncio
async def test_list_knowledge_bases_matches_api_list(
    client: AsyncClient,
    register_and_login,
) -> None:
    """tool 与 GET /knowledge-bases 同 scope 下 total 一致。"""
    headers, user = await register_and_login(prefix="g3-list-kb-parity")
    await create_test_kb(client, headers, user, name="对齐库")

    api_resp = await client.get(
        "/api/v1/knowledge-bases",
        headers=headers,
        params=workspace_query(user),
    )
    assert api_resp.status_code == 200
    api_body = api_resp.json()

    async with SessionLocal() as db:
        current_user = UserPublic.model_validate(user)
        workspace = await resolve_workspace(
            db,
            current_user,
            workspace_query(user)["workspace"],
        )
        result = await run_list_knowledge_bases(db, workspace)

    assert result.data.total == api_body["total"]
    assert len(result.data.items) == len(api_body["items"])
