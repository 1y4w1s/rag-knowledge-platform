"""021 — agent_runs + agent_steps (G3-0.1)

Revision ID: 021
Revises: 020
Create Date: 2026-07-09

G3-0.1: thorough-mode agent execution metadata; FK thread/user/message.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "021"
down_revision: Union[str, None] = "020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

agent_mode_enum = postgresql.ENUM(
    "thorough",
    name="agent_mode",
    create_type=False,
)
agent_run_status_enum = postgresql.ENUM(
    "running",
    "completed",
    "failed",
    "capped",
    name="agent_run_status",
    create_type=False,
)
agent_step_status_enum = postgresql.ENUM(
    "running",
    "done",
    "error",
    name="agent_step_status",
    create_type=False,
)


def upgrade() -> None:
    op.execute("CREATE TYPE agent_mode AS ENUM ('thorough')")
    op.execute(
        "CREATE TYPE agent_run_status AS ENUM "
        "('running', 'completed', 'failed', 'capped')"
    )
    op.execute(
        "CREATE TYPE agent_step_status AS ENUM ('running', 'done', 'error')"
    )

    op.create_table(
        "agent_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
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
            "mode",
            agent_mode_enum,
            nullable=False,
            server_default="thorough",
        ),
        sa.Column(
            "status",
            agent_run_status_enum,
            nullable=False,
            server_default="running",
        ),
        sa.Column(
            "steps_used",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "max_steps",
            sa.Integer(),
            nullable=False,
            server_default="5",
        ),
        sa.Column(
            "assistant_message_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("chat_messages.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_agent_runs_thread_id", "agent_runs", ["thread_id"])
    op.create_index("ix_agent_runs_user_id", "agent_runs", ["user_id"])
    op.create_index(
        "ix_agent_runs_assistant_message_id",
        "agent_runs",
        ["assistant_message_id"],
    )

    op.create_table(
        "agent_steps",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agent_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("step_index", sa.Integer(), nullable=False),
        sa.Column("tool_name", sa.String(length=64), nullable=False),
        sa.Column("args_json", postgresql.JSONB(), nullable=True),
        sa.Column("result_summary", sa.Text(), nullable=True),
        sa.Column("ok", sa.Boolean(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column(
            "status",
            agent_step_status_enum,
            nullable=False,
            server_default="running",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_agent_steps_run_id", "agent_steps", ["run_id"])
    op.create_index(
        "ix_agent_steps_run_step",
        "agent_steps",
        ["run_id", "step_index"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_agent_steps_run_step", table_name="agent_steps")
    op.drop_index("ix_agent_steps_run_id", table_name="agent_steps")
    op.drop_table("agent_steps")
    op.drop_index("ix_agent_runs_assistant_message_id", table_name="agent_runs")
    op.drop_index("ix_agent_runs_user_id", table_name="agent_runs")
    op.drop_index("ix_agent_runs_thread_id", table_name="agent_runs")
    op.drop_table("agent_runs")
    op.execute("DROP TYPE agent_step_status")
    op.execute("DROP TYPE agent_run_status")
    op.execute("DROP TYPE agent_mode")
