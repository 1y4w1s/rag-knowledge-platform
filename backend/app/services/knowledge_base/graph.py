"""D1 GraphRAG — 知识库图谱查询服务。"""

import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entity import Entity, Relation
from app.schemas.knowledge_base import (
    GraphEdge,
    GraphNode,
    KnowledgeGraphResponse,
)

logger = logging.getLogger(__name__)

MAX_NODES = 500


async def get_kb_graph(
    db: AsyncSession,
    kb_id: UUID,
    *,
    max_nodes: int = MAX_NODES,
) -> KnowledgeGraphResponse:
    """查询指定知识库的实体关系图数据。

    限制 max_nodes 个节点，超出时按 id 顺序截断前 max_nodes 个。
    """
    # 1. 查 entities（限制 max_nodes）
    entities = await db.execute(
        select(Entity)
        .where(Entity.kb_id == kb_id)
        .limit(max_nodes)
        .order_by(Entity.id)
    )
    entity_rows = entities.scalars().all()

    entity_ids = {e.id for e in entity_rows}

    # 2. 查 relations（仅含两端均在 entity_ids 内的边，防悬空边）
    relations = await db.execute(
        select(Relation)
        .where(Relation.kb_id == kb_id)
        .where(Relation.source_id.in_(entity_ids))
        .where(Relation.target_id.in_(entity_ids))
    )
    relation_rows = relations.scalars().all()

    return KnowledgeGraphResponse(
        nodes=[
            GraphNode(id=str(e.id), label=e.name, type=e.type, title=e.name)
            for e in entity_rows
        ],
        edges=[
            GraphEdge(
                source=str(r.source_id),
                target=str(r.target_id),
                label=r.relation_type,
                type=r.relation_type,
            )
            for r in relation_rows
        ],
    )
