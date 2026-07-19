"""026 — knowledge_bases + documents 查询性能索引

M2 实测（6000 库）：
  GET /knowledge-bases p95=5.4s → 预期 < 50ms
  GET /dashboard/stats  p95=10s  → 预期 < 200ms

添加：
  1. knowledge_bases(owner_org_id, created_at DESC) — 组织空间列表排序
  2. knowledge_bases(owner_user_id, created_at DESC) — 个人空间列表排序
  3. documents(kb_id) — 文档 JOIN 加速（FK 无自动索引）

Revision ID: 026
Revises: 025
Create Date: 2026-07-14
"""

from typing import Sequence, Union
from alembic import op

revision: str = "026"
down_revision: Union[str, None] = "025"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # knowledge_bases: 组织空间列表按创建时间排序
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_kb_owner_org_created "
        "ON knowledge_bases (owner_org_id, created_at DESC)"
    )
    # knowledge_bases: 个人空间列表按创建时间排序
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_kb_owner_user_created "
        "ON knowledge_bases (owner_user_id, created_at DESC)"
    )
    # documents: kb_id 外键无自动索引，JOIN 时全表扫描
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_doc_kb_id ON documents (kb_id)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_kb_owner_org_created")
    op.execute("DROP INDEX IF EXISTS idx_kb_owner_user_created")
    op.execute("DROP INDEX IF EXISTS idx_doc_kb_id")
