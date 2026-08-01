"""038_add_message_status

为 ChatMessage 添加 status 字段（pending / completed / interrupted），
用于 SSE 断开的对话保存和中断标记。

Revision ID: 038
Revises: 037
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "038"
down_revision = "037"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 创建 ENUM 类型
    op.execute("CREATE TYPE message_status AS ENUM ('pending', 'completed', 'interrupted')")
    # 添加列（允许 NULL → 再设 NOT NULL）
    op.add_column("chat_messages", sa.Column("status", sa.Enum("pending", "completed", "interrupted", name="message_status", create_type=False), nullable=True))
    # 已有行默认 completed
    op.execute("UPDATE chat_messages SET status = 'completed' WHERE status IS NULL")
    # 设 NOT NULL
    op.alter_column("chat_messages", "status", nullable=False)


def downgrade() -> None:
    op.drop_column("chat_messages", "status")
    op.execute("DROP TYPE IF EXISTS message_status")
