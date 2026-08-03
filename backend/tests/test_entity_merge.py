"""D1 GraphRAG — 实体 fuzzy 合并单元测试。

直接测试 merge_fuzzy_entities 函数（依赖真实 DB + pg_trgm）。
所有测试标记 pytest.mark.asyncio，需 DATABASE_URL 环境变量。
"""

import pytest
from uuid import uuid4

from sqlalchemy import text as raw_text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import SessionLocal
from app.services.rag.entity_merge import merge_fuzzy_entities
from app.models.entity import Entity
from app.models.knowledge_base import KnowledgeBase


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
        email=f"merge-test-{uuid4().hex[:8]}@example.com",
        username=f"merge-test-{uuid4().hex[:8]}",
        password_hash="x",
        account_type="personal",
    )
    db.add(user)
    await db.flush()
    kb = KnowledgeBase(
        id=uuid4(),
        name="测试库-fuzzy-merge",
        owner_user_id=user.id,
    )
    db.add(kb)
    await db.flush()
    return kb


@pytest.mark.asyncio
async def test_merge_basic(db: AsyncSession, test_kb: KnowledgeBase) -> None:
    """同 kb + 同 type "华为" vs "华为技术有限公司" → 合并"""
    kb_id = test_kb.id
    e1 = Entity(kb_id=kb_id, name="华为", type="organization")
    e2 = Entity(kb_id=kb_id, name="华为技术有限公司", type="organization")
    db.add_all([e1, e2])
    await db.flush()

    result = await merge_fuzzy_entities(db, kb_id, threshold=0.15, dry_run=False)
    await db.commit()

    assert result["merged"] >= 1
    assert result["dry_run"] is False
    assert result["removed_entities"] == 1

    # 验证只剩 1 个实体
    remaining = await db.execute(
        raw_text("SELECT COUNT(*) FROM entities WHERE kb_id = :kb_id"),
        {"kb_id": kb_id},
    )
    assert remaining.scalar() == 1

    # 验证审计事件
    audit = await db.execute(
        raw_text("SELECT action, metadata FROM audit_logs WHERE action = 'entity_merge_fuzzy'"),
    )
    row = audit.fetchone()
    assert row is not None
    assert row.action == "entity_merge_fuzzy"
    assert row.metadata["merged"] >= 1


@pytest.mark.asyncio
async def test_merge_no_duplicates(db: AsyncSession, test_kb: KnowledgeBase) -> None:
    """无近似重复 → merged=0"""
    kb_id = test_kb.id
    e1 = Entity(kb_id=kb_id, name="张三", type="person")
    e2 = Entity(kb_id=kb_id, name="李四", type="person")
    db.add_all([e1, e2])
    await db.flush()

    result = await merge_fuzzy_entities(db, kb_id, dry_run=False)
    await db.commit()

    assert result["merged"] == 0
    assert result["candidates"] == 0


@pytest.mark.asyncio
async def test_merge_different_type(db: AsyncSession, test_kb: KnowledgeBase) -> None:
    """同名但不同 type → 不合并"""
    kb_id = test_kb.id
    e1 = Entity(kb_id=kb_id, name="华为", type="organization")
    e2 = Entity(kb_id=kb_id, name="华为", type="project")
    db.add_all([e1, e2])
    await db.flush()

    result = await merge_fuzzy_entities(db, kb_id, threshold=0.15, dry_run=False)
    await db.commit()

    assert result["merged"] == 0


@pytest.mark.asyncio
async def test_merge_different_kb(db: AsyncSession, test_kb: KnowledgeBase) -> None:
    """不同 kb_id → 不跨库合并"""
    from app.models.user import User
    kb_a = test_kb.id
    kb_b = uuid4()
    # kb_b 也需要是真实的知识库
    user2 = User(
        id=uuid4(),
        email=f"merge-test-{uuid4().hex[:8]}@example.com",
        username=f"merge-test-{uuid4().hex[:8]}",
        password_hash="x",
        account_type="personal",
    )
    db.add(user2)
    await db.flush()
    kb2 = KnowledgeBase(id=kb_b, name="另一个库", owner_user_id=user2.id)
    db.add(kb2)
    await db.flush()

    e1 = Entity(kb_id=kb_a, name="华为", type="organization")
    e2 = Entity(kb_id=kb_b, name="华为技术有限公司", type="organization")
    db.add_all([e1, e2])
    await db.flush()

    # 只扫描 kb_a
    result = await merge_fuzzy_entities(db, kb_a, threshold=0.5, dry_run=False)
    await db.commit()

    assert result["merged"] == 0
    assert result["candidates"] == 0


@pytest.mark.asyncio
async def test_merge_idempotent(db: AsyncSession, test_kb: KnowledgeBase) -> None:
    """两次 dry_run=False 执行 → 第二次 merged=0"""
    kb_id = test_kb.id
    e1 = Entity(kb_id=kb_id, name="华为", type="organization")
    e2 = Entity(kb_id=kb_id, name="华为技术有限公司", type="organization")
    db.add_all([e1, e2])
    await db.flush()

    # 第一次执行
    r1 = await merge_fuzzy_entities(db, kb_id, threshold=0.15, dry_run=False)
    await db.commit()
    assert r1["merged"] >= 1

    # 第二次执行
    r2 = await merge_fuzzy_entities(db, kb_id, threshold=0.15, dry_run=False)
    await db.commit()
    assert r2["merged"] == 0  # 幂等


@pytest.mark.asyncio
async def test_merge_dry_run(db: AsyncSession, test_kb: KnowledgeBase) -> None:
    """dry_run=True → 不写库、不写审计"""
    kb_id = test_kb.id
    e1 = Entity(kb_id=kb_id, name="华为", type="organization")
    e2 = Entity(kb_id=kb_id, name="华为技术有限公司", type="organization")
    db.add_all([e1, e2])
    await db.flush()

    result = await merge_fuzzy_entities(db, kb_id, threshold=0.15, dry_run=True)

    assert result["dry_run"] is True
    assert result["merged"] >= 1
    assert result["candidates"] >= 1

    # 验证没写审计（限定本 kb）
    audit = await db.execute(
        raw_text("SELECT COUNT(*) FROM audit_logs WHERE action = 'entity_merge_fuzzy' AND kb_id = :kb_id"),
        {"kb_id": kb_id},
    )
    assert audit.scalar() == 0

    # 验证实体没被删
    remaining = await db.execute(
        raw_text("SELECT COUNT(*) FROM entities WHERE kb_id = :kb_id"),
        {"kb_id": kb_id},
    )
    assert remaining.scalar() == 2


@pytest.mark.asyncio
async def test_merge_chain_guard(db: AsyncSession, test_kb: KnowledgeBase) -> None:
    """链式 A≈B≈C → 不产生悬空 FK"""
    kb_id = test_kb.id
    # 用相同前缀+后缀触发 trigram 匹配
    e1 = Entity(kb_id=kb_id, name="张三", type="person")
    e2 = Entity(kb_id=kb_id, name="张三（项目经理）", type="person")
    e3 = Entity(kb_id=kb_id, name="张三（项目）", type="person")
    db.add_all([e1, e2, e3])
    await db.flush()

    await merge_fuzzy_entities(db, kb_id, threshold=0.3, dry_run=False)
    await db.commit()

    # 至少应当合并掉 1 个，且不抛 FK 异常
    remaining = await db.execute(
        raw_text("SELECT COUNT(*) FROM entities WHERE kb_id = :kb_id"),
        {"kb_id": kb_id},
    )
    remaining_count = remaining.scalar()
    assert remaining_count < 3  # 至少合并掉一个
    assert remaining_count >= 1  # 至少剩一个
