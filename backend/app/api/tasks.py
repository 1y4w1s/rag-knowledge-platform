"""任务状态查询路由（Celery）。"""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from app.core.deps import CurrentUser, get_current_user
from app.services.ingestion.celery_app import celery_app

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("/{task_id}")
async def get_task_status(
    task_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
):
    """查询 Celery 任务状态。需要认证。"""
    # 校验 task_id 格式
    try:
        UUID(task_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="无效的任务 ID 格式")

    result = celery_app.AsyncResult(task_id)

    if result.state == "PENDING":
        # Celery 不保留 PENDING 任务的记录
        return {
            "task_id": task_id,
            "status": "pending",
            "result": None,
            "error": None,
        }

    if result.state == "FAILURE":
        return {
            "task_id": task_id,
            "status": "failed",
            "result": None,
            "error": str(result.result) if result.result else "未知错误",
        }

    if result.state == "SUCCESS":
        return {
            "task_id": task_id,
            "status": "success",
            "result": result.result,
            "error": None,
        }

    return {
        "task_id": task_id,
        "status": result.state.lower(),
        "result": None,
        "error": None,
    }
