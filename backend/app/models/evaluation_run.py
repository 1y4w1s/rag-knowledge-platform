"""EvaluationRun — 评测运行记录（企业评测体系 Phase 4-1）。
存储每次评测的结果，支持历史趋势和回归检测。
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class EvaluationRun(Base):
    """一次评测运行的完整记录。"""

    __tablename__ = "evaluation_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    run_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    dataset_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    mode: Mapped[str] = mapped_column(
        String(32), nullable=False, default="retrieval",
        comment="retrieval | generation | full",
    )
    git_sha: Mapped[str | None] = mapped_column(String(64), nullable=True)
    total_queries: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skipped: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # 检索指标（JSON）
    hit_at_1: Mapped[float | None] = mapped_column(Float, nullable=True)
    hit_at_3: Mapped[float | None] = mapped_column(Float, nullable=True)
    hit_at_5: Mapped[float | None] = mapped_column(Float, nullable=True)
    mrr: Mapped[float | None] = mapped_column(Float, nullable=True)
    precision_at_k: Mapped[float | None] = mapped_column(Float, nullable=True)
    recall_at_k: Mapped[float | None] = mapped_column(Float, nullable=True)
    map_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    correct_rejection_rate: Mapped[float | None] = mapped_column(Float, nullable=True)

    # 生成指标（JSON）
    generation_correctness: Mapped[float | None] = mapped_column(Float, nullable=True)
    generation_faithfulness: Mapped[float | None] = mapped_column(Float, nullable=True)
    generation_hallucination_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    generation_citation_accuracy: Mapped[float | None] = mapped_column(Float, nullable=True)

    # 延迟
    p50_latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    p95_latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    p99_latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    throughput_qps: Mapped[float | None] = mapped_column(Float, nullable=True)

    # 分 domain 下钻
    breakdown_domain: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    breakdown_type: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # 元数据
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    triggered_by: Mapped[str | None] = mapped_column(
        String(32), nullable=True, default="manual",
        comment="manual | ci_fast | ci_full | nightly",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow,
    )
