"""024 — chat_messages 附属 approval_id + approval_status (G4-0.4)

Revision ID: 024
Revises: 023
Create Date: 2026-07-10

G4-0.4: chat_messages 添加 approval_id FK → agent_approvals.id
与 approval_status JSONB，支持 H4-3-B 刷新后卡片终态保留。
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "024"
down_revision: Union[str, None] = "023"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "chat_messages",
        sa.Column(
            "approval_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agent_approvals.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "chat_messages",
        sa.Column("approval_status", postgresql.JSONB(), nullable=True),
    )
    op.create_index(
        "ix_chat_messages_approval_id", "chat_messages", ["approval_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_chat_messages_approval_id", table_name="chat_messages")
    op.drop_column("chat_messages", "approval_status")
    op.drop_column("chat_messages", "approval_id")