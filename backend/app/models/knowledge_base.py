"""knowledge_bases 表（Wave 2.1）。"""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class KnowledgeBase(Base):
    __tablename__ = "knowledge_bases"
    __table_args__ = (
        CheckConstraint(
            "(owner_user_id IS NOT NULL AND owner_org_id IS NULL) OR "
            "(owner_user_id IS NULL AND owner_org_id IS NOT NULL)",
            name="ck_kb_owner_xor",
        ),
        Index(
            "idx_kb_owner_org_created",
            "owner_org_id",
            text("created_at DESC"),
        ),
        Index(
            "idx_kb_owner_user_created",
            "owner_user_id",
            text("created_at DESC"),
        ),
        Index(
            "uq_kb_org_name",
            "owner_org_id",
            text("lower(btrim(name))"),
            unique=True,
            postgresql_where=text("owner_org_id IS NOT NULL"),
        ),
        Index(
            "uq_kb_personal_name",
            "owner_user_id",
            text("lower(btrim(name))"),
            unique=True,
            postgresql_where=text("owner_user_id IS NOT NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    owner_org_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    org_unit_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("org_units.id", ondelete="SET NULL"),
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

    org_unit = relationship("OrgUnit", foreign_keys=[org_unit_id])
    unit_grants = relationship("KbUnitGrant", back_populates="knowledge_base")
