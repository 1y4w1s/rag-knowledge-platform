"""022 — agent_approvals (G4-0.1)

Revision ID: 022
Revises: 021
Create Date: 2026-07-10

G4-0.1: approval table for adopt-to-kb write flow; FK run/thread/user/kb.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "022"
down_revision: Union[str, None] = "021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

approval_kind_enum = postgresql.ENUM(
    "adopt_faq",
    name="approval_kind",
    create_type=False,
)
approval_status_enum = postgresql.ENUM(
    "pending",
    "adopted",
    "cancelled",
    "expired",
    name="approval_status",
    create_type=False,
)


def upgrade() -> None:
    op.execute("CREATE TYPE approval_kind AS ENUM ('adopt_faq')")
    op.execute(
        "CREATE TYPE approval_status AS ENUM "
        "('pending', 'adopted', 'cancelled', 'expired')"
    )

    op.create_table(
        "agent_approvals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agent_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "thread_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("chat_threads.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "kind",
            approval_kind_enum,
            nullable=False,
            server_default="adopt_faq",
        ),
        sa.Column(
            "status",
            approval_status_enum,
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "kb_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("knowledge_bases.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("filename", sa.String(length=512), nullable=False),
        sa.Column("payload_json", postgresql.JSONB(), nullable=True),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_agent_approvals_run_id", "agent_approvals", ["run_id"])
    op.create_index("ix_agent_approvals_thread_id", "agent_approvals", ["thread_id"])
    op.create_index("ix_agent_approvals_user_id", "agent_approvals", ["user_id"])
    op.create_index("ix_agent_approvals_kb_id", "agent_approvals", ["kb_id"])
    op.create_index(
        "ix_agent_approvals_document_id", "agent_approvals", ["document_id"]
    )
    op.create_index(
        "ix_agent_approvals_status", "agent_approvals", ["status"]
    )


def downgrade() -> None:
    op.drop_index("ix_agent_approvals_status", table_name="agent_approvals")
    op.drop_index("ix_agent_approvals_document_id", table_name="agent_approvals")
    op.drop_index("ix_agent_approvals_kb_id", table_name="agent_approvals")
    op.drop_index("ix_agent_approvals_user_id", table_name="agent_approvals")
    op.drop_index("ix_agent_approvals_thread_id", table_name="agent_approvals")
    op.drop_index("ix_agent_approvals_run_id", table_name="agent_approvals")
    op.drop_table("agent_approvals")
    op.execute("DROP TYPE approval_status")
    op.execute("DROP TYPE approval_kind")