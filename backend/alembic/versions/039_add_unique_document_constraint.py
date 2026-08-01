"""039_add_unique_document_constraint

防止并发上传竞态导致同名同内容文档出现两条。
在 (kb_id, filename, content_sha256) 上建唯一索引，仅约束未软删的文档。

Revision ID: 039
Revises: 038
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "039"
down_revision = "038"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 先清理存在的重复数据（保留最早的那条）
    op.execute("""
        DELETE FROM documents d1 USING (
            SELECT kb_id, filename, content_sha256, MIN(created_at) as min_created
            FROM documents
            WHERE deleted_at IS NULL AND content_sha256 IS NOT NULL
            GROUP BY kb_id, filename, content_sha256
            HAVING COUNT(*) > 1
        ) dup
        WHERE d1.kb_id = dup.kb_id
          AND d1.filename = dup.filename
          AND d1.content_sha256 = dup.content_sha256
          AND d1.deleted_at IS NULL
          AND d1.created_at > dup.min_created
    """)
    # 创建部分唯一索引
    op.create_index(
        "uq_documents_kb_filename_sha256",
        "documents",
        ["kb_id", "filename", "content_sha256"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL AND content_sha256 IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_documents_kb_filename_sha256")
