"""Dashboard 统计 Pydantic 模型（Wave 2.5 / DB-API W1 / EW-C3 RAG 指标）。"""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class DocumentStatusCounts(BaseModel):
    """各状态文档数量（TECH-2B）。"""

    queued: int = 0
    processing: int = 0
    completed: int = 0
    failed: int = 0


class DashboardActivity(BaseModel):
    """Dashboard 最近动态条目（D-5 前 stub 结构预留）。"""

    type: str
    title: str
    kb_id: uuid.UUID
    doc_id: uuid.UUID | None = None
    created_at: datetime


class DashboardStatsResponse(BaseModel):
    """GET /dashboard/stats 响应（TECH-2B / TECH-5）。"""

    scope: Literal["personal", "organization"]
    knowledge_base_count: int = Field(ge=0)
    document_count: int = Field(ge=0)
    documents_by_status: DocumentStatusCounts
    total_chunk_count: int = Field(ge=0)
    avg_processing_duration_seconds: float | None = Field(
        default=None,
        description="已完成文档平均入库耗时（秒）；无样本时为 null",
    )
    ingestion_success_rate: float | None = Field(
        default=None,
        description="completed / (completed + failed) × 100；无终态文档时为 null",
    )
    chat_message_count: int = Field(
        default=0,
        ge=0,
        description="Wave 3 对话表就绪前恒为 0",
    )
    member_count: int | None = Field(
        default=None,
        ge=0,
        description="团队成员数；个人版为 null",
    )
    recent_kb_id: uuid.UUID | None = Field(
        default=None,
        description="可见范围内最近活跃资料库 id；无库时为 null",
    )
    recent_activities: list[DashboardActivity] = Field(
        default_factory=list,
        description="最近动态（D-5 前恒为空数组）",
    )
    golden_hit_rate_percent: float | None = Field(
        default=None,
        description="golden_qa Hit@3 生产基线命中率（%，EW-C2 rag_baseline.py）",
    )
    golden_baseline_evaluated_at: datetime | None = Field(
        default=None,
        description="golden 生产基线最近评估时间（UTC）",
    )
    avg_retrieval_latency_ms: float | None = Field(
        default=None,
        description="近 7 日 workspace 内 assistant 消息平均检索耗时（ms）；无样本 null",
    )
    retrieval_latency_sample_count: int = Field(
        default=0,
        ge=0,
        description="参与 avg_retrieval_latency_ms 计算的 assistant 消息数",
    )
    document_retry_count_7d: int = Field(
        default=0,
        ge=0,
        description="近 7 日 visible 范围内 document.retry 审计条数（Plan-3E-6b / ORG-3.5）",
    )
    storage_cleanup_failure_count: int = Field(
        default=0,
        ge=0,
        description="visible 范围内 storage.cleanup_failed 审计累计条数（Plan-3E-6b / ORG-3.5）",
    )
