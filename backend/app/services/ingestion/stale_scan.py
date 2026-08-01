"""NW-12：超龄 queued/processing 扫描；干跑默认；apply 标 failed。

v1 仅年龄闸（无 celery_task_id）；不上 Beat；不做自动重入队。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.document import Document
from app.models.enums import DocumentStatus
from app.services.audit.log import write_audit_log
from app.services.ingestion.progress import clear_progress_fields

STALE_FAILED_MSG = "入库任务已超时或与队列脱节，请在详情页重试"
_EAGER_APPLY_BLOCKED = (
    "CELERY_TASK_ALWAYS_EAGER_LOCAL=true：拒绝 --apply（仅允许干跑）。"
    "生产请关 eager 后再标 failed。"
)


@dataclass(frozen=True)
class StaleItem:
    doc_id: UUID
    kb_id: UUID
    status: str
    filename: str
    age_seconds: float
    clock_field: str


@dataclass
class StaleReport:
    items: list[StaleItem] = field(default_factory=list)
    scanned_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    queued_threshold_minutes: float = 60.0
    processing_threshold_minutes: float = 120.0


@dataclass
class ApplyResult:
    dry_run: bool
    marked: int = 0
    skipped: int = 0
    errors: int = 0
    blocked_reason: str | None = None
    items: list[dict[str, Any]] = field(default_factory=list)


def _age_anchor(doc: Document) -> tuple[datetime | None, str]:
    if doc.status == DocumentStatus.processing:
        if doc.processing_started_at is not None:
            return doc.processing_started_at, "processing_started_at"
        if doc.updated_at is not None:
            return doc.updated_at, "updated_at"
        return doc.created_at, "created_at"
    if doc.updated_at is not None:
        return doc.updated_at, "updated_at"
    return doc.created_at, "created_at"


def _ensure_aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def is_stale(
    doc: Document,
    *,
    now: datetime,
    queued_minutes: float,
    processing_minutes: float,
) -> StaleItem | None:
    if doc.deleted_at is not None:
        return None
    if doc.status not in (DocumentStatus.queued, DocumentStatus.processing):
        return None
    anchor, clock_field = _age_anchor(doc)
    if anchor is None:
        return None
    age = now - _ensure_aware(anchor)
    threshold = (
        timedelta(minutes=processing_minutes)
        if doc.status == DocumentStatus.processing
        else timedelta(minutes=queued_minutes)
    )
    if age < threshold:
        return None
    return StaleItem(
        doc_id=doc.id,
        kb_id=doc.kb_id,
        status=doc.status.value,
        filename=doc.filename,
        age_seconds=age.total_seconds(),
        clock_field=clock_field,
    )


async def scan_stale_ingestion(
    db: AsyncSession,
    *,
    now: datetime | None = None,
    queued_minutes: float | None = None,
    processing_minutes: float | None = None,
) -> StaleReport:
    """查出超龄 queued/processing（不含软删）。"""
    scanned_at = now or datetime.now(timezone.utc)
    q_min = (
        settings.ingest_stale_queued_minutes
        if queued_minutes is None
        else queued_minutes
    )
    p_min = (
        settings.ingest_stale_processing_minutes
        if processing_minutes is None
        else processing_minutes
    )
    result = await db.execute(
        select(Document).where(
            Document.deleted_at.is_(None),
            Document.status.in_(
                (DocumentStatus.queued, DocumentStatus.processing)
            ),
        )
    )
    items = [
        hit
        for doc in result.scalars().all()
        if (
            hit := is_stale(
                doc,
                now=scanned_at,
                queued_minutes=q_min,
                processing_minutes=p_min,
            )
        )
        is not None
    ]
    items.sort(key=lambda x: x.age_seconds, reverse=True)
    return StaleReport(
        items=items,
        scanned_at=scanned_at,
        queued_threshold_minutes=q_min,
        processing_threshold_minutes=p_min,
    )


def report_to_dict(report: StaleReport) -> dict[str, Any]:
    return {
        "scanned_at": report.scanned_at.isoformat(),
        "queued_threshold_minutes": report.queued_threshold_minutes,
        "processing_threshold_minutes": report.processing_threshold_minutes,
        "found": len(report.items),
        "items": [
            {
                "doc_id": str(i.doc_id),
                "kb_id": str(i.kb_id),
                "status": i.status,
                "filename": i.filename,
                "age_seconds": round(i.age_seconds, 1),
                "clock_field": i.clock_field,
            }
            for i in report.items
        ],
    }


async def apply_stale_mark_failed(
    db: AsyncSession,
    report: StaleReport,
    *,
    dry_run: bool = True,
    max_apply: int | None = None,
    now: datetime | None = None,
    allow_eager_apply: bool = False,
) -> ApplyResult:
    """干跑或将候选标 failed。eager 默认禁止 apply。"""
    limit = (
        settings.ingest_stale_max_apply if max_apply is None else max_apply
    )
    applied_at = now or datetime.now(timezone.utc)
    if (
        not dry_run
        and settings.celery_task_always_eager_local
        and not allow_eager_apply
    ):
        return ApplyResult(
            dry_run=False,
            blocked_reason=_EAGER_APPLY_BLOCKED,
            errors=1,
        )

    out = ApplyResult(dry_run=dry_run)
    candidates = report.items[: max(0, limit)]
    out.skipped = max(0, len(report.items) - len(candidates))

    if dry_run:
        out.items = [
            {
                "doc_id": str(i.doc_id),
                "status": i.status,
                "action": "would_mark_failed",
            }
            for i in candidates
        ]
        await write_audit_log(
            db,
            action="ingestion.stale_scan",
            metadata={
                "dry_run": True,
                "found": len(report.items),
                "would_mark": len(candidates),
                "skipped_over_limit": out.skipped,
            },
        )
        await db.commit()
        return out

    for item in candidates:
        doc = await db.get(Document, item.doc_id)
        if doc is None or doc.deleted_at is not None:
            out.errors += 1
            out.items.append(
                {
                    "doc_id": str(item.doc_id),
                    "action": "error",
                    "error": "missing_or_deleted",
                }
            )
            continue
        if doc.status not in (
            DocumentStatus.queued,
            DocumentStatus.processing,
        ):
            out.skipped += 1
            out.items.append(
                {
                    "doc_id": str(item.doc_id),
                    "action": "skipped",
                    "error": f"status={doc.status.value}",
                }
            )
            continue

        status_before = doc.status.value
        doc.status = DocumentStatus.failed
        doc.error_message = STALE_FAILED_MSG
        doc.processing_completed_at = applied_at
        clear_progress_fields(doc)
        await write_audit_log(
            db,
            action="ingestion.stale_marked_failed",
            resource_type="document",
            resource_id=doc.id,
            kb_id=doc.kb_id,
            metadata={
                "filename": doc.filename,
                "status_before": status_before,
                "age_seconds": round(item.age_seconds, 1),
                "clock_field": item.clock_field,
            },
        )
        out.marked += 1
        out.items.append(
            {
                "doc_id": str(doc.id),
                "status_before": status_before,
                "action": "marked_failed",
            }
        )

    await write_audit_log(
        db,
        action="ingestion.stale_scan",
        metadata={
            "dry_run": False,
            "found": len(report.items),
            "marked": out.marked,
            "skipped": out.skipped,
            "errors": out.errors,
        },
    )
    await db.commit()
    return out
