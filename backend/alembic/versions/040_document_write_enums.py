"""040 — 文档写操作 ENUM 扩展 (G5 自然语言文档写操作)

Revision ID: 040
Revises: 039
Create Date: 2026-07-27

G5: agent_mode 增加 document_write（文档操作模式）；
approval_kind 增加 delete_document / restore_document（删除/恢复写操作审批）。
"""

from typing import Sequence, Union

from alembic import op

revision: str = "040"
down_revision: Union[str, None] = "039"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE agent_mode ADD VALUE 'document_write'")
    op.execute("ALTER TYPE approval_kind ADD VALUE 'delete_document'")
    op.execute("ALTER TYPE approval_kind ADD VALUE 'restore_document'")


def downgrade() -> None:
    # PostgreSQL 不支持从 ENUM 中移除单个值；不做回退操作
    pass
