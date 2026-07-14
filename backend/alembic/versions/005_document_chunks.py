"""005 — document_chunks + pgvector

Revision ID: 005
Revises: 004
Create Date: 2026-07-03

Wave 2.3: chunk metadata, pgvector embedding, tsvector for hybrid retrieval.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

EMBEDDING_DIM = 1536


def upgrade() -> None:
    op.create_table(
        "document_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "kb_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("knowledge_bases.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("section_title", sa.String(512), nullable=True),
        sa.Column("heading_path", sa.String(1024), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=True),
        sa.Column("content_tsv", postgresql.TSVECTOR(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_document_chunks_kb_id", "document_chunks", ["kb_id"])
    op.create_index(
        "ix_document_chunks_document_id", "document_chunks", ["document_id"]
    )
    op.create_index(
        "ix_document_chunks_content_tsv",
        "document_chunks",
        ["content_tsv"],
        postgresql_using="gin",
    )
    op.execute(
        "CREATE INDEX ix_document_chunks_embedding_hnsw ON document_chunks "
        "USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_document_chunks_embedding_hnsw")
    op.drop_index("ix_document_chunks_content_tsv", table_name="document_chunks")
    op.drop_index("ix_document_chunks_document_id", table_name="document_chunks")
    op.drop_index("ix_document_chunks_kb_id", table_name="document_chunks")
    op.drop_table("document_chunks")
