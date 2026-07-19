"""enable pgvector extension

Revision ID: 001
Revises:
Create Date: 2026-07-03

Wave 0.3: empty schema bootstrap — ensure vector extension exists.
Business tables (users, kb, ...) come in Wave 1+ migrations.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")


def downgrade() -> None:
    op.execute("DROP EXTENSION IF EXISTS vector")
