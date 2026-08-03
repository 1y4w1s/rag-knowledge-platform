"""045 — knowledge_bases owner FK CASCADE → RESTRICT（P1-23 禁删）

Revision ID: 045_kb_owner_restrict
Revises: 044_model_alignment
Create Date: 2026-08-03

P1-23 选项 B（拍板文档 §6.2 / §9.2）：`knowledge_bases.owner_user_id` /
`owner_org_id` 由 ON DELETE CASCADE 改为 ON DELETE RESTRICT——有 KB 归属时
删用户/组织**显式失败**（FK 冲突），必须先显式处理 KB（`delete_knowledge_base`
+ `remove_kb_tree` 清盘，或转移所有权），与 NW-41「禁止裸 DELETE users」一致。

安全纪律：
- 仅 drop 旧 FK + 建 ON DELETE RESTRICT 新约束，不含任何数据改写 / DROP TABLE；
- `organization_members` / `chat_threads` 等 user 子表 CASCADE 保持不变
  （成员关系/对话属用户数据，删号清理由 NW-41 编排负责）。
"""

from __future__ import annotations

from alembic import op

revision: str = "045_kb_owner_restrict"
down_revision: str | None = "044_model_alignment"
branch_labels: str | None = None
depends_on: str | None = None

# (约束名, 表, 列, 引用表)；约束名沿用 PG 默认命名，与 003 建表时一致。
_KB_OWNER_FKS: tuple[tuple[str, str, str, str], ...] = (
    ("knowledge_bases_owner_user_id_fkey", "knowledge_bases", "owner_user_id", "users"),
    (
        "knowledge_bases_owner_org_id_fkey",
        "knowledge_bases",
        "owner_org_id",
        "organizations",
    ),
)


def upgrade() -> None:
    for name, table, column, referent in _KB_OWNER_FKS:
        op.drop_constraint(name, table, type_="foreignkey")
        op.create_foreign_key(
            name,
            table,
            referent,
            [column],
            ["id"],
            ondelete="RESTRICT",
        )


def downgrade() -> None:
    for name, table, column, referent in reversed(_KB_OWNER_FKS):
        op.drop_constraint(name, table, type_="foreignkey")
        op.create_foreign_key(
            name,
            table,
            referent,
            [column],
            ["id"],
            ondelete="CASCADE",
        )
