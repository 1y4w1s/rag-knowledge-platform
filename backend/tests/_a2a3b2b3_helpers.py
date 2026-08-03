"""序 1.5 验收测试共享辅助（A2/A3 + B2/B3 两个测试文件共用）。"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.agent_approval import AgentApproval
from app.models.agent_run import AgentRun
from app.models.audit_log import AuditLog
from app.models.chat_thread import ChatThread
from app.models.enums import (
    AgentRunMode,
    AgentRunStatus,
    ApprovalKind,
    ApprovalStatus,
    ThreadKind,
    ThreadStatus,
)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def login(client: AsyncClient, user) -> dict[str, str]:
    login = await client.post(
        "/api/v1/auth/login",
        json={"identifier": user.email, "password": "Test123!@"},
    )
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


async def insert_approval(
    *,
    kb_id: uuid.UUID,
    user_id: uuid.UUID,
    status: ApprovalStatus = ApprovalStatus.pending,
    created_at: datetime | None = None,
    filename: str = "faq-draft.md",
) -> uuid.UUID:
    """直插 approval（含父表 thread/run FK），返回 approval_id。"""
    approval_id = uuid.uuid4()
    thread_id = uuid.uuid4()
    run_id = uuid.uuid4()
    async with SessionLocal() as db:
        db.add(
            ChatThread(
                id=thread_id,
                thread_kind=ThreadKind.workspace,
                user_id=user_id,
                kb_id=kb_id,
                status=ThreadStatus.active,
            )
        )
        await db.flush()
        db.add(
            AgentRun(
                id=run_id,
                thread_id=thread_id,
                user_id=user_id,
                mode=AgentRunMode.edit,
                status=AgentRunStatus.completed,
            )
        )
        await db.flush()
        approval = AgentApproval(
            id=approval_id,
            run_id=run_id,
            thread_id=thread_id,
            user_id=user_id,
            kind=ApprovalKind.adopt_faq,
            status=status,
            kb_id=kb_id,
            filename=filename,
            payload_json={
                "title": "年假制度 FAQ",
                "filename": filename,
                "markdown": "# FAQ\n\n内容",
                "source_chunk_ids": [],
            },
        )
        if created_at is not None:
            approval.created_at = created_at
        db.add(approval)
        await db.commit()
    return approval_id


async def get_approval(approval_id: uuid.UUID) -> AgentApproval | None:
    async with SessionLocal() as db:
        return await db.get(AgentApproval, approval_id)


async def audit_count(action: str, resource_id: uuid.UUID) -> int:
    async with SessionLocal() as db:
        return int(
            await db.scalar(
                select(func.count())
                .select_from(AuditLog)
                .where(
                    AuditLog.action == action,
                    AuditLog.resource_id == resource_id,
                )
            )
            or 0
        )


@pytest.fixture
def upload_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    return tmp_path


def _age_minutes(created_at: datetime) -> float:
    return (utcnow() - created_at).total_seconds() / 60


__all__ = [
    "audit_count",
    "get_approval",
    "insert_approval",
    "login",
    "upload_dir",
    "utcnow",
]
