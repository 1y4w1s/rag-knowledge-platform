"""014 — document_chunks parent-child + chunk_kind

Revision ID: 014
Revises: 013
Create Date: 2026-07-06

Plan-RAG R2-2: table chunks + parent-child retrieval (TECH-4 §4.3.6).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "014"
down_revision: Union[str, None] = "013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "document_chunks",
        sa.Column(
            "parent_chunk_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("document_chunks.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "document_chunks",
        sa.Column(
            "chunk_kind",
            sa.String(length=16),
            nullable=False,
            server_default="text",
        ),
    )
    op.create_index(
        "ix_document_chunks_parent_chunk_id",
        "document_chunks",
        ["parent_chunk_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_document_chunks_parent_chunk_id", table_name="document_chunks")
    op.drop_column("document_chunks", "chunk_kind")
    op.drop_column("document_chunks", "parent_chunk_id")
