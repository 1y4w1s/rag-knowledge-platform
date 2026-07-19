"""Format-F4-3 · pipeline OCR 错误文案与 completed 路径。"""

from __future__ import annotations

import uuid
from pathlib import Path
from unittest.mock import patch

import pytest
from httpx import AsyncClient

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.document import Document
from app.models.enums import DocumentStatus
from app.services.ingestion.pipeline import process_document_ingestion

from tests.conftest import create_test_kb as _create_kb


@pytest.fixture
def upload_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    return tmp_path


def _make_blank_pdf(path: Path) -> None:
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas

    c = canvas.Canvas(str(path), pagesize=letter)
    c.showPage()
    c.save()


async def _queue_pdf_document(
    *,
    kb_id: uuid.UUID,
    user_id: uuid.UUID,
    pdf_path: Path,
    upload_dir: Path,
) -> uuid.UUID:
    doc_id = uuid.uuid4()
    storage_dir = upload_dir / str(kb_id) / str(doc_id)
    storage_dir.mkdir(parents=True, exist_ok=True)
    storage_path = storage_dir / f"{uuid.uuid4()}.pdf"
    storage_path.write_bytes(pdf_path.read_bytes())

    async with SessionLocal() as db:
        db.add(
            Document(
                id=doc_id,
                kb_id=kb_id,
                filename=pdf_path.name,
                file_type="pdf",
                file_size=storage_path.stat().st_size,
                storage_path=str(storage_path),
                status=DocumentStatus.queued,
                uploaded_by=user_id,
            )
        )
        await db.commit()
    return doc_id


@pytest.mark.asyncio
async def test_pipeline_scanned_ocr_empty_fails_with_chinese_message(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
) -> None:
    headers, user = await register_and_login(prefix="pipe-ocr-empty")
    kb = await _create_kb(client, headers, user)
    kb_id = uuid.UUID(kb["id"])

    pdf_path = upload_dir / "blank-scan.pdf"
    _make_blank_pdf(pdf_path)

    doc_id = await _queue_pdf_document(
        kb_id=kb_id,
        user_id=uuid.UUID(user["id"]),
        pdf_path=pdf_path,
        upload_dir=upload_dir,
    )

    with patch("app.services.ingestion.ocr.is_ocr_runtime_available", return_value=True):
        with patch("app.services.ingestion.ocr.ocr_pdf_pages", return_value=[(1, "   ")]):
            await process_document_ingestion(doc_id)

    async with SessionLocal() as db:
        doc = await db.get(Document, doc_id)
        assert doc is not None
        assert doc.status == DocumentStatus.failed
        assert doc.error_message == "OCR 未识别到文字"
        assert "500" not in (doc.error_message or "")
        assert "Internal" not in (doc.error_message or "")


@pytest.mark.asyncio
async def test_pipeline_scanned_page_limit_fails_with_chinese_message(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.config import Settings

    headers, user = await register_and_login(prefix="pipe-ocr-limit")
    kb = await _create_kb(client, headers, user)
    kb_id = uuid.UUID(kb["id"])

    pdf_path = upload_dir / "big-scan.pdf"
    _make_blank_pdf(pdf_path)

    doc_id = await _queue_pdf_document(
        kb_id=kb_id,
        user_id=uuid.UUID(user["id"]),
        pdf_path=pdf_path,
        upload_dir=upload_dir,
    )

    enabled = Settings(_env_file=None, ocr_enabled=True, ocr_max_pages=1)
    monkeypatch.setattr("app.services.ingestion.ocr.settings", enabled)

    with patch("app.services.ingestion.ocr.is_ocr_runtime_available", return_value=True):
        with patch(
            "app.services.ingestion.ocr.ocr_pdf_pages",
            side_effect=ValueError("扫描页数超过上限（1 页），请拆分后上传"),
        ):
            await process_document_ingestion(doc_id)

    async with SessionLocal() as db:
        doc = await db.get(Document, doc_id)
        assert doc is not None
        assert doc.status == DocumentStatus.failed
        assert doc.error_message == "扫描页数超过上限（1 页），请拆分后上传"


@pytest.mark.asyncio
async def test_pipeline_scanned_ocr_disabled_fails_with_chinese_message(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.config import Settings

    headers, user = await register_and_login(prefix="pipe-ocr-off")
    kb = await _create_kb(client, headers, user)
    kb_id = uuid.UUID(kb["id"])

    pdf_path = upload_dir / "blank-off.pdf"
    _make_blank_pdf(pdf_path)

    doc_id = await _queue_pdf_document(
        kb_id=kb_id,
        user_id=uuid.UUID(user["id"]),
        pdf_path=pdf_path,
        upload_dir=upload_dir,
    )

    disabled = Settings(_env_file=None, ocr_enabled=False)
    monkeypatch.setattr("app.services.ingestion.ocr.settings", disabled)

    await process_document_ingestion(doc_id)

    async with SessionLocal() as db:
        doc = await db.get(Document, doc_id)
        assert doc is not None
        assert doc.status == DocumentStatus.failed
        assert doc.error_message == "不支持扫描件"


@pytest.mark.asyncio
async def test_pipeline_scanned_ocr_success_completed(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
) -> None:
    headers, user = await register_and_login(prefix="pipe-ocr-ok")
    kb = await _create_kb(client, headers, user)
    kb_id = uuid.UUID(kb["id"])

    pdf_path = upload_dir / "blank-ok.pdf"
    _make_blank_pdf(pdf_path)

    doc_id = await _queue_pdf_document(
        kb_id=kb_id,
        user_id=uuid.UUID(user["id"]),
        pdf_path=pdf_path,
        upload_dir=upload_dir,
    )

    with patch("app.services.ingestion.ocr.is_ocr_runtime_available", return_value=True):
        with patch(
            "app.services.ingestion.ocr.ocr_pdf_pages",
            return_value=[(1, "扫描件识别文本用于入库")],
        ):
            await process_document_ingestion(doc_id)

    async with SessionLocal() as db:
        doc = await db.get(Document, doc_id)
        assert doc is not None
        assert doc.status == DocumentStatus.completed
        assert doc.chunk_count is not None and doc.chunk_count > 0
        assert doc.error_message is None
