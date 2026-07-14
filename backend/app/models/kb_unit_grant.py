"""kb_unit_grants 表（ORG · 跨部门库共享）。"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.enums import GranteeType, GrantPermission


class KbUnitGrant(Base):
    __tablename__ = "kb_unit_grants"
    __table_args__ = (
        UniqueConstraint(
            "kb_id",
            "grantee_type",
            "grantee_id",
            name="uq_kb_unit_grant_target",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    kb_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("knowledge_bases.id", ondelete="CASCADE"),
        nullable=False,
    )
    grantee_type: Mapped[GranteeType] = mapped_column(
        Enum(GranteeType, name="grantee_type", native_enum=True),
        nullable=False,
    )
    grantee_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("org_units.id", ondelete="CASCADE"),
        nullable=True,
    )
    permission: Mapped[GrantPermission] = mapped_column(
        Enum(GrantPermission, name="grant_permission", native_enum=True),
        nullable=False,
        default=GrantPermission.read,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    knowledge_base = relationship("KnowledgeBase", back_populates="unit_grants")
    grantee_unit = relationship("OrgUnit", foreign_keys=[grantee_id])
