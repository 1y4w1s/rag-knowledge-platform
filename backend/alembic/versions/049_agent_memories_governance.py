"""049 - agent_memories 治理列 + (user_id, status) 索引（T5 W1）

新增 source / last_observed_at / status / suppress_until / churn_count 五列，
为 T5 记忆治理（来源优先级、错误记忆发现、churn 风险）提供数据层基础。

Safety constraints:
  - add_column 全部带 server_default，存量行由 DDL 默认值回填，无 op.execute 数据改写；
  - 索引 DDL 使用 CREATE INDEX CONCURRENTLY + autocommit_block（与 046 先例一致）；
  - downgrade 对称：先 DROP INDEX CONCURRENTLY，再 drop_column。
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision: str = "049_agent_memories_governance"
down_revision: str | None = "048"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "agent_memories",
        sa.Column(
            "source",
            sa.String(16),
            nullable=False,
            server_default="rule_inference",
        ),
    )
    op.add_column(
        "agent_memories",
        sa.Column(
            "last_observed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.add_column(
        "agent_memories",
        sa.Column(
            "status",
            sa.String(16),
            nullable=False,
            server_default="active",
        ),
    )
    op.add_column(
        "agent_memories",
        sa.Column("suppress_until", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "agent_memories",
        sa.Column(
            "churn_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )

    with op.get_context().autocommit_block():
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_agent_memories_user_status "
            "ON agent_memories (user_id, status)"
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(
            "DROP INDEX CONCURRENTLY IF EXISTS ix_agent_memories_user_status"
        )
    op.drop_column("agent_memories", "churn_count")
    op.drop_column("agent_memories", "suppress_until")
    op.drop_column("agent_memories", "status")
    op.drop_column("agent_memories", "last_observed_at")
    op.drop_column("agent_memories", "source")
