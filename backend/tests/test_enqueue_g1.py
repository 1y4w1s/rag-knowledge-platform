"""G1 · enqueue_document_ingestion：eager / Celery 分支。"""

from __future__ import annotations

from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi import BackgroundTasks

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.document import Document
from app.models.enums import DocumentStatus
from app.services.ingestion import enqueue as enqueue_mod
from tests.conftest import create_test_kb


@pytest.mark.asyncio
async def test_enqueue_eager_uses_background_tasks(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "celery_task_always_eager_local", True)
    recorded: list = []

    async def _spy(doc_id) -> None:
        recorded.append(doc_id)

    monkeypatch.setattr(enqueue_mod, "process_document_ingestion", _spy)
    doc_id = uuid4()
    bt = BackgroundTasks()
    await enqueue_mod.enqueue_document_ingestion(doc_id, bt)
    await bt()
    assert recorded == [doc_id]


@pytest.mark.asyncio
async def test_enqueue_eager_without_bt_skips(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "celery_task_always_eager_local", True)
    called = {"delay": False}

    def _delay(_doc_id: str):
        called["delay"] = True

    monkeypatch.setattr(enqueue_mod.ingest_document_task, "delay", _delay)
    await enqueue_mod.enqueue_document_ingestion(uuid4(), None)
    assert called["delay"] is False


@pytest.mark.asyncio
async def test_enqueue_celery_calls_delay(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "celery_task_always_eager_local", False)
    seen: list[str] = []

    def _delay(doc_id: str):
        seen.append(doc_id)

    monkeypatch.setattr(enqueue_mod.ingest_document_task, "delay", _delay)
    doc_id = uuid4()
    await enqueue_mod.enqueue_document_ingestion(doc_id, None)
    assert seen == [str(doc_id)]


@pytest.mark.asyncio
async def test_enqueue_celery_with_bt_defers_delay(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "celery_task_always_eager_local", False)
    seen: list[str] = []

    def _delay(doc_id: str):
        seen.append(doc_id)

    monkeypatch.setattr(enqueue_mod.ingest_document_task, "delay", _delay)
    doc_id = uuid4()
    bt = BackgroundTasks()
    await enqueue_mod.enqueue_document_ingestion(doc_id, bt)
    assert seen == []
    await bt()
    assert seen == [str(doc_id)]


@pytest.mark.asyncio
async def test_enqueue_delay_failure_marks_failed(
    client,
    register_and_login,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """F-log：delay 抛错 → queued 文档标 failed。"""
    monkeypatch.setattr(settings, "celery_task_always_eager_local", False)
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))

    def _boom(_doc_id: str):
        raise ConnectionError("redis down")

    monkeypatch.setattr(enqueue_mod.ingest_document_task, "delay", _boom)

    headers, user = await register_and_login(prefix="g1-enq")
    kb = await create_test_kb(client, headers, user, name="G1 enqueue fail")
    doc_id = uuid4()
    storage = Path(tmp_path) / "g1-fail.md"
    storage.write_text("x", encoding="utf-8")

    async with SessionLocal() as db:
        db.add(
            Document(
                id=doc_id,
                kb_id=UUID(str(kb["id"])),
                filename="g1-enqueue-fail.md",
                file_type="md",
                file_size=1,
                content_sha256="a" * 64,
                storage_path=str(storage),
                status=DocumentStatus.queued,
                uploaded_by=UUID(str(user["id"])),
            )
        )
        await db.commit()

    await enqueue_mod.enqueue_document_ingestion(doc_id, None)

    async with SessionLocal() as db:
        doc = await db.get(Document, doc_id)
        assert doc is not None
        assert doc.status == DocumentStatus.failed
        assert doc.error_message and "任务队列不可用" in doc.error_message
