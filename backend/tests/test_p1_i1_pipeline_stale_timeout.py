"""M8-I1：pipeline 行锁原子认领 + processing 超龄重认领 + outcome 返回值。"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.audit_log import AuditLog
from app.models.document import Document
from app.models.enums import DocumentStatus
from app.services.ingestion import pipeline as pipeline_mod
from app.services.ingestion.pipeline import (
    IngestionOutcome,
    _claim_document,
    process_document_ingestion,
)
from app.services.ingestion.stale_scan import (
    StaleReport,
    apply_stale_mark_failed,
    is_stale,
    scan_stale_ingestion,
)
from app.services.ingestion.types import ParsedBlock
from tests.conftest import create_test_kb as _create_kb

_NOW = datetime(2026, 8, 10, 8, 0, 0, tzinfo=timezone.utc)


async def _kb_context(
    client: AsyncClient,
    register_and_login: Any,
) -> tuple[UUID, UUID]:
    headers, user = await register_and_login(prefix="m8i1")
    kb = await _create_kb(client, headers, user, name="M8-I1 超龄兜底")
    return UUID(kb["id"]), UUID(user["id"])


async def _seed_doc(
    kb_id: UUID,
    uploaded_by: UUID,
    tmp_path: Path,
    *,
    status: DocumentStatus = DocumentStatus.queued,
    processing_started_at: datetime | None = None,
    deleted_at: datetime | None = None,
    valid_file: bool = True,
) -> UUID:
    doc_id = uuid.uuid4()
    storage = tmp_path / f"{doc_id}.md"
    if valid_file:
        storage.write_text(
            "# 测试制度\n\n"
            "第一条：员工每年可申请年假 10 天，需要提前两周申请，"
            "并且按照公司流程填写休假申请单，经主管审批后生效。\n\n"
            "第二条：出差需提前提交差旅申请，报销标准按公司最新制度执行。",
            encoding="utf-8",
        )
    async with SessionLocal() as db:
        db.add(
            Document(
                id=doc_id,
                kb_id=kb_id,
                filename="m8-i1.md",
                file_type="md",
                file_size=storage.stat().st_size if valid_file else 1,
                storage_path=str(storage),
                status=status,
                processing_started_at=processing_started_at,
                deleted_at=deleted_at,
                uploaded_by=uploaded_by,
            )
        )
        await db.commit()
    return doc_id


def _fake_parse(calls: dict[str, int]):
    def _parse(*_args: Any, **_kwargs: Any) -> list[ParsedBlock]:
        calls["count"] += 1
        return [
            ParsedBlock(
                content=(
                    "这是一段足够长的测试正文，用于并发场景下验证解析只执行一次。"
                    "入库管道按结构优先切分并写入文档切片。"
                ),
                section_title="测试",
                heading_path="测试",
            )
        ]

    return _parse


@pytest.mark.asyncio
async def test_queued_claim_atomic_then_second_skips(
    client: AsyncClient,
    register_and_login: Any,
    tmp_path: Path,
) -> None:
    """queued 连续两次认领：第一次 claimed + processing，第二次 skipped。"""
    kb_id, user_id = await _kb_context(client, register_and_login)
    doc_id = await _seed_doc(kb_id, user_id, tmp_path)

    async with SessionLocal() as db:
        doc, kind = await _claim_document(
            db,
            document_id=doc_id,
            started_at=_NOW,
            stale_minutes=120,
        )
    assert kind == "claimed"
    assert doc is not None
    assert doc.status == DocumentStatus.processing

    async with SessionLocal() as db:
        _doc, kind = await _claim_document(
            db,
            document_id=doc_id,
            started_at=_NOW + timedelta(seconds=1),
            stale_minutes=120,
        )
    assert kind == "skipped"
    assert _doc is not None
    assert _doc.status == DocumentStatus.processing

    async with SessionLocal() as db:
        row = await db.get(Document, doc_id)
        assert row is not None
        row.status = DocumentStatus.queued
        row.processing_started_at = None
        await db.commit()

    outcome = await process_document_ingestion(doc_id)
    assert outcome == IngestionOutcome.completed
    async with SessionLocal() as db:
        row = await db.get(Document, doc_id)
        assert row is not None
        assert row.status == DocumentStatus.completed


@pytest.mark.asyncio
async def test_concurrent_calls_parse_once(
    client: AsyncClient,
    register_and_login: Any,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """asyncio.gather 并发两次 process：解析只执行 1 次，最终 completed。"""
    kb_id, user_id = await _kb_context(client, register_and_login)
    doc_id = await _seed_doc(kb_id, user_id, tmp_path)
    calls = {"count": 0}
    monkeypatch.setattr(pipeline_mod, "parse_document", _fake_parse(calls))

    outcomes = await asyncio.gather(
        process_document_ingestion(doc_id),
        process_document_ingestion(doc_id),
    )
    assert calls["count"] == 1
    assert IngestionOutcome.completed in outcomes
    assert IngestionOutcome.skipped in outcomes
    async with SessionLocal() as db:
        row = await db.get(Document, doc_id)
        assert row is not None
        assert row.status == DocumentStatus.completed


@pytest.mark.asyncio
async def test_stale_processing_reclaimed_and_completed(
    client: AsyncClient,
    register_and_login: Any,
    tmp_path: Path,
) -> None:
    """processing 超龄：pipeline 重认领、刷新时钟、写 ingestion.stale_reclaimed 审计。"""
    kb_id, user_id = await _kb_context(client, register_and_login)
    doc_id = await _seed_doc(kb_id, user_id, tmp_path)
    started_at = datetime.now(timezone.utc)
    async with SessionLocal() as db:
        row = await db.get(Document, doc_id)
        assert row is not None
        row.status = DocumentStatus.processing
        row.processing_started_at = started_at - timedelta(minutes=121)
        await db.commit()

    outcome = await process_document_ingestion(doc_id)
    assert outcome == IngestionOutcome.completed

    async with SessionLocal() as db:
        row = await db.get(Document, doc_id)
        assert row is not None
        assert row.status == DocumentStatus.completed
        assert row.processing_started_at is not None
        assert row.processing_started_at >= started_at - timedelta(seconds=5)

    async with SessionLocal() as db:
        logs = (
            await db.scalars(
                select(AuditLog).where(
                    AuditLog.action == "ingestion.stale_reclaimed",
                    AuditLog.resource_id == doc_id,
                )
            )
        ).all()
    assert len(logs) >= 1
    log = logs[0]
    assert log.resource_type == "document"
    assert log.kb_id == kb_id
    assert log.details is not None
    assert log.details["status_before"] == "processing"
    assert log.details["clock_field"] == "processing_started_at"


@pytest.mark.asyncio
async def test_fresh_processing_skipped_without_parse(
    client: AsyncClient,
    register_and_login: Any,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """processing 未超龄：返回 skipped，解析不执行，状态保持 processing。"""
    kb_id, user_id = await _kb_context(client, register_and_login)
    doc_id = await _seed_doc(kb_id, user_id, tmp_path)
    async with SessionLocal() as db:
        row = await db.get(Document, doc_id)
        assert row is not None
        row.status = DocumentStatus.processing
        row.processing_started_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        await db.commit()

    calls = {"count": 0}
    monkeypatch.setattr(pipeline_mod, "parse_document", _fake_parse(calls))
    outcome = await process_document_ingestion(doc_id)
    assert outcome == IngestionOutcome.skipped
    assert calls["count"] == 0
    async with SessionLocal() as db:
        row = await db.get(Document, doc_id)
        assert row is not None
        assert row.status == DocumentStatus.processing


@pytest.mark.asyncio
async def test_terminal_and_soft_deleted_skipped(
    client: AsyncClient,
    register_and_login: Any,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """completed/failed/软删文档：返回 skipped，状态不变，解析不执行。"""
    kb_id, user_id = await _kb_context(client, register_and_login)
    expected: list[tuple[UUID, DocumentStatus]] = []
    for status in (DocumentStatus.completed, DocumentStatus.failed):
        doc_id = await _seed_doc(kb_id, user_id, tmp_path, status=status)
        expected.append((doc_id, status))
    soft_deleted = await _seed_doc(
        kb_id,
        user_id,
        tmp_path,
        deleted_at=_NOW,
    )
    expected.append((soft_deleted, DocumentStatus.queued))

    calls = {"count": 0}
    monkeypatch.setattr(pipeline_mod, "parse_document", _fake_parse(calls))
    for doc_id, _status in expected:
        assert await process_document_ingestion(doc_id) == IngestionOutcome.skipped

    assert calls["count"] == 0
    async with SessionLocal() as db:
        for doc_id, status in expected:
            row = await db.get(Document, doc_id)
            assert row is not None
            assert row.status == status


@pytest.mark.asyncio
async def test_pipeline_skips_after_sweeper_marked_failed(
    client: AsyncClient,
    register_and_login: Any,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """NW-12 先标 failed 后 pipeline 不重跑：返回 skipped，状态保持 failed。"""
    monkeypatch.setattr(settings, "celery_task_always_eager_local", False)
    kb_id, user_id = await _kb_context(client, register_and_login)
    doc_id = await _seed_doc(kb_id, user_id, tmp_path)
    async with SessionLocal() as db:
        row = await db.get(Document, doc_id)
        assert row is not None
        row.status = DocumentStatus.processing
        row.processing_started_at = _NOW - timedelta(minutes=121)
        await db.commit()

    async with SessionLocal() as db:
        report = await scan_stale_ingestion(
            db,
            now=_NOW,
            queued_minutes=60,
            processing_minutes=120,
        )
        our_items = [item for item in report.items if item.doc_id == doc_id]
        assert our_items
        report = StaleReport(
            items=our_items,
            scanned_at=report.scanned_at,
            queued_threshold_minutes=report.queued_threshold_minutes,
            processing_threshold_minutes=report.processing_threshold_minutes,
        )
        result = await apply_stale_mark_failed(db, report, dry_run=False)
        assert result.marked == 1

    calls = {"count": 0}
    monkeypatch.setattr(pipeline_mod, "parse_document", _fake_parse(calls))
    outcome = await process_document_ingestion(doc_id)
    assert outcome == IngestionOutcome.skipped
    assert calls["count"] == 0
    async with SessionLocal() as db:
        row = await db.get(Document, doc_id)
        assert row is not None
        assert row.status == DocumentStatus.failed


@pytest.mark.asyncio
async def test_reclaimed_doc_not_stale_to_sweeper(
    client: AsyncClient,
    register_and_login: Any,
    tmp_path: Path,
) -> None:
    """pipeline 重认领刷新 started_at 后，stale_scan.is_stale 不再命中。"""
    kb_id, user_id = await _kb_context(client, register_and_login)
    doc_id = await _seed_doc(kb_id, user_id, tmp_path)
    started_at = datetime.now(timezone.utc)
    async with SessionLocal() as db:
        row = await db.get(Document, doc_id)
        assert row is not None
        row.status = DocumentStatus.processing
        row.processing_started_at = started_at - timedelta(minutes=121)
        await db.commit()

    async with SessionLocal() as db:
        doc, kind = await _claim_document(
            db,
            document_id=doc_id,
            started_at=started_at,
            stale_minutes=120,
        )
    assert kind == "reclaimed"
    assert doc is not None
    assert doc.status == DocumentStatus.processing

    async with SessionLocal() as db:
        row = await db.get(Document, doc_id)
        assert row is not None
        hit = is_stale(
            row,
            now=started_at + timedelta(minutes=1),
            queued_minutes=60,
            processing_minutes=120,
        )
    assert hit is None


@pytest.mark.asyncio
async def test_process_returns_completed_failed_skipped(
    client: AsyncClient,
    register_and_login: Any,
    tmp_path: Path,
) -> None:
    """返回值映射：正常 completed；缺文件 failed；新鲜 processing skipped。"""
    kb_id, user_id = await _kb_context(client, register_and_login)

    ok_doc = await _seed_doc(kb_id, user_id, tmp_path)
    assert (
        await process_document_ingestion(ok_doc)
        == IngestionOutcome.completed
    )

    missing_doc = await _seed_doc(
        kb_id,
        user_id,
        tmp_path,
        valid_file=False,
    )
    assert await process_document_ingestion(missing_doc) == IngestionOutcome.failed

    fresh_doc = await _seed_doc(kb_id, user_id, tmp_path)
    async with SessionLocal() as db:
        row = await db.get(Document, fresh_doc)
        assert row is not None
        row.status = DocumentStatus.processing
        row.processing_started_at = datetime.now(timezone.utc)
        await db.commit()
    assert (
        await process_document_ingestion(fresh_doc)
        == IngestionOutcome.skipped
    )
