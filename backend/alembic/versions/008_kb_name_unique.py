"""008 — knowledge_bases 名称在同一 owner 内唯一（忽略大小写）

Revision ID: 008
Revises: 007
Create Date: 2026-07-04
"""

from typing import Sequence, Union

from alembic import op

revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _dedupe_kb_names(owner_column: str) -> None:
    """为已有重复名称追加序号，避免加唯一索引失败。"""
    op.execute(
        f"""
        WITH ranked AS (
            SELECT
                id,
                name,
                ROW_NUMBER() OVER (
                    PARTITION BY {owner_column}, lower(btrim(name))
                    ORDER BY created_at, id
                ) AS rn
            FROM knowledge_bases
            WHERE {owner_column} IS NOT NULL
        )
        UPDATE knowledge_bases AS kb
        SET name = kb.name || ' (' || ranked.rn || ')'
        FROM ranked
        WHERE kb.id = ranked.id AND ranked.rn > 1
        """
    )


def upgrade() -> None:
    _dedupe_kb_names("owner_user_id")
    _dedupe_kb_names("owner_org_id")

    op.execute(
        """
        CREATE UNIQUE INDEX uq_kb_personal_name
        ON knowledge_bases (owner_user_id, lower(btrim(name)))
        WHERE owner_user_id IS NOT NULL
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uq_kb_org_name
        ON knowledge_bases (owner_org_id, lower(btrim(name)))
        WHERE owner_org_id IS NOT NULL
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_kb_org_name")
    op.execute("DROP INDEX IF EXISTS uq_kb_personal_name")
