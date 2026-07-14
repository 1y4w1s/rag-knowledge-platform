"""020 — chat_messages.thread_id NOT NULL

Revision ID: 020
Revises: 019
Create Date: 2026-07-09

G2-0.3: orphan messages without thread_id get a default thread; then enforce NOT NULL.
"""

from __future__ import annotations

import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "020"
down_revision: Union[str, None] = "019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DEFAULT_THREAD_TITLE = "历史对话"

_GROUP_MESSAGES = sa.text(
    """
    SELECT
        user_id,
        thread_kind::text AS thread_kind,
        kb_id,
        workspace_kind,
        workspace_org_id,
        workspace_department_key,
        MIN(created_at) AS min_created_at,
        MAX(created_at) AS max_created_at
    FROM chat_messages
    WHERE thread_id IS NULL
    GROUP BY
        user_id,
        thread_kind,
        kb_id,
        workspace_kind,
        workspace_org_id,
        workspace_department_key
    """
)

_INSERT_THREAD = sa.text(
    """
    INSERT INTO chat_threads (
        id,
        thread_kind,
        kb_id,
        user_id,
        title,
        workspace_kind,
        workspace_org_id,
        workspace_department_key,
        status,
        created_at,
        updated_at,
        last_message_at
    ) VALUES (
        :id,
        :thread_kind,
        :kb_id,
        :user_id,
        :title,
        :workspace_kind,
        :workspace_org_id,
        :workspace_department_key,
        'active',
        :created_at,
        :updated_at,
        :last_message_at
    )
    """
)

_ASSIGN_MESSAGES = sa.text(
    """
    UPDATE chat_messages
    SET thread_id = :thread_id
    WHERE thread_id IS NULL
      AND user_id = :user_id
      AND thread_kind::text = :thread_kind
      AND kb_id IS NOT DISTINCT FROM :kb_id
      AND workspace_kind IS NOT DISTINCT FROM :workspace_kind
      AND workspace_org_id IS NOT DISTINCT FROM :workspace_org_id
      AND workspace_department_key IS NOT DISTINCT FROM :workspace_department_key
    """
)


def _backfill_orphan_messages() -> None:
    conn = op.get_bind()
    groups = conn.execute(_GROUP_MESSAGES).fetchall()
    for group in groups:
        thread_id = uuid.uuid4()
        conn.execute(
            _INSERT_THREAD,
            {
                "id": thread_id,
                "thread_kind": group.thread_kind,
                "kb_id": group.kb_id,
                "user_id": group.user_id,
                "title": DEFAULT_THREAD_TITLE,
                "workspace_kind": group.workspace_kind,
                "workspace_org_id": group.workspace_org_id,
                "workspace_department_key": group.workspace_department_key,
                "created_at": group.min_created_at,
                "updated_at": group.max_created_at,
                "last_message_at": group.max_created_at,
            },
        )
        conn.execute(
            _ASSIGN_MESSAGES,
            {
                "thread_id": thread_id,
                "user_id": group.user_id,
                "thread_kind": group.thread_kind,
                "kb_id": group.kb_id,
                "workspace_kind": group.workspace_kind,
                "workspace_org_id": group.workspace_org_id,
                "workspace_department_key": group.workspace_department_key,
            },
        )


def upgrade() -> None:
    _backfill_orphan_messages()
    op.alter_column(
        "chat_messages",
        "thread_id",
        existing_type=sa.UUID(),
        nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "chat_messages",
        "thread_id",
        existing_type=sa.UUID(),
        nullable=True,
    )
