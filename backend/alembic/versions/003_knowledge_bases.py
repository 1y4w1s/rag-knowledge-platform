"""003 — knowledge_bases

Revision ID: 003
Revises: 002
Create Date: 2026-07-03

Wave 2.1: knowledge base table with personal (owner_user_id) / enterprise (owner_org_id) isolation.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "knowledge_bases",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "owner_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "owner_org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(owner_user_id IS NOT NULL AND owner_org_id IS NULL) OR "
            "(owner_user_id IS NULL AND owner_org_id IS NOT NULL)",
            name="ck_kb_owner_xor",
        ),
    )
    op.create_index(
        "ix_knowledge_bases_owner_user_id",
        "knowledge_bases",
        ["owner_user_id"],
    )
    op.create_index(
        "ix_knowledge_bases_owner_org_id",
        "knowledge_bases",
        ["owner_org_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_knowledge_bases_owner_org_id", table_name="knowledge_bases")
    op.drop_index("ix_knowledge_bases_owner_user_id", table_name="knowledge_bases")
    op.drop_table("knowledge_bases")
