"""共享 fixture：OrgScope 隔离测试用的 OrgIsolationFixture 构建器 + org_iso fixture。"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import SessionLocal
from app.core.deps import CurrentUser
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.enums import (
    AccountType,
    DocumentStatus,
    OrgRole,
    UnitRole,
)
from app.models.knowledge_base import KnowledgeBase
from app.models.organization import Organization
from app.models.organization_member import OrganizationMember
from app.models.user import User
from app.services.auth.password import hash_password
from app.services.org.units import add_unit_member, create_org_root_unit, create_org_unit
from tests.conftest import unique_email, unique_username


@dataclass
class OrgIsolationFixture:
    org_id: uuid.UUID
    root_id: uuid.UUID
    rd_id: uuid.UUID
    mkt_id: uuid.UUID
    rd_child_id: uuid.UUID
    public_kb_id: uuid.UUID
    rd_kb_id: uuid.UUID
    mkt_kb_id: uuid.UUID
    rd_child_kb_id: uuid.UUID
    owner: CurrentUser
    rd_member: CurrentUser
    mkt_member: CurrentUser
    unassigned_member: CurrentUser
    rd_admin: CurrentUser


async def _login_user(client: AsyncClient, email: str, password: str) -> tuple[dict[str, str], dict]:
    login = await client.post(
        "/api/v1/auth/login",
        json={"identifier": email, "password": password},
    )
    assert login.status_code == 200
    data = login.json()
    return {"Authorization": f"Bearer {data['access_token']}"}, data["user"]


async def _build_org_isolation_fixture(db: AsyncSession) -> OrgIsolationFixture:
    password = "password123"
    org = Organization(id=uuid.uuid4(), name="隔离测试公司")
    db.add(org)
    await db.flush()

    root = await create_org_root_unit(db, org_id=org.id, name="总部")
    rd = await create_org_unit(db, org_id=org.id, name="研发部", parent=root)
    mkt = await create_org_unit(db, org_id=org.id, name="市场部", parent=root)
    rd_child = await create_org_unit(db, org_id=org.id, name="后端组", parent=rd)

    async def _user(prefix: str) -> tuple[User, str]:
        email = unique_email(prefix)
        user = User(
            id=uuid.uuid4(),
            email=email,
            username=unique_username(prefix),
            password_hash=hash_password(password),
            account_type=AccountType.enterprise,
        )
        db.add(user)
        return user, email

    owner_user, _owner_email = await _user("org-owner")
    rd_user, _ = await _user("rd-member")
    mkt_user, _ = await _user("mkt-member")
    unassigned_user, _ = await _user("unassigned")
    rd_admin_user, _ = await _user("rd-admin")

    db.add(
        OrganizationMember(
            org_id=org.id,
            user_id=owner_user.id,
            role=OrgRole.admin,
            is_owner=True,
        )
    )
    for user, role in (
        (rd_user, OrgRole.member),
        (mkt_user, OrgRole.member),
        (unassigned_user, OrgRole.member),
        (rd_admin_user, OrgRole.member),
    ):
        db.add(
            OrganizationMember(
                org_id=org.id,
                user_id=user.id,
                role=role,
                is_owner=False,
            )
        )

    await add_unit_member(
        db,
        org_unit_id=root.id,
        user_id=owner_user.id,
        role=UnitRole.unit_admin,
        is_primary=True,
    )
    await add_unit_member(
        db,
        org_unit_id=rd.id,
        user_id=rd_user.id,
        role=UnitRole.unit_member,
        is_primary=True,
    )
    await add_unit_member(
        db,
        org_unit_id=mkt.id,
        user_id=mkt_user.id,
        role=UnitRole.unit_member,
        is_primary=True,
    )
    await add_unit_member(
        db,
        org_unit_id=rd.id,
        user_id=rd_admin_user.id,
        role=UnitRole.unit_admin,
        is_primary=True,
    )

    def _kb(name: str, unit_id: uuid.UUID | None) -> KnowledgeBase:
        kb = KnowledgeBase(
            id=uuid.uuid4(),
            name=name,
            owner_org_id=org.id,
            owner_user_id=None,
            org_unit_id=unit_id,
        )
        db.add(kb)
        return kb

    public_kb = _kb("公司公共库", None)
    rd_kb = _kb("研发库", rd.id)
    mkt_kb = _kb("市场机密库", mkt.id)
    rd_child_kb = _kb("后端组库", rd_child.id)

    await db.commit()

    def _current(user: User, *, org_role: OrgRole, is_owner: bool = False) -> CurrentUser:
        return CurrentUser(
            id=user.id,
            email=user.email,
            username=user.username,
            nickname=user.nickname,
            account_type=AccountType.enterprise,
            org_id=org.id,
            org_role=org_role,
            is_owner=is_owner,
        )

    return OrgIsolationFixture(
        org_id=org.id,
        root_id=root.id,
        rd_id=rd.id,
        mkt_id=mkt.id,
        rd_child_id=rd_child.id,
        public_kb_id=public_kb.id,
        rd_kb_id=rd_kb.id,
        mkt_kb_id=mkt_kb.id,
        rd_child_kb_id=rd_child_kb.id,
        owner=_current(owner_user, org_role=OrgRole.admin, is_owner=True),
        rd_member=_current(rd_user, org_role=OrgRole.member),
        mkt_member=_current(mkt_user, org_role=OrgRole.member),
        unassigned_member=_current(unassigned_user, org_role=OrgRole.member),
        rd_admin=_current(rd_admin_user, org_role=OrgRole.member),
    )


@pytest.fixture
async def org_iso() -> OrgIsolationFixture:
    async with SessionLocal() as db:
        fixture = await _build_org_isolation_fixture(db)
    return fixture


async def _seed_kb_documents(
    db: AsyncSession,
    *,
    kb_id: uuid.UUID,
    count: int,
    uploaded_by: uuid.UUID,
    status: DocumentStatus = DocumentStatus.completed,
    chunk_count: int = 1,
) -> None:
    for index in range(count):
        doc_id = uuid.uuid4()
        db.add(
            Document(
                id=doc_id,
                kb_id=kb_id,
                filename=f"doc-{index}.txt",
                file_type="txt",
                file_size=12,
                storage_path=f"/tmp/{kb_id}/{doc_id}.txt",
                status=status,
                chunk_count=chunk_count,
                uploaded_by=uploaded_by,
            )
        )


async def _seed_kb_document_with_chunk(
    db: AsyncSession,
    *,
    kb_id: uuid.UUID,
    uploaded_by: uuid.UUID,
    filename: str,
    content: str,
) -> None:
    from sqlalchemy import text

    doc_id = uuid.uuid4()
    chunk_id = uuid.uuid4()
    db.add(
        Document(
            id=doc_id,
            kb_id=kb_id,
            filename=filename,
            file_type="txt",
            file_size=12,
            storage_path=f"/tmp/{kb_id}/{doc_id}.txt",
            status=DocumentStatus.completed,
            chunk_count=1,
            uploaded_by=uploaded_by,
        )
    )
    db.add(
        DocumentChunk(
            id=chunk_id,
            document_id=doc_id,
            kb_id=kb_id,
            chunk_index=0,
            content=content,
            embedding=None,
        )
    )
    await db.flush()
    await db.execute(
        text(
            "UPDATE document_chunks SET content_tsv = to_tsvector('simple', :src) "
            "WHERE id = :chunk_id"
        ),
        {"src": content, "chunk_id": chunk_id},
    )


async def _seed_kb_document_with_ids(
    db: AsyncSession,
    *,
    kb_id: uuid.UUID,
    uploaded_by: uuid.UUID,
    filename: str,
    content: str,
) -> tuple[uuid.UUID, uuid.UUID]:
    from sqlalchemy import text

    doc_id = uuid.uuid4()
    chunk_id = uuid.uuid4()
    db.add(
        Document(
            id=doc_id,
            kb_id=kb_id,
            filename=filename,
            file_type="txt",
            file_size=len(content),
            storage_path=f"/tmp/{kb_id}/{doc_id}.txt",
            status=DocumentStatus.completed,
            chunk_count=1,
            uploaded_by=uploaded_by,
        )
    )
    db.add(
        DocumentChunk(
            id=chunk_id,
            document_id=doc_id,
            kb_id=kb_id,
            chunk_index=0,
            content=content,
            embedding=None,
        )
    )
    await db.flush()
    await db.execute(
        text(
            "UPDATE document_chunks SET content_tsv = to_tsvector('simple', :src) "
            "WHERE id = :chunk_id"
        ),
        {"src": content, "chunk_id": chunk_id},
    )
    return doc_id, chunk_id
