"""D1 GraphRAG — 知识库图谱查询单元测试。

直接测试 get_kb_graph 函数（依赖真实 DB）。
需 DATABASE_URL 环境变量。
"""

import pytest
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import SessionLocal
from app.services.knowledge_base.graph import get_kb_graph
from app.models.entity import Entity, Relation
from app.models.knowledge_base import KnowledgeBase
from app.models.user import User


@pytest.fixture
async def db() -> AsyncSession:
    session = SessionLocal()
    try:
        yield session
    finally:
        await session.rollback()
        await session.close()


@pytest.fixture
async def test_kb(db: AsyncSession) -> KnowledgeBase:
    user = User(
        id=uuid4(),
        email=f"graph-test-{uuid4().hex[:8]}@example.com",
        username=f"graphtest{uuid4().hex[:4]}",
        password_hash="x",
        account_type="personal",
    )
    db.add(user)
    await db.flush()
    kb = KnowledgeBase(
        id=uuid4(),
        name="测试库-graph",
        owner_user_id=user.id,
    )
    db.add(kb)
    await db.flush()
    return kb


@pytest.mark.asyncio
async def test_graph_normal(db: AsyncSession, test_kb: KnowledgeBase) -> None:
    """有 entities + relations → 返回正确的 nodes/edges"""
    kb_id = test_kb.id
    e1 = Entity(kb_id=kb_id, name="张三", type="person")
    e2 = Entity(kb_id=kb_id, name="智慧城市物联网平台", type="project")
    db.add_all([e1, e2])
    await db.flush()

    rel = Relation(
        kb_id=kb_id, source_id=e1.id, target_id=e2.id,
        relation_type="responsible_for",
    )
    db.add(rel)
    await db.flush()

    result = await get_kb_graph(db, kb_id)

    assert len(result.nodes) == 2
    assert len(result.edges) == 1

    node_ids = {n.id for n in result.nodes}
    assert str(e1.id) in node_ids
    assert str(e2.id) in node_ids

    edge = result.edges[0]
    assert edge.source == str(e1.id)
    assert edge.target == str(e2.id)
    assert edge.label == "responsible_for"


@pytest.mark.asyncio
async def test_graph_empty(db: AsyncSession, test_kb: KnowledgeBase) -> None:
    """空 kb → nodes=[] edges=[]"""
    result = await get_kb_graph(db, test_kb.id)
    assert result.nodes == []
    assert result.edges == []


@pytest.mark.asyncio
async def test_graph_limit(db: AsyncSession, test_kb: KnowledgeBase) -> None:
    """entity > max_nodes 时截断"""
    kb_id = test_kb.id
    # 插入 max_nodes+1 个实体
    for i in range(10):
        db.add(Entity(kb_id=kb_id, name=f"E{i}", type="test"))
    await db.flush()

    result = await get_kb_graph(db, kb_id, max_nodes=5)
    assert len(result.nodes) == 5


@pytest.mark.asyncio
async def test_graph_different_kb(db: AsyncSession) -> None:
    """不同 kb 的实体不互相污染"""
    # 建两个 kb
    user = User(
        id=uuid4(),
        email=f"graph-test-{uuid4().hex[:8]}@example.com",
        username=f"graphtest{uuid4().hex[:4]}",
        password_hash="x",
        account_type="personal",
    )
    db.add(user)
    await db.flush()

    kb_a = KnowledgeBase(id=uuid4(), name="A", owner_user_id=user.id)
    kb_b = KnowledgeBase(id=uuid4(), name="B", owner_user_id=user.id)
    db.add_all([kb_a, kb_b])
    await db.flush()

    ea = Entity(kb_id=kb_a.id, name="实体A", type="test")
    eb = Entity(kb_id=kb_b.id, name="实体B", type="test")
    db.add_all([ea, eb])
    await db.flush()

    # 查 A 不应包含 B 的实体
    result = await get_kb_graph(db, kb_a.id)
    node_names = {n.label for n in result.nodes}
    assert "实体A" in node_names
    assert "实体B" not in node_names
