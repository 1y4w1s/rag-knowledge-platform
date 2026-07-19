"""Celery 应用实例 — 用于异步文档 ingestion。"""
from __future__ import annotations

from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "ruige",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_always_eager=settings.celery_task_always_eager_local,
    task_track_started=True,
    task_store_errors_even_if_ignored=True,
    worker_max_tasks_per_child=100,
)

# 自动发现 Task
celery_app.autodiscover_tasks(["app.services.ingestion"], force=True)
