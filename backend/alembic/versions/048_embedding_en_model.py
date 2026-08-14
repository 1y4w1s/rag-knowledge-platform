"""048 - document_chunks.embedding_en_model 列（P1-11 方案 B M1）

新增 embedding_en_model varchar(64) nullable 列，用于追踪 EN 嵌入模型
（bge-small-en-v1.5），为后续 EN 模型过滤/换模型提供 schema 基线。

Safety constraints:
  - Only nullable add_column, no index, no data rewrite;
  - Downgrade only drops the column, safe for rollback.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision: str = "048"
down_revision: str | None = "047"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "document_chunks",
        sa.Column("embedding_en_model", sa.String(64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("document_chunks", "embedding_en_model")
