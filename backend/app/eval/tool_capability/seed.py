"""Seed personal workspace data for TOOL P2 real-local cases (eval-only)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import SessionLocal
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.enums import AccountType, DocumentStatus
from app.models.knowledge_base import KnowledgeBase
from app.models.user import User
from app.services.auth.password import hash_password
from app.services.workspace.scope import WorkspaceKind, WorkspaceScope


@dataclass(frozen=True, slots=True)
class SeededWorkspace:
    user_id: uuid.UUID
    kb_ids: tuple[uuid.UUID, ...]
    markers: dict[str, str]


async def _seed_chunk(db: AsyncSession, *, doc: Document, content: str) -> None:
    chunk_id = uuid.uuid4()
    db.add(
        DocumentChunk(
            id=chunk_id,
            document_id=doc.id,
            kb_id=doc.kb_id,
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


async def _seed_doc(
    db: AsyncSession,
    *,
    kb_id: uuid.UUID,
    user_id: uuid.UUID,
    filename: str,
) -> Document:
    doc_id = uuid.uuid4()
    doc = Document(
        id=doc_id,
        kb_id=kb_id,
        filename=filename,
        file_type="pdf",
        file_size=1024,
        storage_path=f"/tmp/{doc_id}.pdf",
        status=DocumentStatus.completed,
        uploaded_by=user_id,
    )
    db.add(doc)
    await db.flush()
    return doc


async def seed_case_workspace(case_id: str) -> SeededWorkspace:
    """Create isolated user + KB fixtures so real tools return contract observations."""
    prefix = case_id.replace("-", "").lower()
    async with SessionLocal() as db:
        user = User(
            email=f"tool-p2-{prefix}-{uuid.uuid4().hex[:8]}@research.local",
            username=f"tp2{uuid.uuid4().hex[:8]}"[:32],
            password_hash=hash_password("ToolP2Research!a"),
            account_type=AccountType.personal,
        )
        db.add(user)
        await db.flush()

        kb_main = KnowledgeBase(
            id=uuid.uuid4(),
            name=f"TOOL P2 {case_id} Main",
            description="benchmark kb",
            owner_user_id=user.id,
        )
        kb_second = KnowledgeBase(
            id=uuid.uuid4(),
            name=f"TOOL P2 {case_id} Secondary",
            description="benchmark kb 2",
            owner_user_id=user.id,
        )
        db.add(kb_main)
        db.add(kb_second)
        await db.flush()

        markers: dict[str, str] = {}
        if case_id == "GQ-131":
            marker = "TOOLP2_GQ131_SEARCH_MARKER"
            markers["filename"] = marker
            await _seed_doc(
                db,
                kb_id=kb_main.id,
                user_id=user.id,
                filename=f"{marker}_guide.pdf",
            )
            await _seed_doc(
                db,
                kb_id=kb_second.id,
                user_id=user.id,
                filename="other-doc.pdf",
            )
        elif case_id == "GQ-132":
            markers["kb"] = kb_main.name
        elif case_id == "GQ-149":
            marker = "TOOLP2_GQ149_CONTENT_MARKER"
            markers["content"] = marker
            doc = await _seed_doc(
                db,
                kb_id=kb_main.id,
                user_id=user.id,
                filename="content-hidden.pdf",
            )
            await _seed_chunk(
                db,
                doc=doc,
                content=f"{marker} search documents by content mode benchmark",
            )
        else:
            raise KeyError(case_id)

        await db.commit()
        return SeededWorkspace(
            user_id=user.id,
            kb_ids=(kb_main.id, kb_second.id),
            markers=markers,
        )


def workspace_for(user_id: uuid.UUID) -> WorkspaceScope:
    return WorkspaceScope(kind=WorkspaceKind.personal, user_id=user_id, org_id=None)
