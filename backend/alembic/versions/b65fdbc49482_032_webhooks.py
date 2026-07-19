"""032_webhooks: 新增 webhooks 表

改动：
  1. 新建 webhooks 表

Revision ID: b65fdbc49482
Revises: be3d9fc2c804
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "b65fdbc49482"
down_revision: Union[str, None] = "be3d9fc2c804"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "webhooks",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("kb_id", sa.UUID(), nullable=False),
        sa.Column("url", sa.String(length=2048), nullable=False),
        sa.Column("secret", sa.String(length=128), nullable=False),
        sa.Column("events", sa.String(length=256), nullable=False, server_default=sa.text("'document.completed'")),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["kb_id"], ["knowledge_bases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_webhooks_kb_id"), "webhooks", ["kb_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_webhooks_kb_id"), table_name="webhooks")
    op.drop_table("webhooks")
