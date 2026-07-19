"""评测 API 路由（企业评测体系 Phase 4-1）。
提供历史趋势查询、最新结果、运行记录管理。
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.evaluation_run import EvaluationRun
from app.schemas.evaluation import (
    EvaluationRunCreate,
    EvaluationRunOut,
    EvaluationTrend,
    TrendPoint,
)

router = APIRouter(prefix="/api/v1/evaluations", tags=["evaluations"])


@router.get("/latest", response_model=EvaluationRunOut | None)
async def get_latest(
    dataset: str = Query("golden_qa", description="数据集名称"),
    mode: str = Query("retrieval", description="retrieval | generation | full"),
    db: AsyncSession = Depends(get_db),
):
    """获取指定数据集的最新评测结果。"""
    result = await db.execute(
        select(EvaluationRun)
        .where(EvaluationRun.dataset_name == dataset)
        .where(EvaluationRun.mode == mode)
        .order_by(desc(EvaluationRun.created_at))
        .limit(1)
    )
    run = result.scalar_one_or_none()
    return run


@router.get("/trends", response_model=EvaluationTrend)
async def get_trends(
    dataset: str = Query("golden_qa", description="数据集名称"),
    metric: str = Query("hit_at_3", description="指标名"),
    last: int = Query(30, ge=1, le=365, description="最近 N 次"),
    db: AsyncSession = Depends(get_db),
):
    """获取指定指标的历史趋势。"""
    result = await db.execute(
        select(EvaluationRun)
        .where(EvaluationRun.dataset_name == dataset)
        .where(EvaluationRun.hit_at_3.isnot(None))
        .order_by(desc(EvaluationRun.created_at))
        .limit(last)
    )
    runs = result.scalars().all()

    points = []
    for r in reversed(runs):
        val = getattr(r, metric, None)
        if val is not None:
            points.append(TrendPoint(
                run_id=r.run_id,
                value=round(float(val), 4),
                created_at=r.created_at,
                triggered_by=r.triggered_by,
            ))

    avg_val = sum(p.value for p in points) / len(points) if points else 0.0
    return EvaluationTrend(
        dataset=dataset, metric=metric, total_runs=len(runs),
        points=points, average=round(avg_val, 4),
    )


@router.get("/compare")
async def compare_runs(
    since: str = Query(..., description="ISO 时间戳，与此后的最新结果对比"),
    dataset: str = Query("golden_qa", description="数据集"),
    db: AsyncSession = Depends(get_db),
):
    """与指定时间点相比的变化。"""
    try:
        since_dt = datetime.fromisoformat(since)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid timestamp format")

    # 基线 = 时间点之前的最新一次
    base = await db.execute(
        select(EvaluationRun)
        .where(EvaluationRun.dataset_name == dataset)
        .where(EvaluationRun.created_at <= since_dt)
        .order_by(desc(EvaluationRun.created_at))
        .limit(1)
    )
    baseline = base.scalar_one_or_none()
    if not baseline:
        raise HTTPException(status_code=404, detail="No baseline found before %s" % since)

    # 当前 = 时间点之后的最新一次
    curr = await db.execute(
        select(EvaluationRun)
        .where(EvaluationRun.dataset_name == dataset)
        .where(EvaluationRun.created_at > since_dt)
        .order_by(desc(EvaluationRun.created_at))
        .limit(1)
    )
    current = curr.scalar_one_or_none()
    if not current:
        raise HTTPException(status_code=404, detail="No runs found after %s" % since)

    # 计算差异
    metrics = ["hit_at_1", "hit_at_3", "hit_at_5", "mrr", "precision_at_k",
               "recall_at_k", "map_score", "correct_rejection_rate"]
    diffs = {}
    for m in metrics:
        bv = getattr(baseline, m, None)
        cv = getattr(current, m, None)
        if bv is not None and cv is not None:
            diffs[m] = round(float(cv) - float(bv), 4)

    return {
        "baseline_run_id": baseline.run_id,
        "baseline_at": baseline.created_at.isoformat(),
        "current_run_id": current.run_id,
        "current_at": current.created_at.isoformat(),
        "differences": diffs,
    }


@router.post("/runs", response_model=EvaluationRunOut, status_code=201)
async def create_run(
    data: EvaluationRunCreate,
    db: AsyncSession = Depends(get_db),
):
    """手动记录一次评测运行结果。"""
    run = EvaluationRun(
        id=uuid.uuid4(),
        run_id=data.run_id,
        dataset_name=data.dataset_name,
        mode=data.mode,
        git_sha=data.git_sha,
        total_queries=data.total_queries,
        skipped=data.skipped,
        hit_at_1=data.hit_at_1,
        hit_at_3=data.hit_at_3,
        hit_at_5=data.hit_at_5,
        mrr=data.mrr,
        precision_at_k=data.precision_at_k,
        recall_at_k=data.recall_at_k,
        map_score=data.map_score,
        correct_rejection_rate=data.correct_rejection_rate,
        generation_correctness=data.generation_correctness,
        generation_faithfulness=data.generation_faithfulness,
        generation_hallucination_rate=data.generation_hallucination_rate,
        generation_citation_accuracy=data.generation_citation_accuracy,
        p50_latency_ms=data.p50_latency_ms,
        p95_latency_ms=data.p95_latency_ms,
        p99_latency_ms=data.p99_latency_ms,
        throughput_qps=data.throughput_qps,
        breakdown_domain=data.breakdown_domain,
        breakdown_type=data.breakdown_type,
        notes=data.notes,
        triggered_by=data.triggered_by or "api",
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)
    return run


@router.get("/runs", response_model=list[EvaluationRunOut])
async def list_runs(
    dataset: str | None = Query(None),
    mode: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """列出评测运行历史。"""
    stmt = select(EvaluationRun).order_by(desc(EvaluationRun.created_at))
    if dataset:
        stmt = stmt.where(EvaluationRun.dataset_name == dataset)
    if mode:
        stmt = stmt.where(EvaluationRun.mode == mode)
    stmt = stmt.limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()
