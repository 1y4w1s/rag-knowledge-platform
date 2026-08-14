"""P2-R13：实体合并显式清理被去重跳过的引用，不残留孤儿行。

`merge_fuzzy_entities` 的去重 UPDATE 会跳过「同 chunk 已有 keep 提及 /
已存在等价 keep 关系」的重复行，随后直接删除冗余实体。若这些被跳过的行
未显式清理，会留下指向已删实体的引用（无 FK 级联时即为孤儿行）。
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from sqlalchemy import text as raw_text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import SessionLocal
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.entity import Entity, EntityMention, Relation
from app.models.enums import DocumentStatus
from app.models.knowledge_base import KnowledgeBase
from app.services.rag.entity_merge import merge_fuzzy_entities


@pytest.fixture
async def db() -> AsyncSession:
    """提供独立 DB session，测试结束后回滚。"""
    session = SessionLocal()
    try:
        yield session
    finally:
        await session.rollback()
        await session.close()


@pytest.fixture
async def test_kb(db: AsyncSession) -> KnowledgeBase:
    """创建测试用知识库（含虚拟用户）。"""
    from app.models.user import User
    user = User(
        id=uuid4(),
        email=f"merge-orphan-{uuid4().hex[:8]}@example.com",
        username=f"merge-orphan-{uuid4().hex[:8]}",
        password_hash="x",
        account_type="personal",
    )
    db.add(user)
    await db.flush()
    kb = KnowledgeBase(
        id=uuid4(),
        name="测试库-fuzzy-merge-orphan",
        owner_user_id=user.id,
    )
    db.add(kb)
    await db.flush()
    return kb


async def _add_chunk(db: AsyncSession, kb_id: UUID) -> DocumentChunk:
    """创建测试用文档 + chunk。"""
    doc = Document(
        kb_id=kb_id,
        filename=f"merge-orphan-{uuid4().hex[:8]}.md",
        file_type="md",
        file_size=16,
        storage_path=f"tests/merge-orphan-{uuid4().hex[:8]}.md",
        status=DocumentStatus.completed,
    )
    db.add(doc)
    await db.flush()
    chunk = DocumentChunk(
        document_id=doc.id,
        kb_id=kb_id,
        chunk_index=0,
        content="测试内容",
    )
    db.add(chunk)
    await db.flush()
    return chunk


@pytest.mark.asyncio
async def test_merge_duplicate_mention_no_orphan(
    db: AsyncSession,
    test_kb: KnowledgeBase,
) -> None:
    """同 chunk 已提及 keep 时，remove 的重复提及被去重，不残留孤儿引用。"""
    kb_id = test_kb.id
    keep_id, remove_id = sorted([uuid4(), uuid4()])
    db.add_all(
        [
            Entity(id=keep_id, kb_id=kb_id, name="华为", type="organization"),
            Entity(
                id=remove_id,
                kb_id=kb_id,
                name="华为技术有限公司",
                type="organization",
            ),
        ]
    )
    await db.flush()
    chunk = await _add_chunk(db, kb_id)
    db.add_all(
        [
            EntityMention(chunk_id=chunk.id, entity_id=keep_id),
            EntityMention(chunk_id=chunk.id, entity_id=remove_id),
        ]
    )
    await db.flush()

    result = await merge_fuzzy_entities(db, kb_id, threshold=0.15, dry_run=False)
    await db.commit()

    assert result["merged"] >= 1
    assert result["removed_entities"] == 1

    remaining_ids = [
        row[0]
        for row in (
            await db.execute(
                raw_text("SELECT id FROM entities WHERE kb_id = :kb_id"),
                {"kb_id": kb_id},
            )
        ).all()
    ]
    assert remove_id not in remaining_ids
    assert keep_id in remaining_ids

    mention_rows = await db.execute(
        raw_text("SELECT entity_id FROM entity_mentions WHERE chunk_id = :chunk_id"),
        {"chunk_id": chunk.id},
    )
    assert [row[0] for row in mention_rows.all()] == [keep_id]

    orphan = await db.execute(
        raw_text(
            "SELECT COUNT(*) FROM entity_mentions WHERE entity_id = :remove_id"
        ),
        {"remove_id": remove_id},
    )
    assert orphan.scalar() == 0


@pytest.mark.asyncio
async def test_merge_duplicate_relation_no_orphan(
    db: AsyncSession,
    test_kb: KnowledgeBase,
) -> None:
    """已存在等价 keep 关系时，remove 的重复关系被去重，不残留孤儿引用。"""
    kb_id = test_kb.id
    keep_id, remove_id = sorted([uuid4(), uuid4()])
    other = Entity(kb_id=kb_id, name="某项目", type="project")
    db.add_all(
        [
            Entity(id=keep_id, kb_id=kb_id, name="华为", type="organization"),
            Entity(
                id=remove_id,
                kb_id=kb_id,
                name="华为技术有限公司",
                type="organization",
            ),
            other,
        ]
    )
    await db.flush()

    db.add_all(
        [
            Relation(
                kb_id=kb_id,
                source_id=keep_id,
                target_id=other.id,
                relation_type="涉及",
            ),
            Relation(
                kb_id=kb_id,
                source_id=remove_id,
                target_id=other.id,
                relation_type="涉及",
            ),
            Relation(
                kb_id=kb_id,
                source_id=other.id,
                target_id=keep_id,
                relation_type="相关",
            ),
            Relation(
                kb_id=kb_id,
                source_id=other.id,
                target_id=remove_id,
                relation_type="相关",
            ),
        ]
    )
    await db.flush()

    result = await merge_fuzzy_entities(db, kb_id, threshold=0.15, dry_run=False)
    await db.commit()

    assert result["merged"] >= 1

    orphan = await db.execute(
        raw_text(
            "SELECT COUNT(*) FROM relations "
            "WHERE source_id = :remove_id OR target_id = :remove_id"
        ),
        {"remove_id": remove_id},
    )
    assert orphan.scalar() == 0

    rows = await db.execute(
        raw_text(
            "SELECT source_id, target_id, relation_type FROM relations "
            "WHERE kb_id = :kb_id ORDER BY relation_type"
        ),
        {"kb_id": kb_id},
    )
    edges = {
        (str(r.source_id), str(r.target_id), r.relation_type)
        for r in rows.all()
    }
    assert edges == {
        (str(keep_id), str(other.id), "涉及"),
        (str(other.id), str(keep_id), "相关"),
    }


@pytest.mark.asyncio
async def test_merge_no_orphan_without_fk_cascade(
    db: AsyncSession,
    test_kb: KnowledgeBase,
) -> None:
    """去掉实体外键级联后，合并仍先清引用再删实体，不留下孤儿行。"""
    kb_id = test_kb.id
    # 复现扫描描述的无级联场景：约束在事务内移除，fixture 结束随回滚还原。
    await db.execute(
        raw_text(
            "ALTER TABLE entity_mentions "
            "DROP CONSTRAINT entity_mentions_entity_id_fkey"
        )
    )
    await db.execute(
        raw_text("ALTER TABLE relations DROP CONSTRAINT relations_source_id_fkey")
    )
    await db.execute(
        raw_text("ALTER TABLE relations DROP CONSTRAINT relations_target_id_fkey")
    )

    keep_id, remove_id = sorted([uuid4(), uuid4()])
    other = Entity(kb_id=kb_id, name="某项目", type="project")
    db.add_all(
        [
            Entity(id=keep_id, kb_id=kb_id, name="华为", type="organization"),
            Entity(
                id=remove_id,
                kb_id=kb_id,
                name="华为技术有限公司",
                type="organization",
            ),
            other,
        ]
    )
    await db.flush()
    chunk = await _add_chunk(db, kb_id)
    db.add_all(
        [
            EntityMention(chunk_id=chunk.id, entity_id=keep_id),
            EntityMention(chunk_id=chunk.id, entity_id=remove_id),
            Relation(
                kb_id=kb_id,
                source_id=keep_id,
                target_id=other.id,
                relation_type="涉及",
            ),
            Relation(
                kb_id=kb_id,
                source_id=remove_id,
                target_id=other.id,
                relation_type="涉及",
            ),
        ]
    )
    await db.flush()

    result = await merge_fuzzy_entities(db, kb_id, threshold=0.15, dry_run=False)

    assert result["merged"] >= 1

    orphan_mentions = await db.execute(
        raw_text(
            "SELECT COUNT(*) FROM entity_mentions WHERE entity_id = :remove_id"
        ),
        {"remove_id": remove_id},
    )
    assert orphan_mentions.scalar() == 0

    orphan_relations = await db.execute(
        raw_text(
            "SELECT COUNT(*) FROM relations "
            "WHERE source_id = :remove_id OR target_id = :remove_id"
        ),
        {"remove_id": remove_id},
    )
    assert orphan_relations.scalar() == 0

    remaining_ids = [
        row[0]
        for row in (
            await db.execute(
                raw_text("SELECT id FROM entities WHERE kb_id = :kb_id"),
                {"kb_id": kb_id},
            )
        ).all()
    ]
    assert remove_id not in remaining_ids
    assert keep_id in remaining_ids

    mention_rows = await db.execute(
        raw_text("SELECT entity_id FROM entity_mentions WHERE chunk_id = :chunk_id"),
        {"chunk_id": chunk.id},
    )
    assert [row[0] for row in mention_rows.all()] == [keep_id]
