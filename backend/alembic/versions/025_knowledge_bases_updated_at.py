"""025 — knowledge_bases 添加 updated_at 列

B1-1: knowledge_bases 缺少 updated_at 列，与 schema 不一致修复。

策略：纯 SQL，全部用 op.execute 执行 DDL/DML。

Revision ID: 025
Revises: 024
Create Date: 2026-07-14
"""

from typing import Sequence, Union

from alembic import op

revision: str = "025"
down_revision: Union[str, None] = "024"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE knowledge_bases ADD COLUMN updated_at TIMESTAMP WITH TIME ZONE")
    op.execute("UPDATE knowledge_bases SET updated_at = created_at")
    op.execute("ALTER TABLE knowledge_bases ALTER COLUMN updated_at SET NOT NULL")
    op.execute("ALTER TABLE knowledge_bases ALTER COLUMN updated_at SET DEFAULT now()")


def downgrade() -> None:
    op.drop_column("knowledge_bases", "updated_at")
