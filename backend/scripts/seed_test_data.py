#!/usr/bin/env python3
"""睿阁 Seed 脚本：清空脏数据 + 灌入 demo 数据。

用法（在 Docker 容器内运行）：
    cd /app && python scripts/seed_test_data.py
"""

import asyncio
import uuid
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.document import Document
from app.models.enums import DocumentStatus
from app.models.knowledge_base import KnowledgeBase
from app.models.user import User
from app.services.auth.password import hash_password
from app.services.ingestion.pipeline import process_document_ingestion


SEED_USER_EMAIL = "admin@test.com"
SEED_USER_PASSWORD = "Test1234!"
SEED_USER_USERNAME = "admin"
SEED_USER_NICKNAME = "\u7ba1\u7406\u5458"

FIXTURES = Path("/app/tests/fixtures")
GOLDEN_MD = FIXTURES / "golden_handbook.md"
GOLDEN_DOCX = FIXTURES / "golden_handbook.docx"


async def truncate_all(db):
    tables = [
        "agent_approvals", "agent_steps", "agent_runs",
        "chat_messages", "chat_threads", "document_chunks",
        "documents", "kb_unit_grants", "knowledge_bases",
        "org_unit_members", "org_units",
        "organization_invite_codes", "organization_members",
        "organizations", "audit_logs", "users",
    ]
    for t in tables:
        await db.execute(text(f"TRUNCATE TABLE {t} CASCADE"))
    await db.commit()
    print(f"OK truncated {len(tables)} tables")


async def create_seed_user(db):
    user = User(
        id=uuid.uuid4(),
        email=SEED_USER_EMAIL,
        username=SEED_USER_USERNAME,
        nickname=SEED_USER_NICKNAME,
        password_hash=hash_password(SEED_USER_PASSWORD),
        account_type="personal",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    print(f"OK user: {user.email} / {SEED_USER_PASSWORD}")
    return user


async def create_seed_kb(db, user):
    kb = KnowledgeBase(
        id=uuid.uuid4(),
        name="\u5458\u5de5\u624b\u518c",
        description=(
            "\u5305\u542b\u8003\u52e4\u5236\u5ea6\u4e0e\u85aa\u916c\u798f\u5229"
            "\uff0c\u7528\u4e8e golden_qa \u68c0\u7d22\u6d4b\u8bd5"
        ),
        owner_user_id=user.id,
    )
    db.add(kb)
    await db.commit()
    await db.refresh(kb)
    print(f"OK KB: {kb.name}")
    return kb


async def ingest_document(kb_id, user_id, source, file_type):
    doc_id = uuid.uuid4()
    upload_dir = Path(settings.upload_dir)
    storage_dir = upload_dir / str(kb_id) / str(doc_id)
    storage_dir.mkdir(parents=True, exist_ok=True)
    storage_path = storage_dir / f"{uuid.uuid4()}.{file_type}"
    storage_path.write_bytes(source.read_bytes())

    async with SessionLocal() as db:
        doc = Document(
            id=doc_id, kb_id=kb_id, filename=source.name,
            file_type=file_type, file_size=storage_path.stat().st_size,
            storage_path=str(storage_path), status=DocumentStatus.queued,
            uploaded_by=user_id,
        )
        db.add(doc)
        await db.commit()

    await process_document_ingestion(doc_id)

    async with SessionLocal() as db:
        row = await db.get(Document, doc_id)
        assert row is not None
        assert row.status == DocumentStatus.completed
    print(f"  OK {source.name} ingested")


async def main():
    print("=" * 50)
    async with SessionLocal() as db:
        await truncate_all(db)
    async with SessionLocal() as db:
        user = await create_seed_user(db)
    async with SessionLocal() as db:
        kb = await create_seed_kb(db, user)
    print()
    await ingest_document(kb.id, user.id, GOLDEN_MD, "md")
    if GOLDEN_DOCX.exists():
        await ingest_document(kb.id, user.id, GOLDEN_DOCX, "docx")
    print("=" * 50)
    print("DONE. Login: admin@test.com / Test1234!")


if __name__ == "__main__":
    asyncio.run(main())
