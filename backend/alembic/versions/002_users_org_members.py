"""002 — users / organizations / organization_members

Revision ID: 002
Revises: 001
Create Date: 2026-07-03

Wave 1.1: identity tables for personal + enterprise registration.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

account_type_enum = postgresql.ENUM(
    "personal", "enterprise", name="account_type", create_type=False
)
org_role_enum = postgresql.ENUM("admin", "member", name="org_role", create_type=False)


def upgrade() -> None:
    op.execute("CREATE TYPE account_type AS ENUM ('personal', 'enterprise')")
    op.execute("CREATE TYPE org_role AS ENUM ('admin', 'member')")

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column(
            "account_type",
            account_type_enum,
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "organizations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    op.create_table(
        "organization_members",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", org_role_enum, nullable=False),
        sa.Column(
            "joined_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("org_id", "user_id", name="uq_org_member"),
    )


def downgrade() -> None:
    op.drop_table("organization_members")
    op.drop_table("organizations")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
    op.execute("DROP TYPE IF EXISTS org_role")
    op.execute("DROP TYPE IF EXISTS account_type")
