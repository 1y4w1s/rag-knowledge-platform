"""documents 表（Wave 2.2）。"""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import ENUM, UUID
from sqlalchemy.sql import text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.enums import DocumentStatus, DocumentVisibility


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        Index("ix_documents_kb_deleted", "kb_id", "deleted_at"),
        Index(
            "uq_documents_kb_content_sha256",
            "kb_id",
            "content_sha256",
            unique=True,
            postgresql_where=text("content_sha256 IS NOT NULL"),
        ),
        Index(
            "uq_documents_kb_filename_sha256",
            "kb_id",
            "filename",
            "content_sha256",
            unique=True,
            postgresql_where=text(
                "deleted_at IS NULL AND content_sha256 IS NOT NULL"
            ),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    kb_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("knowledge_bases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    file_type: Mapped[str] = mapped_column(String(32), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    content_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    storage_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    status: Mapped[DocumentStatus] = mapped_column(
        ENUM(DocumentStatus, name="document_status", create_type=False),
        nullable=False,
        default=DocumentStatus.queued,
        index=True,
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    chunk_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    processing_stage: Mapped[str | None] = mapped_column(String(32), nullable=True)
    progress_percent: Mapped[int | None] = mapped_column(Integer, nullable=True)
    progress_detail: Mapped[str | None] = mapped_column(String(64), nullable=True)
    processing_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    processing_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    visibility: Mapped[DocumentVisibility] = mapped_column(
        ENUM(DocumentVisibility, name="document_visibility", create_type=False),
        nullable=False,
        default=DocumentVisibility.everyone,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    current_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1
    )
    entity_extracted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
