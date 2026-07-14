"""EW-A2：audit_logs 表 + write_audit_log helper 测试。"""

import uuid

import pytest
from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.audit_log import AuditLog
from app.models.enums import AccountType
from app.models.user import User
from app.services.audit.log import get_audit_log, write_audit_log
from app.services.auth.password import hash_password


@pytest.mark.asyncio
async def test_write_audit_log_persisted_and_queryable() -> None:
    kb_id = uuid.uuid4()
    doc_id = uuid.uuid4()
    async with SessionLocal() as db:
        user = User(
            id=uuid.uuid4(),
            email=f"audit-{uuid.uuid4().hex[:8]}@example.com",
            username=f"audit{uuid.uuid4().hex[:8]}"[:32],
            password_hash=hash_password("Test123!@"),
            account_type=AccountType.personal,
        )
        db.add(user)
        await db.commit()

        async with SessionLocal() as write_db:
            entry = await write_audit_log(
                write_db,
                action="document.delete",
                actor_user_id=user.id,
                resource_type="document",
                resource_id=doc_id,
                kb_id=kb_id,
                metadata={"filename": "report.pdf"},
                ip="192.168.1.10",
            )
            log_id = entry.id
            await write_db.commit()

        async with SessionLocal() as read_db:
            fetched = await get_audit_log(read_db, log_id)
            assert fetched is not None
            assert fetched.action == "document.delete"
            assert fetched.actor_user_id == user.id
            assert fetched.resource_type == "document"
            assert fetched.resource_id == doc_id
            assert fetched.kb_id == kb_id
            assert fetched.details == {"filename": "report.pdf"}
            assert fetched.ip == "192.168.1.10"
            assert fetched.created_at is not None


@pytest.mark.asyncio
async def test_write_audit_log_allows_null_actor_for_failed_login() -> None:
    async with SessionLocal() as db:
        entry = await write_audit_log(
            db,
            action="auth.login_failed",
            metadata={"identifier": "unknown@example.com"},
            ip="10.0.0.1",
        )
        log_id = entry.id
        await db.commit()

    async with SessionLocal() as db:
        result = await db.execute(select(AuditLog).where(AuditLog.id == log_id))
        row = result.scalar_one()
        assert row.actor_user_id is None
        assert row.action == "auth.login_failed"
        assert row.details == {"identifier": "unknown@example.com"}
