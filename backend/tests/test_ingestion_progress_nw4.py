"""NW-4：入库进度字段契约与 pipeline 阶段序列。"""

from __future__ import annotations

import uuid
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.document import Document
from app.models.enums import DocumentStatus
from app.services.ingestion.progress import (
    STAGE_CHUNKING,
    STAGE_EMBEDDING,
    STAGE_PARSING,
    percent_for_ocr_page,
)
from app.services.ingestion.pipeline import process_document_ingestion
from app.services.ingestion.types import ParsedBlock

from tests.conftest import create_test_kb as _create_kb


@pytest.fixture
def upload_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    return tmp_path


def test_percent_for_ocr_page_bounds() -> None:
    assert percent_for_ocr_page(0, 10) == 10
    assert percent_for_ocr_page(5, 10) == 25
    assert percent_for_ocr_page(10, 10) == 40
    assert percent_for_ocr_page(1, 0) == 10


async def _queue_txt(
    *,
    kb_id: uuid.UUID,
    user_id: uuid.UUID,
    upload_dir: Path,
    text: str = "第一章 测试内容\n\n这是一段用于切片的正文。",
) -> uuid.UUID:
    doc_id = uuid.uuid4()
    storage_dir = upload_dir / str(kb_id) / str(doc_id)
    storage_dir.mkdir(parents=True, exist_ok=True)
    storage_path = storage_dir / f"{uuid.uuid4()}.txt"
    storage_path.write_text(text, encoding="utf-8")

    async with SessionLocal() as db:
        db.add(
            Document(
                id=doc_id,
                kb_id=kb_id,
                filename="progress.txt",
                file_type="txt",
                file_size=storage_path.stat().st_size,
                storage_path=str(storage_path),
                status=DocumentStatus.queued,
                uploaded_by=user_id,
            )
        )
        await db.commit()
    return doc_id


@pytest.mark.asyncio
async def test_pipeline_progress_stages_then_completed_100(
    client,
    register_and_login,
    upload_dir: Path,
) -> None:
    headers, user = await register_and_login(prefix="nw4-prog-ok")
    kb = await _create_kb(client, headers, user, name="nw4-prog-ok")
    kb_id = uuid.UUID(kb["id"])
    doc_id = await _queue_txt(kb_id=kb_id, user_id=uuid.UUID(user["id"]), upload_dir=upload_dir)

    seen: list[tuple[str, int]] = []
    from app.services.ingestion import progress as progress_mod

    real_update = progress_mod.update_document_progress

    async def _track(document_id, *, stage, percent, detail=None):
        seen.append((stage, percent))
        assert percent < 100
        await real_update(document_id, stage=stage, percent=percent, detail=detail)

    fake_vectors = [[0.1] * 512]

    with (
        patch.object(progress_mod, "update_document_progress", side_effect=_track),
        patch(
            "app.services.ingestion.pipeline.try_embed_texts",
            new_callable=AsyncMock,
            return_value=fake_vectors,
        ),
        patch(
            "app.services.ingestion.pipeline.is_mostly_english",
            return_value=False,
        ),
    ):
        await process_document_ingestion(doc_id)

    stages = [s for s, _ in seen]
    assert STAGE_PARSING in stages
    assert STAGE_CHUNKING in stages
    assert STAGE_EMBEDDING in stages
    assert all(p < 100 for _, p in seen)

    async with SessionLocal() as db:
        doc = await db.get(Document, doc_id)
        assert doc is not None
        assert doc.status == DocumentStatus.completed
        assert doc.progress_percent == 100
        assert doc.processing_stage is None
        assert doc.progress_detail is None


@pytest.mark.asyncio
async def test_pipeline_failure_clears_progress(
    client,
    register_and_login,
    upload_dir: Path,
) -> None:
    headers, user = await register_and_login(prefix="nw4-prog-fail")
    kb = await _create_kb(client, headers, user, name="nw4-prog-fail")
    kb_id = uuid.UUID(kb["id"])
    doc_id = await _queue_txt(
        kb_id=kb_id,
        user_id=uuid.UUID(user["id"]),
        upload_dir=upload_dir,
    )

    with patch(
        "app.services.ingestion.pipeline.parse_document",
        side_effect=ValueError("解析后无有效文本内容"),
    ):
        await process_document_ingestion(doc_id)

    async with SessionLocal() as db:
        doc = await db.get(Document, doc_id)
        assert doc is not None
        assert doc.status == DocumentStatus.failed
        assert doc.progress_percent is None
        assert doc.processing_stage is None
        assert doc.progress_detail is None
        assert doc.error_message
        assert "解析后无有效文本内容" in doc.error_message


@pytest.mark.asyncio
async def test_ocr_page_callback_writes_detail(
    client,
    register_and_login,
    upload_dir: Path,
) -> None:
    headers, user = await register_and_login(prefix="nw4-ocr-page")
    kb = await _create_kb(client, headers, user, name="nw4-ocr-page")
    kb_id = uuid.UUID(kb["id"])
    doc_id = await _queue_txt(kb_id=kb_id, user_id=uuid.UUID(user["id"]), upload_dir=upload_dir)

    page_seen: list[tuple[int, str | None]] = []
    from app.services.ingestion import progress as progress_mod

    real_update = progress_mod.update_document_progress

    async def _track(document_id, *, stage, percent, detail=None):
        page_seen.append((percent, detail))
        assert percent < 100
        await real_update(document_id, stage=stage, percent=percent, detail=detail)

    def fake_parse(path, file_type, *, pdf_batch_pages=10, on_page=None):
        if on_page is not None:
            on_page(1, 3)
            on_page(3, 3)
        return [ParsedBlock(content="扫描页正文内容足够长用于切片测试。", page_number=1)]

    fake_vectors = [[0.1] * 512]

    with (
        patch.object(progress_mod, "update_document_progress", side_effect=_track),
        patch(
            "app.services.ingestion.pipeline.parse_document",
            side_effect=fake_parse,
        ),
        patch(
            "app.services.ingestion.pipeline.try_embed_texts",
            new_callable=AsyncMock,
            return_value=fake_vectors,
        ),
        patch(
            "app.services.ingestion.pipeline.is_mostly_english",
            return_value=False,
        ),
    ):
        await process_document_ingestion(doc_id)

    details = [d for _, d in page_seen if d]
    assert any(d and ("第 1/3 页" in d or "第 3/3 页" in d) for d in details)
    ocr_percents = [p for p, d in page_seen if d]
    assert ocr_percents
    assert all(10 <= p <= 40 for p in ocr_percents)

    async with SessionLocal() as db:
        doc = await db.get(Document, doc_id)
        assert doc is not None
        assert doc.status == DocumentStatus.completed
        assert doc.progress_percent == 100


@pytest.mark.asyncio
async def test_retry_clears_progress_fields(
    client,
    register_and_login,
    upload_dir: Path,
) -> None:
    headers, user = await register_and_login(prefix="nw4-retry-clr")
    kb = await _create_kb(client, headers, user, name="nw4-retry-clr")
    kb_id = uuid.UUID(kb["id"])
    doc_id = await _queue_txt(kb_id=kb_id, user_id=uuid.UUID(user["id"]), upload_dir=upload_dir)

    async with SessionLocal() as db:
        doc = await db.get(Document, doc_id)
        assert doc is not None
        doc.status = DocumentStatus.failed
        doc.error_message = "先前失败"
        doc.processing_stage = STAGE_PARSING
        doc.progress_percent = 25
        doc.progress_detail = "第 2/8 页"
        await db.commit()

    with patch(
        "app.services.documents.lifecycle.enqueue_document_ingestion",
        new_callable=AsyncMock,
    ):
        resp = await client.post(
            f"/api/v1/knowledge-bases/{kb_id}/documents/{doc_id}/retry",
            headers=headers,
        )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "queued"
    assert body.get("processing_stage") is None
    assert body.get("progress_percent") is None
    assert body.get("progress_detail") is None

    async with SessionLocal() as db:
        doc = await db.get(Document, doc_id)
        assert doc is not None
        assert doc.processing_stage is None
        assert doc.progress_percent is None
        assert doc.progress_detail is None
