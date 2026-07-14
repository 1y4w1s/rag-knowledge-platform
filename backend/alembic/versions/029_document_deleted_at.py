"""029 — documents.deleted_at 列（软删·回收站）

新增 deleted_at 字段，删除文档时设为当前时间而非物理删除。
列表/检索/搜索查询须过滤 deleted_at IS NULL。

Revision ID: 029
Revises: 028
Create Date: 2026-07-14
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "029"
down_revision: Union[str, None] = "028"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("documents", "deleted_at")
