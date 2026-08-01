"""NW-5 / Eval-Ops M4：dashboard 用量与成本粗估（非计费）。"""

import uuid
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient

from app.core.database import SessionLocal
from app.models.chat_message import ChatMessage
from app.models.chat_thread import ChatThread
from app.models.enums import AccountType, MessageRole, OrgRole, ThreadKind
from app.models.organization_member import OrganizationMember
from app.models.user import User
from app.services.auth.password import hash_password
from app.services.dashboard.cost_estimate import (
    COST_ESTIMATE_NOTE,
    COST_PER_ASSISTANT_REPLY_CNY,
    estimate_chat_cost_cny_7d,
)
from tests.conftest import unique_email, unique_username, workspace_query


def test_estimate_chat_cost_formula() -> None:
    assert estimate_chat_cost_cny_7d(0) == 0.0
    assert estimate_chat_cost_cny_7d(100) == round(
        100 * COST_PER_ASSISTANT_REPLY_CNY, 2
    )


async def _create_org_member_and_login(
    client: AsyncClient,
    *,
    org_id: str,
    password: str = "Test123!@",
) -> tuple[dict[str, str], dict]:
    email = unique_email("nw5-member")
    username = unique_username("nw5member")
    async with SessionLocal() as db:
        user = User(
            id=uuid.uuid4(),
            email=email,
            username=username,
            password_hash=hash_password(password),
            account_type=AccountType.enterprise,
        )
        db.add(user)
        db.add(
            OrganizationMember(
                id=uuid.uuid4(),
                org_id=uuid.UUID(org_id),
                user_id=user.id,
                role=OrgRole.member,
            )
        )
        await db.commit()

    login = await client.post(
        "/api/v1/auth/login",
        json={"identifier": email, "password": password},
    )
    assert login.status_code == 200
    data = login.json()
    return {"Authorization": f"Bearer {data['access_token']}"}, data["user"]


async def _create_kb(
    client: AsyncClient,
    headers: dict[str, str],
    user: dict,
    *,
    name: str = "NW5 成本库",
) -> dict:
    params = workspace_query(user)
    payload: dict = {"name": name}
    if params.get("workspace") != "personal" and user.get("org_id"):
        payload["org_unit_id"] = None
    resp = await client.post(
        "/api/v1/knowledge-bases",
        headers=headers,
        params=params,
        json=payload,
    )
    assert resp.status_code == 201
    return resp.json()


async def _seed_chat_pair(
    *,
    kb_id: uuid.UUID,
    user_id: uuid.UUID,
    assistant_count: int = 5,
) -> None:
    async with SessionLocal() as db:
        thread = ChatThread(
            id=uuid.uuid4(),
            thread_kind=ThreadKind.knowledge_base,
            kb_id=kb_id,
            user_id=user_id,
            title="NW5 usage seed",
        )
        db.add(thread)
        await db.flush()
        now = datetime.now(UTC)
        for i in range(assistant_count):
            db.add(
                ChatMessage(
                    id=uuid.uuid4(),
                    thread_kind=ThreadKind.knowledge_base,
                    kb_id=kb_id,
                    user_id=user_id,
                    thread_id=thread.id,
                    role=MessageRole.user,
                    content=f"q{i}",
                    created_at=now,
                )
            )
            db.add(
                ChatMessage(
                    id=uuid.uuid4(),
                    thread_kind=ThreadKind.knowledge_base,
                    kb_id=kb_id,
                    user_id=user_id,
                    thread_id=thread.id,
                    role=MessageRole.assistant,
                    content=f"a{i}",
                    created_at=now,
                )
            )
        await db.commit()


@pytest.mark.asyncio
async def test_personal_stats_include_cost_estimate(
    client: AsyncClient,
    register_and_login,
) -> None:
    headers, user = await register_and_login(prefix="nw5-personal")
    kb = await _create_kb(client, headers, user)
    await _seed_chat_pair(
        kb_id=uuid.UUID(kb["id"]),
        user_id=uuid.UUID(user["id"]),
        assistant_count=5,
    )

    resp = await client.get(
        "/api/v1/dashboard/stats",
        headers=headers,
        params=workspace_query(user),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["usage_7d_user_questions"] == 5
    assert body["usage_7d_assistant_replies"] == 5
    assert body["estimated_api_cost_cny_7d"] == estimate_chat_cost_cny_7d(5)
    assert body["cost_estimate_note"] == COST_ESTIMATE_NOTE
    # 无扣费字段
    assert "balance" not in body
    assert "credits" not in body


@pytest.mark.asyncio
async def test_org_admin_sees_cost_member_gets_null(
    client: AsyncClient,
    register_and_login,
) -> None:
    admin_headers, admin_user = await register_and_login(
        prefix="nw5-org-admin",
        account_type="enterprise",
        org_name="NW5 成本公司",
    )
    kb = await _create_kb(client, admin_headers, admin_user)
    await _seed_chat_pair(
        kb_id=uuid.UUID(kb["id"]),
        user_id=uuid.UUID(admin_user["id"]),
        assistant_count=10,
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
    member_body = member_resp.json()

    assert admin_body["usage_7d_assistant_replies"] == 10
    assert member_body["usage_7d_assistant_replies"] == 10
    assert admin_body["estimated_api_cost_cny_7d"] == estimate_chat_cost_cny_7d(10)
    assert admin_body["cost_estimate_note"] == COST_ESTIMATE_NOTE
    assert member_body["estimated_api_cost_cny_7d"] is None
    assert member_body["cost_estimate_note"] is None
