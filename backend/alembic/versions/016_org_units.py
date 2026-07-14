"""016 — org_units / org_unit_members / kb_unit_grants / knowledge_bases.org_unit_id

Revision ID: 016
Revises: 015
Create Date: 2026-07-07

ORG Plan-0: department tree + KB unit ownership + cross-unit grants.
"""

from typing import Sequence, Union
import uuid

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "016"
down_revision: Union[str, None] = "015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

unit_role_enum = postgresql.ENUM(
    "unit_admin", "unit_member", name="unit_role", create_type=False
)
grantee_type_enum = postgresql.ENUM(
    "org_unit", "company", name="grantee_type", create_type=False
)
grant_permission_enum = postgresql.ENUM(
    "read", "write", name="grant_permission", create_type=False
)


def upgrade() -> None:
    op.execute("CREATE TYPE unit_role AS ENUM ('unit_admin', 'unit_member')")
    op.execute("CREATE TYPE grantee_type AS ENUM ('org_unit', 'company')")
    op.execute("CREATE TYPE grant_permission AS ENUM ('read', 'write')")

    op.create_table(
        "org_units",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "parent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("org_units.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("path", sa.String(length=4096), nullable=False),
        sa.Column("depth", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_org_units_org_id", "org_units", ["org_id"])
    op.create_index("ix_org_units_path", "org_units", ["path"])

    op.create_table(
        "org_unit_members",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "org_unit_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("org_units.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", unit_role_enum, nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "joined_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("org_unit_id", "user_id", name="uq_org_unit_member"),
    )
    op.create_index("ix_org_unit_members_user_id", "org_unit_members", ["user_id"])

    op.add_column(
        "knowledge_bases",
        sa.Column(
            "org_unit_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("org_units.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )

    op.create_table(
        "kb_unit_grants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "kb_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("knowledge_bases.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("grantee_type", grantee_type_enum, nullable=False),
        sa.Column(
            "grantee_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("org_units.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "permission",
            grant_permission_enum,
            nullable=False,
            server_default="read",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "kb_id",
            "grantee_type",
            "grantee_id",
            name="uq_kb_unit_grant_target",
        ),
    )
    op.create_index("ix_kb_unit_grants_kb_id", "kb_unit_grants", ["kb_id"])

    bind = op.get_bind()
    orgs = bind.execute(sa.text("SELECT id, name FROM organizations")).fetchall()
    for org_id, org_name in orgs:
        root_id = uuid.uuid4()
        root_path = f"/{root_id}/"
        bind.execute(
            sa.text(
                """
                INSERT INTO org_units (id, org_id, parent_id, name, path, depth)
                VALUES (:id, :org_id, NULL, :name, :path, 0)
                """
            ),
            {"id": root_id, "org_id": org_id, "name": org_name, "path": root_path},
        )
        members = bind.execute(
            sa.text(
                """
                SELECT om.user_id, om.role, om.is_owner
                FROM organization_members om
                WHERE om.org_id = :org_id
                """
            ),
            {"org_id": org_id},
        ).fetchall()
        for user_id, org_role, is_owner in members:
            unit_role = "unit_admin" if org_role == "admin" or is_owner else "unit_member"
            bind.execute(
                sa.text(
                    """
                    INSERT INTO org_unit_members (id, org_unit_id, user_id, role, is_primary)
                    VALUES (:id, :org_unit_id, :user_id, :role, true)
                    """
                ),
                {
                    "id": uuid.uuid4(),
                    "org_unit_id": root_id,
                    "user_id": user_id,
                    "role": unit_role,
                },
            )


def downgrade() -> None:
    op.drop_index("ix_kb_unit_grants_kb_id", table_name="kb_unit_grants")
    op.drop_table("kb_unit_grants")
    op.drop_column("knowledge_bases", "org_unit_id")
    op.drop_index("ix_org_unit_members_user_id", table_name="org_unit_members")
    op.drop_table("org_unit_members")
    op.drop_index("ix_org_units_path", table_name="org_units")
    op.drop_index("ix_org_units_org_id", table_name="org_units")
    op.drop_table("org_units")
    op.execute("DROP TYPE IF EXISTS grant_permission")
    op.execute("DROP TYPE IF EXISTS grantee_type")
    op.execute("DROP TYPE IF EXISTS unit_role")
