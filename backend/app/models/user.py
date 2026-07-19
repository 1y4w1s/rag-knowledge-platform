"""users 表（Wave 1.1）。"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.enums import AccountType


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    username: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    nickname: Mapped[str | None] = mapped_column(String(64), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    account_type: Mapped[AccountType] = mapped_column(
        Enum(AccountType, name="account_type", native_enum=True),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    organization_memberships = relationship(
        "OrganizationMember", back_populates="user", lazy="selectin"
    )
    org_unit_memberships = relationship(
        "OrgUnitMember", back_populates="user", lazy="selectin"
    )
