"""NW-12：超龄 queued/processing 扫描 · 干跑默认 · apply 标 failed。

假时钟 + 内存假 Session，不依赖本机 Postgres 密码。
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from app.core.config import settings
from app.models.audit_log import AuditLog
from app.models.document import Document
from app.models.enums import DocumentStatus
from app.services.ingestion.stale_scan import (
    STALE_FAILED_MSG,
    apply_stale_mark_failed,
    is_stale,
    scan_stale_ingestion,
)

_NOW = datetime(2026, 7, 22, 8, 0, 0, tzinfo=timezone.utc)


def _doc(
    *,
    status: DocumentStatus,
    updated_at: datetime | None = None,
    created_at: datetime | None = None,
    processing_started_at: datetime | None = None,
    deleted_at: datetime | None = None,
    filename: str = "stale.txt",
) -> Document:
    return Document(
        id=uuid.uuid4(),
        kb_id=uuid.uuid4(),
        filename=filename,
        file_type="txt",
        file_size=1,
        storage_path="/tmp/x.txt",
        status=status,
        created_at=created_at or _NOW,
        updated_at=updated_at or created_at or _NOW,
        processing_started_at=processing_started_at,
        deleted_at=deleted_at,
    )


class _ScalarResult:
    def __init__(self, rows: list[Document]) -> None:
        self._rows = rows

    def all(self) -> list[Document]:
        return list(self._rows)


class _ExecResult:
    def __init__(self, rows: list[Document]) -> None:
        self._rows = rows

    def scalars(self) -> _ScalarResult:
        return _ScalarResult(self._rows)


class FakeSession:
    """最小 AsyncSession 替身：execute / get / add / flush / commit。"""

    def __init__(self, docs: list[Document]) -> None:
        self.docs = {d.id: d for d in docs}
        self.added: list[Any] = []
        self.commits = 0

    async def execute(self, _stmt: Any) -> _ExecResult:
        rows = [
            d
            for d in self.docs.values()
            if d.deleted_at is None
            and d.status in (DocumentStatus.queued, DocumentStatus.processing)
        ]
        return _ExecResult(rows)

    async def get(self, _model: Any, doc_id: uuid.UUID) -> Document | None:
        return self.docs.get(doc_id)

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def flush(self) -> None:
        return None

    async def commit(self) -> None:
        self.commits += 1


def test_is_stale_queued_over_threshold() -> None:
    doc = _doc(
        status=DocumentStatus.queued,
        updated_at=_NOW - timedelta(minutes=61),
    )
    hit = is_stale(doc, now=_NOW, queued_minutes=60, processing_minutes=120)
    assert hit is not None
    assert hit.status == "queued"
    assert hit.clock_field == "updated_at"


def test_is_stale_queued_under_threshold() -> None:
    doc = _doc(
        status=DocumentStatus.queued,
        updated_at=_NOW - timedelta(minutes=30),
    )
    assert (
        is_stale(doc, now=_NOW, queued_minutes=60, processing_minutes=120)
        is None
    )


def test_is_stale_processing_uses_started_at() -> None:
    doc = _doc(
        status=DocumentStatus.processing,
        updated_at=_NOW - timedelta(minutes=10),
        processing_started_at=_NOW - timedelta(minutes=121),
    )
    hit = is_stale(doc, now=_NOW, queued_minutes=60, processing_minutes=120)
    assert hit is not None
    assert hit.clock_field == "processing_started_at"


def test_is_stale_skips_soft_deleted() -> None:
    doc = _doc(
        status=DocumentStatus.queued,
        updated_at=_NOW - timedelta(hours=5),
        deleted_at=_NOW - timedelta(hours=1),
    )
    assert (
        is_stale(doc, now=_NOW, queued_minutes=60, processing_minutes=120)
        is None
    )


@pytest.mark.asyncio
async def test_scan_finds_stale_queued() -> None:
    stale = _doc(
        status=DocumentStatus.queued,
        updated_at=_NOW - timedelta(minutes=90),
        filename="old.txt",
    )
    fresh = _doc(
        status=DocumentStatus.queued,
        updated_at=_NOW - timedelta(minutes=10),
        filename="fresh.txt",
    )
    db = FakeSession([stale, fresh])
    report = await scan_stale_ingestion(
        db,  # type: ignore[arg-type]
        now=_NOW,
        queued_minutes=60,
        processing_minutes=120,
    )
    ids = {i.doc_id for i in report.items}
    assert stale.id in ids
    assert fresh.id not in ids


@pytest.mark.asyncio
async def test_dry_run_does_not_change_status() -> None:
    doc = _doc(
        status=DocumentStatus.processing,
        processing_started_at=_NOW - timedelta(minutes=200),
        updated_at=_NOW - timedelta(minutes=200),
    )
    db = FakeSession([doc])
    report = await scan_stale_ingestion(
        db,  # type: ignore[arg-type]
        now=_NOW,
        queued_minutes=60,
        processing_minutes=120,
    )
    result = await apply_stale_mark_failed(
        db,  # type: ignore[arg-type]
        report,
        dry_run=True,
    )
    assert result.dry_run is True
    assert result.marked == 0
    assert doc.status == DocumentStatus.processing
    assert any(
        isinstance(a, AuditLog) and a.action == "ingestion.stale_scan"
        for a in db.added
    )


@pytest.mark.asyncio
async def test_apply_marks_failed_when_not_eager(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "celery_task_always_eager_local", False)
    doc = _doc(
        status=DocumentStatus.queued,
        updated_at=_NOW - timedelta(minutes=90),
    )
    db = FakeSession([doc])
    report = await scan_stale_ingestion(
        db,  # type: ignore[arg-type]
        now=_NOW,
        queued_minutes=60,
        processing_minutes=120,
    )
    result = await apply_stale_mark_failed(
        db,  # type: ignore[arg-type]
        report,
        dry_run=False,
        max_apply=10,
    )
    assert result.blocked_reason is None
    assert result.marked == 1
    assert doc.status == DocumentStatus.failed
    assert doc.error_message == STALE_FAILED_MSG
    assert any(
        isinstance(a, AuditLog) and a.action == "ingestion.stale_marked_failed"
        for a in db.added
    )


@pytest.mark.asyncio
async def test_apply_blocked_when_eager(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "celery_task_always_eager_local", True)
    doc = _doc(
        status=DocumentStatus.queued,
        updated_at=_NOW - timedelta(minutes=90),
    )
    db = FakeSession([doc])
    report = await scan_stale_ingestion(
        db,  # type: ignore[arg-type]
        now=_NOW,
        queued_minutes=60,
        processing_minutes=120,
    )
    result = await apply_stale_mark_failed(
        db,  # type: ignore[arg-type]
        report,
        dry_run=False,
    )
    assert result.blocked_reason is not None
    assert result.marked == 0
    assert doc.status == DocumentStatus.queued
