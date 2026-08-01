"""NW-10 / R6-4：消息级反馈 API（assistant 闸 · audit · Admin 聚合）。"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.core.database import SessionLocal
from app.models.audit_log import AuditLog
from app.models.chat_feedback import ChatFeedback
from app.models.chat_message import ChatMessage
from app.models.chat_thread import ChatThread
from app.models.enums import AccountType, MessageRole, OrgRole, ThreadKind
from app.models.organization_member import OrganizationMember
from app.models.user import User
from app.services.auth.password import hash_password
from tests.conftest import create_test_kb, unique_email, unique_username


async def _count_audit(action: str) -> int:
    async with SessionLocal() as db:
        result = await db.execute(
            select(func.count()).select_from(AuditLog).where(AuditLog.action == action)
        )
        return int(result.scalar_one())


async def _insert_assistant_message(
    *,
    user_id: uuid.UUID,
    kb_id: uuid.UUID,
    content: str = "助手回答",
    role: MessageRole = MessageRole.assistant,
) -> uuid.UUID:
    msg_id = uuid.uuid4()
    async with SessionLocal() as db:
        thread = ChatThread(
            id=uuid.uuid4(),
            thread_kind=ThreadKind.knowledge_base,
            kb_id=kb_id,
            user_id=user_id,
            title="NW10 feedback thread",
        )
        db.add(thread)
        await db.flush()
        db.add(
            ChatMessage(
                id=msg_id,
                thread_kind=ThreadKind.knowledge_base,
                kb_id=kb_id,
                user_id=user_id,
                thread_id=thread.id,
                role=role,
                content=content,
                citations=None,
                created_at=datetime.now(timezone.utc),
            )
        )
        await db.commit()
    return msg_id


async def _create_org_member_and_login(
    client: AsyncClient,
    *,
    org_id: str,
    password: str = "Test123!@",
) -> tuple[dict[str, str], dict]:
    email = unique_email("nw10-member")
    username = unique_username("nw10member")
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


@pytest.mark.asyncio
async def test_feedback_assistant_upsert_writes_audit(
    client: AsyncClient,
    register_and_login,
) -> None:
    headers, user = await register_and_login(prefix="nw10-fb")
    kb = await create_test_kb(client, headers, user, name="NW10 反馈库")
    msg_id = await _insert_assistant_message(
        user_id=uuid.UUID(user["id"]),
        kb_id=uuid.UUID(kb["id"]),
    )
    before = await _count_audit("chat.feedback_upserted")

    resp = await client.post(
        "/api/v1/feedback",
        headers=headers,
        json={"message_id": str(msg_id), "rating": 1},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["rating"] == 1
    assert body["message_id"] == str(msg_id)

    after = await _count_audit("chat.feedback_upserted")
    assert after == before + 1

    again = await client.post(
        "/api/v1/feedback",
        headers=headers,
        json={"message_id": str(msg_id), "rating": 0},
    )
    assert again.status_code == 201
    assert again.json()["id"] == body["id"]
    assert again.json()["rating"] == 0
    assert await _count_audit("chat.feedback_upserted") == before + 2


@pytest.mark.asyncio
async def test_feedback_rejects_user_role_message(
    client: AsyncClient,
    register_and_login,
) -> None:
    headers, user = await register_and_login(prefix="nw10-user-msg")
    kb = await create_test_kb(client, headers, user, name="NW10 user 消息库")
    msg_id = await _insert_assistant_message(
        user_id=uuid.UUID(user["id"]),
        kb_id=uuid.UUID(kb["id"]),
        content="用户问题",
        role=MessageRole.user,
    )
    resp = await client.post(
        "/api/v1/feedback",
        headers=headers,
        json={"message_id": str(msg_id), "rating": 1},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_feedback_stats_member_only_self_admin_kb_aggregate(
    client: AsyncClient,
    register_and_login,
) -> None:
    admin_headers, admin = await register_and_login(
        prefix="nw10-adm",
        account_type="enterprise",
        org_name="NW10 反馈公司",
    )
    kb = await create_test_kb(client, admin_headers, admin, name="NW10 聚合库")
    kb_id = uuid.UUID(kb["id"])

    member_headers, member = await _create_org_member_and_login(
        client, org_id=admin["org_id"]
    )

    admin_msg = await _insert_assistant_message(
        user_id=uuid.UUID(admin["id"]), kb_id=kb_id, content="admin 答"
    )
    member_msg = await _insert_assistant_message(
        user_id=uuid.UUID(member["id"]), kb_id=kb_id, content="member 答"
    )

    assert (
        await client.post(
            "/api/v1/feedback",
            headers=admin_headers,
            json={"message_id": str(admin_msg), "rating": 1},
        )
    ).status_code == 201
    assert (
        await client.post(
            "/api/v1/feedback",
            headers=member_headers,
            json={"message_id": str(member_msg), "rating": 0},
        )
    ).status_code == 201

    member_stats = await client.get(
        "/api/v1/feedback/stats",
        headers=member_headers,
        params={"kb_id": str(kb_id)},
    )
    assert member_stats.status_code == 200
    assert member_stats.json()["total"] == 1
    assert member_stats.json()["thumbs_down"] == 1

    admin_stats = await client.get(
        "/api/v1/feedback/stats",
        headers=admin_headers,
        params={"kb_id": str(kb_id)},
    )
    assert admin_stats.status_code == 200
    assert admin_stats.json()["total"] == 2
    assert admin_stats.json()["thumbs_up"] == 1
    assert admin_stats.json()["thumbs_down"] == 1


@pytest.mark.asyncio
async def test_feedback_get_and_delete(
    client: AsyncClient,
    register_and_login,
) -> None:
    headers, user = await register_and_login(prefix="nw10-del")
    kb = await create_test_kb(client, headers, user, name="NW10 撤回库")
    msg_id = await _insert_assistant_message(
        user_id=uuid.UUID(user["id"]),
        kb_id=uuid.UUID(kb["id"]),
    )
    created = await client.post(
        "/api/v1/feedback",
        headers=headers,
        json={"message_id": str(msg_id), "rating": 1},
    )
    assert created.status_code == 201
    fb_id = created.json()["id"]

    got = await client.get(f"/api/v1/feedback/messages/{msg_id}", headers=headers)
    assert got.status_code == 200
    assert got.json()["id"] == fb_id

    deleted = await client.delete(f"/api/v1/feedback/{fb_id}", headers=headers)
    assert deleted.status_code == 204

    async with SessionLocal() as db:
        row = await db.get(ChatFeedback, uuid.UUID(fb_id))
        assert row is None
