"""017 — chat_messages workspace thread columns

Revision ID: 017
Revises: 016
Create Date: 2026-07-08

G1-0.1: thread_kind + nullable kb_id + workspace context for /ask history.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "017"
down_revision: Union[str, None] = "016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

thread_kind_enum = postgresql.ENUM(
    "knowledge_base",
    "workspace",
    name="thread_kind",
    create_type=False,
)


def upgrade() -> None:
    op.execute(
        "CREATE TYPE thread_kind AS ENUM ('knowledge_base', 'workspace')"
    )

    op.add_column(
        "chat_messages",
        sa.Column(
            "thread_kind",
            thread_kind_enum,
            nullable=False,
            server_default="knowledge_base",
        ),
    )
    op.add_column(
        "chat_messages",
        sa.Column("workspace_kind", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "chat_messages",
        sa.Column("workspace_org_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "chat_messages",
        sa.Column("workspace_department_key", sa.String(length=64), nullable=True),
    )

    op.alter_column("chat_messages", "kb_id", existing_type=postgresql.UUID(), nullable=True)

    op.create_index(
        "ix_chat_messages_workspace_thread",
        "chat_messages",
        [
            "user_id",
            "thread_kind",
            "workspace_kind",
            "workspace_org_id",
            "workspace_department_key",
            "created_at",
        ],
    )


def downgrade() -> None:
    op.drop_index("ix_chat_messages_workspace_thread", table_name="chat_messages")
    op.alter_column("chat_messages", "kb_id", existing_type=postgresql.UUID(), nullable=False)
    op.drop_column("chat_messages", "workspace_department_key")
    op.drop_column("chat_messages", "workspace_org_id")
    op.drop_column("chat_messages", "workspace_kind")
    op.drop_column("chat_messages", "thread_kind")
    op.execute("DROP TYPE thread_kind")
