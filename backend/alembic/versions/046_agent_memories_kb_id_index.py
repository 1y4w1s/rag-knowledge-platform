"""046 — 模型↔迁移对齐：agent_memories.kb_id 索引 + document_chunks.embedding HNSW 索引

Revision ID: 046_agent_memories_kb_id_index
Revises: 045_kb_owner_restrict
Create Date: 2026-08-03

背景（D gate：`alembic check` 漂移）：
  1. `AgentMemory.kb_id` 模型声明 `index=True`（即 ix_agent_memories_kb_id），
     但 041 建表迁移未建该索引 → fresh 库缺索引，autogenerate 报 add_index。
  2. `document_chunks.embedding` 的 HNSW 索引由 005 迁移以原生 SQL 建立，
     但模型未声明（此前仅声明 embedding_en 的 HNSW）→ autogenerate 报 remove_index。
     检索（vector_recall）对中文 512 维 `embedding` 做 cosine 召回依赖该索引，
     故方向为「补进模型声明」而非删索引；本迁移以 IF NOT EXISTS 收敛存量库。

安全约束：
  - 索引类 DDL 一律 CREATE INDEX CONCURRENTLY（autocommit_block，不占长事务锁表）；
  - 不含任何数据改写 / DROP TABLE / DROP INDEX 破坏性操作；
  - 全部 IF NOT EXISTS，fresh 与存量库均可幂等执行。
"""

from __future__ import annotations

from alembic import op

revision: str = "046_agent_memories_kb_id_index"
down_revision: str | None = "045_kb_owner_restrict"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # 1. agent_memories.kb_id 索引（模型声明 index=True，041 建表遗漏）
    with op.get_context().autocommit_block():
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_agent_memories_kb_id "
            "ON agent_memories (kb_id)"
        )

    # 2. document_chunks.embedding HNSW 索引（005 已建；部分存量库被手工删过，收敛补齐）
    with op.get_context().autocommit_block():
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_document_chunks_embedding_hnsw "
            "ON document_chunks USING hnsw (embedding vector_cosine_ops)"
        )


def downgrade() -> None:
    # 仅撤销本迁移补建的 agent_memories.kb_id 索引；
    # embedding HNSW 由 005 负责，本迁移在 fresh 库并未新建，不回滚删除。
    with op.get_context().autocommit_block():
        op.execute(
            "DROP INDEX CONCURRENTLY IF EXISTS ix_agent_memories_kb_id"
        )
