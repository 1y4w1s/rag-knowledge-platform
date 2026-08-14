"""047 - api_keys.key_hash UNIQUE index (P1-35)

API Key auth looks up api_keys by key_hash; without an index every auth is a
full table scan. The live database was checked before this migration: no
duplicate key_hash values exist, so the unique index can be created directly.

Revision ID: 047
Revises: 046_agent_memories_kb_id_index
Create Date: 2026-08-11

Safety constraints:
  - Index DDL always uses CREATE INDEX CONCURRENTLY inside autocommit_block;
  - No irreversible data rewrites / DROP TABLE;
  - IF NOT EXISTS keeps the migration idempotent on fresh and existing DBs.
"""

from __future__ import annotations

from alembic import op

revision: str = "047"
down_revision: str | None = "046_agent_memories_kb_id_index"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(
            "CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS uq_api_keys_key_hash "
            "ON api_keys (key_hash)"
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS uq_api_keys_key_hash")
