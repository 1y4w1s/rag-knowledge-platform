"""030_performance_indexes_v2: 新增检索/对话缺失索引

Revision ID: 030
Revises: 029
Create Date: 2026-07-15

改动：
  1. document_chunks.content_tsv → GIN 索引（加速全文检索）
  2. document_chunks (kb_id, chunk_kind) → 复合索引（加速检索过滤）
  3. chat_messages.created_at → 索引（加速对话历史排序）
  4. chat_threads.updated_at → 索引（加速 thread 列表排序）
  5. chat_threads.last_message_at → 索引（加速 thread 最新活动排序）
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "030"
down_revision: str | None = "d057befd441b"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # document_chunks — FTS 检索加速
    op.create_index("ix_document_chunks_content_tsv_gin", "document_chunks",
                    [sa.text("content_tsv")], postgresql_using="gin")
    op.create_index("ix_document_chunks_kb_chunk_kind", "document_chunks",
                    ["kb_id", "chunk_kind"])

    # chat_messages — 对话历史排序
    op.create_index("ix_chat_messages_created_at", "chat_messages", ["created_at"])

    # chat_threads — 列表排序
    op.create_index("ix_chat_threads_updated_at", "chat_threads", ["updated_at"])
    op.create_index("ix_chat_threads_last_message_at", "chat_threads", ["last_message_at"])


def downgrade() -> None:
    op.drop_index("ix_document_chunks_content_tsv_gin")
    op.drop_index("ix_document_chunks_kb_chunk_kind")
    op.drop_index("ix_chat_messages_created_at")
    op.drop_index("ix_chat_threads_updated_at")
    op.drop_index("ix_chat_threads_last_message_at")
