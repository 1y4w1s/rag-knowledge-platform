"""034_performance_tuning: 连接池 + 实用索引 + 清理重复索引

改动：
  1. documents 加 (kb_id, deleted_at) 复合索引（文档列表常用查询）
  2. document_chunks 加 (document_id, chunk_index) 索引（chunk 顺序加载）
  3. 清理重复索引：
     - documents: idx_doc_kb_id（与 ix_documents_kb_id 重复）
     - document_chunks: ix_document_chunks_content_tsv（与 030 版本的 GIN 索引重复）

Revision ID: 034
Revises: 033
"""
from typing import Sequence, Union
from alembic import op

revision: str = "034"
down_revision: Union[str, None] = "033"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 新索引
    op.create_index("ix_documents_kb_deleted", "documents", ["kb_id", "deleted_at"])
    op.create_index("ix_document_chunks_doc_chunk", "document_chunks", ["document_id", "chunk_index"])

    # 清理重复索引
    op.drop_index("idx_doc_kb_id", table_name="documents")
    op.drop_index("ix_document_chunks_content_tsv", table_name="document_chunks")


def downgrade() -> None:
    op.create_index("idx_doc_kb_id", "documents", ["kb_id"])
    op.create_index("ix_document_chunks_content_tsv", "document_chunks", ["content_tsv"], postgresql_using="gin")
    op.drop_index("ix_documents_kb_deleted", table_name="documents")
    op.drop_index("ix_document_chunks_doc_chunk", table_name="document_chunks")
