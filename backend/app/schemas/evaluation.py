"""评测 API 数据模型（企业评测体系 Phase 4-1）。"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class EvaluationRunCreate(BaseModel):
    """创建评测运行记录。"""
    run_id: str
    dataset_name: str
    mode: str = "retrieval"
    git_sha: str | None = None
    total_queries: int = 0
    skipped: int = 0
    hit_at_1: float | None = None
    hit_at_3: float | None = None
    hit_at_5: float | None = None
    mrr: float | None = None
    precision_at_k: float | None = None
    recall_at_k: float | None = None
    map_score: float | None = None
    correct_rejection_rate: float | None = None
    generation_correctness: float | None = None
    generation_faithfulness: float | None = None
    generation_hallucination_rate: float | None = None
    generation_citation_accuracy: float | None = None
    p50_latency_ms: float | None = None
    p95_latency_ms: float | None = None
    p99_latency_ms: float | None = None
    throughput_qps: float | None = None
    breakdown_domain: dict[str, Any] | None = None
    breakdown_type: dict[str, Any] | None = None
    notes: str | None = None
    triggered_by: str | None = None


class EvaluationRunOut(BaseModel):
    """评测运行记录（输出）。"""
    id: uuid.UUID
    run_id: str
    dataset_name: str
    mode: str
    git_sha: str | None
    total_queries: int
    skipped: int
    hit_at_1: float | None
    hit_at_3: float | None
    hit_at_5: float | None
    mrr: float | None
    precision_at_k: float | None
    recall_at_k: float | None
    map_score: float | None
    correct_rejection_rate: float | None
    generation_correctness: float | None
    generation_faithfulness: float | None
    generation_hallucination_rate: float | None
    generation_citation_accuracy: float | None
    p50_latency_ms: float | None
    p95_latency_ms: float | None
    p99_latency_ms: float | None
    throughput_qps: float | None
    breakdown_domain: dict[str, Any] | None
    breakdown_type: dict[str, Any] | None
    notes: str | None
    triggered_by: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class TrendPoint(BaseModel):
    """趋势图上的一个数据点。"""
    run_id: str
    value: float
    created_at: datetime
    triggered_by: str | None = None


class EvaluationTrend(BaseModel):
    """指标趋势。"""
    dataset: str
    metric: str
    total_runs: int
    points: list[TrendPoint]
    average: float
