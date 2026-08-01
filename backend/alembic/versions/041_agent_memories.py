"""041_agent_memories

Revision ID: 041_agent_memories
Revises: 040
Create Date: 2026-07-28 17:00:00.000000
"""
from __future__ import annotations

from typing import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "041_agent_memories"
down_revision: str | None = "040"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "agent_memories",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("kb_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("knowledge_bases.id", ondelete="SET NULL"),
                  nullable=True),
        sa.Column("memory_type", sa.String(), nullable=False),
        sa.Column("key", sa.String(), nullable=False),
        sa.Column("value", postgresql.JSONB, nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("last_accessed_at", sa.DateTime(timezone=True),
                  nullable=False,
                  server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "key", name="uq_user_memory_key"),
    )


def downgrade() -> None:
    op.drop_table("agent_memories")
