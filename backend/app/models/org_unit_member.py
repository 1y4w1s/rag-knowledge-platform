"""org_unit_members 表（ORG Plan-0 · 部门成员）。"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.enums import UnitRole


class OrgUnitMember(Base):
    __tablename__ = "org_unit_members"
    __table_args__ = (
        UniqueConstraint("org_unit_id", "user_id", name="uq_org_unit_member"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    org_unit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("org_units.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[UnitRole] = mapped_column(
        Enum(UnitRole, name="unit_role", native_enum=True),
        nullable=False,
    )
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    org_unit = relationship("OrgUnit", back_populates="members")
    user = relationship("User", back_populates="org_unit_memberships")
