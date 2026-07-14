"""agent_runs 表（G3-0.1 · 精准模式 Agent 执行元数据）。"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, func
from sqlalchemy.dialects.postgresql import ENUM, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.enums import AgentRunMode, AgentRunStatus


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    thread_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chat_threads.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    mode: Mapped[AgentRunMode] = mapped_column(
        ENUM(AgentRunMode, name="agent_mode", create_type=False),
        nullable=False,
        server_default=AgentRunMode.thorough.value,
    )
    status: Mapped[AgentRunStatus] = mapped_column(
        ENUM(AgentRunStatus, name="agent_run_status", create_type=False),
        nullable=False,
        server_default=AgentRunStatus.running.value,
    )
    steps_used: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    max_steps: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="5"
    )
    assistant_message_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chat_messages.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
