"""009 — organization_invite_codes（W5+-2 邀请码）

Revision ID: 009
Revises: 008
Create Date: 2026-07-05
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "organization_invite_codes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index(
        op.f("ix_organization_invite_codes_code"),
        "organization_invite_codes",
        ["code"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_organization_invite_codes_code"), table_name="organization_invite_codes")
    op.drop_table("organization_invite_codes")
