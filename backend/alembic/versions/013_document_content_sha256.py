"""013 — documents.content_sha256

Revision ID: 013
Revises: 012
Create Date: 2026-07-06

EW-D1 / Plan-3E-7: SHA-256 content fingerprint for same-KB deduplication.
"""

import hashlib
from pathlib import Path
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "013"
down_revision: Union[str, None] = "012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _backfill_content_sha256() -> None:
    conn = op.get_bind()
    rows = conn.execute(
        sa.text("SELECT id, storage_path FROM documents WHERE content_sha256 IS NULL")
    ).fetchall()
    for row in rows:
        path = Path(row.storage_path)
        if not path.is_file():
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        conn.execute(
            sa.text(
                "UPDATE documents SET content_sha256 = :digest WHERE id = :doc_id"
            ),
            {"digest": digest, "doc_id": row.id},
        )


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column("content_sha256", sa.String(length=64), nullable=True),
    )
    _backfill_content_sha256()
    op.create_index(
        "uq_documents_kb_content_sha256",
        "documents",
        ["kb_id", "content_sha256"],
        unique=True,
        postgresql_where=sa.text("content_sha256 IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_documents_kb_content_sha256", table_name="documents")
    op.drop_column("documents", "content_sha256")
