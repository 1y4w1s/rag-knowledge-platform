"""050 - agent_memories 分层字段 + (user_id, status, tier) 索引（T6 W1）。

新增 tier / importance_score / summary 三列，为工作记忆与长期记忆分层
提供数据层基础；存储行由 server_default 回填，行为等价旧单层长期记忆。
Safety constraints:
  - add_column 全部带 server_default，存储行由 DDL 默认值回填，无
    op.execute 数据改写；
  - 索引 DDL 使用 CREATE INDEX CONCURRENTLY + autocommit_block；
  - downgrade 对称：先 DROP INDEX CONCURRENTLY，再 drop_column。
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "050_agent_memories_tiering"
down_revision: str | None = "049_agent_memories_governance"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "agent_memories",
        sa.Column(
            "tier",
            sa.String(16),
            nullable=False,
            server_default="long_term",
        ),
    )
    op.add_column(
        "agent_memories",
        sa.Column(
            "importance_score",
            sa.Float(),
            nullable=False,
            server_default="0.5",
        ),
    )
    op.add_column(
        "agent_memories",
        sa.Column("summary", postgresql.JSONB(), nullable=True),
    )

    with op.get_context().autocommit_block():
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS "
            "ix_agent_memories_user_status_tier "
            "ON agent_memories (user_id, status, tier)"
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(
            "DROP INDEX CONCURRENTLY IF EXISTS "
            "ix_agent_memories_user_status_tier"
        )
    op.drop_column("agent_memories", "summary")
    op.drop_column("agent_memories", "importance_score")
    op.drop_column("agent_memories", "tier")
