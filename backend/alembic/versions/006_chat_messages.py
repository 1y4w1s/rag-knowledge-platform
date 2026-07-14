"""006 — chat_messages

Revision ID: 006
Revises: 005
Create Date: 2026-07-03

Wave 3.2: persist chat messages and citations JSONB.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE TYPE message_role AS ENUM ('user', 'assistant')")

    op.create_table(
        "chat_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "kb_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("knowledge_bases.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "role",
            postgresql.ENUM("user", "assistant", name="message_role", create_type=False),
            nullable=False,
        ),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("citations", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_chat_messages_kb_id", "chat_messages", ["kb_id"])
    op.create_index("ix_chat_messages_user_id", "chat_messages", ["user_id"])
    op.create_index(
        "ix_chat_messages_kb_user_created",
        "chat_messages",
        ["kb_id", "user_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_chat_messages_kb_user_created", table_name="chat_messages")
    op.drop_index("ix_chat_messages_user_id", table_name="chat_messages")
    op.drop_index("ix_chat_messages_kb_id", table_name="chat_messages")
    op.drop_table("chat_messages")
    op.execute("DROP TYPE message_role")
