"""033_custom_roles: 自定义角色权限

改动：
  1. 新建 custom_roles 表
  2. organization_members 加 custom_role_id 外键

Revision ID: 033
Revises: b65fdbc49482
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "033"
down_revision: Union[str, None] = "b65fdbc49482"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "custom_roles",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_admin_level", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("permissions", postgresql.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_custom_roles_org_id"), "custom_roles", ["org_id"], unique=False)

    op.add_column(
        "organization_members",
        sa.Column("custom_role_id", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        "fk_org_members_custom_role",
        "organization_members", "custom_roles",
        ["custom_role_id"], ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_org_members_custom_role", "organization_members", type_="foreignkey")
    op.drop_column("organization_members", "custom_role_id")
    op.drop_index(op.f("ix_custom_roles_org_id"), table_name="custom_roles")
    op.drop_table("custom_roles")
