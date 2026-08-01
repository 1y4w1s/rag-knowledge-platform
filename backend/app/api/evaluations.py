"""评测 API 路由（企业评测体系 Phase 4-1）。
提供历史趋势查询、最新结果、运行记录管理。
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser, get_current_user
from app.models.evaluation_run import EvaluationRun
from app.schemas.evaluation import (
    EvaluationRunCreate,
    EvaluationRunOut,
    EvaluationTrend,
    TrendPoint,
)
from app.services.audit.log import write_audit_log

router = APIRouter(prefix="/api/v1/evaluations", tags=["evaluations"])


@router.get("/latest", response_model=EvaluationRunOut | None)
async def get_latest(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
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
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
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
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
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
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
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

    await write_audit_log(
        db,
        action="evaluation_run.create",
        actor_user_id=current_user.id,
        resource_type="evaluation_run",
        resource_id=run.id,
        metadata={"dataset": data.dataset_name, "mode": data.mode, "run_id": data.run_id},
    )
    await db.commit()

    return run


@router.get("/runs", response_model=list[EvaluationRunOut])
async def list_runs(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
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


# ═══════════════════════════════════════════════════════════════
# RAGAS 评分（从 benchmark_results/*.json 读取）
# ═══════════════════════════════════════════════════════════════

BENCHMARK_DIR = Path(__file__).resolve().parents[3] / "benchmark_results"


def _ragas_dataset_order(name: str) -> int:
    """数据集排序：已有数据的排序在前。"""
    if "golden" in name:
        return 0
    if "enterprise" in name:
        return 1
    if "baseline" in name:
        return 2
    return 99


def _parse_timestamp(ts: str | float | int) -> str:
    """解析 JSON 中的 timestamp（可能是 ISO 字符串或 Unix 秒）。"""
    if isinstance(ts, (int, float)):
        return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
    try:
        return datetime.fromisoformat(ts.replace("_", "T")).isoformat()
    except Exception:
        return str(ts)


@router.get("/ragas-scores")
async def get_ragas_scores(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
):
    """扫描 benchmark_results/ 目录，读取已有 JSON 文件中的 RAGAS / faithfulness 指标。

    返回按数据集分组的结果，每项含 metrics 和历次运行记录。
    """
    bench_dir = BENCHMARK_DIR
    if not bench_dir.is_dir():
        return {"datasets": [], "metrics_available": []}

    # 收集所有 JSON 文件
    json_files = sorted(bench_dir.glob("*.json"), reverse=True)

    # 按数据集分组
    datasets_map: dict[str, dict[str, Any]] = {}

    for fp in json_files:
        try:
            data = json.loads(fp.read_text("utf-8"))
        except Exception:
            continue

        ds_name = data.get("dataset", fp.stem)

        # 提取统一字段名（不同 JSON 格式可能不同）
        total = data.get("total", data.get("total_in_dataset", 0))
        valid = data.get("valid", data.get("total", 0))
        skipped = data.get("skipped", 0)

        faithfulness = data.get("avg_faithfulness") or data.get("faithfulness_avg")
        hallucination = data.get("avg_hallucination_rate") or data.get("hallucination_avg")

        # 检查嵌套在 summary 下的字段
        if faithfulness is None:
            summary = data.get("summary", {})
            faithfulness = summary.get("faithfulness_avg") or summary.get("avg_faithfulness")
            hallucination = summary.get("hallucination_avg") or summary.get("avg_hallucination_rate")

        if faithfulness is None:
            # 尝试从 results 数组计算
            results = data.get("results") or data.get("faithfulness_judge_results")
            if results and len(results) > 0:
                f_scores = [r.get("faithfulness") for r in results if r.get("faithfulness") is not None]
                if f_scores:
                    faithfulness = sum(f_scores) / len(f_scores)
                h_scores = [r.get("hallucination_rate") for r in results if r.get("hallucination_rate") is not None]
                if h_scores:
                    hallucination = sum(h_scores) / len(h_scores)

        ts_raw = data.get("ts", fp.stat().st_mtime)
        ts_iso = _parse_timestamp(ts_raw)

        run_id = fp.stem

        # 提取数据集显示名
        display_name = ds_name.replace("_", " ").title()

        run_entry = {
            "run_id": run_id,
            "timestamp": ts_iso,
            "faithfulness": round(faithfulness, 4) if faithfulness is not None else None,
            "hallucination_rate": round(hallucination, 4) if hallucination is not None else None,
            "total": total,
            "valid": valid,
            "skipped": skipped,
            "filename": fp.name,
        }

        if ds_name not in datasets_map:
            datasets_map[ds_name] = {
                "name": ds_name,
                "display_name": display_name,
                "runs": [],
            }
        datasets_map[ds_name]["runs"].append(run_entry)

    # 排序：数据集按名称排序，运行按时间倒序
    datasets = sorted(datasets_map.values(), key=lambda d: _ragas_dataset_order(d["name"]))
    for ds in datasets:
        ds["runs"].sort(key=lambda r: r["timestamp"], reverse=True)

    # ── 读取所有 benchmark_retrieval_ragas*.json（含时间戳历史）──
    for ragas_file in sorted(bench_dir.glob("benchmark_retrieval_ragas*.json"), reverse=True):
        try:
            ragas_data = json.loads(ragas_file.read_text("utf-8"))
            for ds_entry in ragas_data.get("datasets", []):
                ds_retrieval = ds_entry.get("retrieval", {})
                cp = ds_retrieval.get("context_precision_avg")
                cr = ds_retrieval.get("context_recall_avg")
                if cp is not None or cr is not None:
                    ds_name = ds_entry.get("dataset_name", "unknown")
                    # 找到或创建数据集条目
                    ds_obj = None
                    for d in datasets:
                        if d["name"] == ds_name:
                            ds_obj = d
                            break
                    if ds_obj is None:
                        ds_obj = {
                            "name": ds_name,
                            "display_name": ds_name.replace("/", " / ").title(),
                            "runs": [],
                        }
                        datasets.append(ds_obj)
                    # 添加 RAGAS 运行条目
                    ds_obj["runs"].append({
                        "run_id": f"ragas_{ragas_file.stem}",
                        "timestamp": ragas_data.get("generated_at", ""),
                        "faithfulness": None,
                        "hallucination_rate": None,
                        "context_precision": round(cp, 4) if cp is not None else None,
                        "context_recall": round(cr, 4) if cr is not None else None,
                        "total": ds_entry.get("total_queries", 0),
                        "valid": ds_entry.get("total_queries", 0),
                        "skipped": ds_entry.get("skipped", 0),
                        "filename": ragas_file.name,
                    })
        except Exception as e:
            pass  # 静默忽略

    return {
        "datasets": datasets,
        "metrics_available": ["faithfulness", "hallucination_rate", "context_precision", "context_recall"],
        "context_datasets_available": [d["name"] for d in datasets if any(
            r.get("context_precision") is not None for r in d.get("runs", [])
        )],
        "note": "" if any(d["name"].startswith("beir/") for d in datasets)
                else "当前仅展示 Faithfulness 指标。运行 RAGAS + BEIR 评测后可查看 context_precision / context_recall。",
    }
