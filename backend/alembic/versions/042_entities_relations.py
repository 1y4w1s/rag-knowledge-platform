"""042_entities_relations

D1 GraphRAG — Entity / EntityMention / Relation 三表。

Revision ID: 042_entities_relations
Revises: 041_agent_memories
Create Date: 2026-07-29 00:00:00.000000
"""
from __future__ import annotations

from typing import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "042_entities_relations"
down_revision: str | None = "041_agent_memories"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # entities
    op.create_table(
        "entities",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("kb_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("knowledge_bases.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("type", sa.String(64), nullable=False),
        sa.Column("metadata", postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("kb_id", "name", "type", name="uq_entity_kb_name_type"),
    )

    # entity_mentions
    op.create_table(
        "entity_mentions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("chunk_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("document_chunks.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("entities.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.UniqueConstraint("chunk_id", "entity_id", name="uq_mention_chunk_entity"),
    )

    # relations
    op.create_table(
        "relations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("kb_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("knowledge_bases.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("source_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("entities.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("target_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("entities.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("relation_type", sa.String(64), nullable=False),
        sa.Column("metadata", postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_relations_kb_type", "relations", ["kb_id", "relation_type"])


def downgrade() -> None:
    op.drop_table("relations")
    op.drop_table("entity_mentions")
    op.drop_table("entities")
