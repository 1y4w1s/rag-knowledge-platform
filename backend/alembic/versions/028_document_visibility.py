"""028 — documents.visibility 列（文档级权限）

新增 documents.visibility 列，用于文档级可见性控制。
可选值: everyone（默认）/ admin_only。

Revision ID: 028
Revises: 027
Create Date: 2026-07-14
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "028"
down_revision: Union[str, None] = "027"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE TYPE document_visibility AS ENUM ('everyone', 'admin_only')")
    op.add_column(
        "documents",
        sa.Column(
            "visibility",
            sa.Enum("everyone", "admin_only", name="document_visibility", create_type=False),
            nullable=False,
            server_default="everyone",
        ),
    )


def downgrade() -> None:
    op.drop_column("documents", "visibility")
    op.execute("DROP TYPE document_visibility")
