"""035 — document_chunks.embedding_en 列（英文嵌入 384 维）

新增 embedding_en vector(384) 列，用于存储英文文档的嵌入向量。
配合 bge-small-en-v1.5 模型使用，支持多语言 RAG。

改动：
1. document_chunks 加 embedding_en vector(384) 列
2. 加 HNSW 索引 ix_document_chunks_embedding_en_hnsw
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

revision: str = "035"
down_revision: Union[str, None] = "034"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "document_chunks",
        sa.Column("embedding_en", Vector(384), nullable=True),
    )
    op.execute(
        "CREATE INDEX ix_document_chunks_embedding_en_hnsw ON document_chunks "
        "USING hnsw (embedding_en vector_cosine_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_document_chunks_embedding_en_hnsw")
    op.drop_column("document_chunks", "embedding_en")
