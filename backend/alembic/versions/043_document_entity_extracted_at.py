"""043_document_entity_extracted_at

Document 加 entity_extracted_at 字段（D1 GraphRAG backfill 幂等判断）。

Revision ID: 043_document_entity_extracted_at
Revises: 042_entities_relations
Create Date: 2026-07-29 00:00:00.000000
"""
from __future__ import annotations

from typing import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "043_document_entity_extracted_at"
down_revision: str | None = "042_entities_relations"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column(
            "entity_extracted_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("documents", "entity_extracted_at")
