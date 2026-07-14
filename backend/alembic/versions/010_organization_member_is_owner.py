"""010 — organization_members.is_owner（W5+-4 Owner 内核）

Revision ID: 010
Revises: 009
Create Date: 2026-07-05
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "organization_members",
        sa.Column("is_owner", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.execute(
        """
        UPDATE organization_members AS om
        SET is_owner = true
        FROM (
            SELECT DISTINCT ON (org_id) id
            FROM organization_members
            WHERE role = 'admin'
            ORDER BY org_id, joined_at ASC
        ) AS first_admin
        WHERE om.id = first_admin.id
        """
    )
    op.alter_column("organization_members", "is_owner", server_default=None)


def downgrade() -> None:
    op.drop_column("organization_members", "is_owner")
