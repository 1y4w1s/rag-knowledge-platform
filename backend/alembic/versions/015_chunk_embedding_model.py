"""015 — document_chunks.embedding_model

Revision ID: 015
Revises: 014
Create Date: 2026-07-06

Plan-RAG R2-4: track embedding model per chunk for stale re-embed (TECH-4 §4.4).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "015"
down_revision: Union[str, None] = "014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "document_chunks",
        sa.Column("embedding_model", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("document_chunks", "embedding_model")
