"""033_add_chunk_content_trgm_index

为 document_chunks.content 添加 GIN trigram 索引，
优化大规模 corpus 下 ILIKE 模式匹配的性能。
（扩展需求：支持 2M+ chunks 级别的 FTS 检索）

Revision ID: add_chunk_content_trgm_index
Revises: d057befd441b
"""
from __future__ import annotations

from alembic import op

revision = "037"
down_revision = "036"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 启用 pg_trgm 扩展（幂等）
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    # GIN trigram 索引：加速 ILIKE / LIKE / similarity 查询
    op.create_index(
        "ix_document_chunks_content_trgm_gin",
        "document_chunks",
        ["content"],
        postgresql_using="gin",
        postgresql_ops={"content": "gin_trgm_ops"},
    )


def downgrade() -> None:
    op.drop_index("ix_document_chunks_content_trgm_gin")
