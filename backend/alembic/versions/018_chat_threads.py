"""018 — chat_threads + chat_messages.thread_id

Revision ID: 018
Revises: 017
Create Date: 2026-07-09

G2-0.1: enterprise thread table; thread_id nullable until G2-0.2 backfill.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "018"
down_revision: Union[str, None] = "017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

thread_kind_enum = postgresql.ENUM(
    "knowledge_base",
    "workspace",
    name="thread_kind",
    create_type=False,
)
thread_status_enum = postgresql.ENUM(
    "active",
    "archived",
    name="thread_status",
    create_type=False,
)


def upgrade() -> None:
    op.execute("CREATE TYPE thread_status AS ENUM ('active', 'archived')")

    op.create_table(
        "chat_threads",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "thread_kind",
            thread_kind_enum,
            nullable=False,
        ),
        sa.Column(
            "kb_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("knowledge_bases.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=256), nullable=False, server_default=""),
        sa.Column("workspace_kind", sa.String(length=32), nullable=True),
        sa.Column("workspace_org_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("workspace_department_key", sa.String(length=64), nullable=True),
        sa.Column(
            "status",
            thread_status_enum,
            nullable=False,
            server_default="active",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_chat_threads_user_id", "chat_threads", ["user_id"])
    op.create_index("ix_chat_threads_kb_id", "chat_threads", ["kb_id"])
    op.create_index(
        "ix_chat_threads_list_scope",
        "chat_threads",
        [
            "user_id",
            "thread_kind",
            "workspace_kind",
            "workspace_org_id",
            "workspace_department_key",
            "status",
            "last_message_at",
        ],
    )

    op.add_column(
        "chat_messages",
        sa.Column(
            "thread_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("chat_threads.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.create_index("ix_chat_messages_thread_id", "chat_messages", ["thread_id"])


def downgrade() -> None:
    op.drop_index("ix_chat_messages_thread_id", table_name="chat_messages")
    op.drop_column("chat_messages", "thread_id")
    op.drop_index("ix_chat_threads_list_scope", table_name="chat_threads")
    op.drop_index("ix_chat_threads_kb_id", table_name="chat_threads")
    op.drop_index("ix_chat_threads_user_id", table_name="chat_threads")
    op.drop_table("chat_threads")
    op.execute("DROP TYPE thread_status")
