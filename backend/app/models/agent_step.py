"""agent_steps 表（G3-0.1 · Agent 单步 tool 执行记录）。"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import ENUM, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.enums import AgentStepStatus


class AgentStep(Base):
    __tablename__ = "agent_steps"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agent_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    step_index: Mapped[int] = mapped_column(Integer, nullable=False)
    tool_name: Mapped[str] = mapped_column(String(64), nullable=False)
    args_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    result_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    ok: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[AgentStepStatus] = mapped_column(
        ENUM(AgentStepStatus, name="agent_step_status", create_type=False),
        nullable=False,
        server_default=AgentStepStatus.running.value,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
