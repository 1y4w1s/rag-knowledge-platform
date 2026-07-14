"""Format-F4-4 · 扫描 PDF fixture + OCR 入库端到端（mock / 可选真引擎）。"""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.enums import DocumentStatus
from app.services.ingestion.ocr import is_ocr_runtime_available
from app.services.ingestion.parser_pdf import detect_scanned_pdf
from app.services.ingestion.pipeline import process_document_ingestion
from app.services.rag.retrieval import chunk_to_citation
from app.services.rag.types import RetrievedChunk

from tests.conftest import create_test_kb as _create_kb

FIXTURES = Path(__file__).parent / "fixtures" / "ocr"
SAMPLE_SCAN_PDF = FIXTURES / "sample_scan.pdf"
OCR_FIXED_SENTENCE = "知岸扫描件测试固定句"
OCR_PAGE2_SENTENCE = "第二页扫描内容页码测试"


def _ocr_live_tests_enabled() -> bool:
    flag = os.environ.get("RUN_OCR_TESTS", "").strip().lower()
    return flag in {"1", "true", "yes"}


requires_ocr_runtime = pytest.mark.skipif(
    not _ocr_live_tests_enabled() or not is_ocr_runtime_available(),
    reason="需 RUN_OCR_TESTS=1 且已安装 paddleocr/pdf2image",
)


@pytest.fixture
def upload_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    return tmp_path


async def _ingest_scan_fixture(
    *,
    kb_id: uuid.UUID,
    user_id: uuid.UUID,
    upload_dir: Path,
) -> Document:
    assert SAMPLE_SCAN_PDF.is_file(), f"缺少 fixture: {SAMPLE_SCAN_PDF}"

    doc_id = uuid.uuid4()
    storage_dir = upload_dir / str(kb_id) / str(doc_id)
    storage_dir.mkdir(parents=True, exist_ok=True)
    storage_path = storage_dir / "sample_scan.pdf"
    storage_path.write_bytes(SAMPLE_SCAN_PDF.read_bytes())

    async with SessionLocal() as db:
        db.add(
            Document(
                id=doc_id,
                kb_id=kb_id,
                filename=SAMPLE_SCAN_PDF.name,
                file_type="pdf",
                file_size=storage_path.stat().st_size,
                storage_path=str(storage_path),
                status=DocumentStatus.queued,
                uploaded_by=user_id,
            )
        )
        await db.commit()

    await process_document_ingestion(doc_id)

    async with SessionLocal() as db:
        row = await db.get(Document, doc_id)
        assert row is not None
        return row


async def _load_chunks(document_id: uuid.UUID) -> list[DocumentChunk]:
    async with SessionLocal() as db:
        result = await db.scalars(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.chunk_index)
        )
        return list(result.all())


def test_sample_scan_fixture_detected_as_scanned() -> None:
    """扫描 fixture 无文字层，检测应走 OCR 分支。"""
    assert SAMPLE_SCAN_PDF.is_file()
    assert detect_scanned_pdf(SAMPLE_SCAN_PDF) is True


@pytest.mark.asyncio
async def test_ocr_scan_ingestion_mock_completed_chunk_and_citation_page(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
) -> None:
    """mock OCR：扫描 PDF 入库 completed · chunk 含固定句 · citation 带 page。"""
    headers, user = await register_and_login(prefix="ocr-mock-e2e")
    kb = await _create_kb(client, headers, user)
    kb_id = uuid.UUID(kb["id"])
    user_id = uuid.UUID(user["id"])

    mock_pages = [
        (1, f"{OCR_FIXED_SENTENCE}。" + "补充文字满足切片最小长度。" * 6),
        (2, f"{OCR_PAGE2_SENTENCE}。"),
    ]

    with patch("app.services.ingestion.ocr.is_ocr_runtime_available", return_value=True):
        with patch("app.services.ingestion.ocr.ocr_pdf_pages", return_value=mock_pages):
            doc = await _ingest_scan_fixture(
                kb_id=kb_id,
                user_id=user_id,
                upload_dir=upload_dir,
            )

    assert doc.status == DocumentStatus.completed
    assert doc.chunk_count is not None and doc.chunk_count > 0
    assert doc.error_message is None

    chunks = await _load_chunks(doc.id)
    keyword_chunks = [c for c in chunks if OCR_FIXED_SENTENCE in c.content]
    assert keyword_chunks, "切片应包含 OCR 固定句"
    assert any(c.page_number == 1 for c in keyword_chunks)

    page2_chunks = [c for c in chunks if OCR_PAGE2_SENTENCE in c.content]
    assert page2_chunks
    assert any(c.page_number == 2 for c in page2_chunks)

    db_chunk = keyword_chunks[0]
    cite = chunk_to_citation(
        RetrievedChunk(
            kb_id=kb_id,
            chunk_id=db_chunk.id,
            document_id=doc.id,
            doc_name=SAMPLE_SCAN_PDF.name,
            content=db_chunk.content,
            page_number=db_chunk.page_number,
            section_title=db_chunk.section_title,
            heading_path=db_chunk.heading_path,
            similarity=1.0,
        )
    )
    assert cite["page"] == 1
    assert OCR_FIXED_SENTENCE in cite["excerpt"]
    assert cite["doc_name"] == SAMPLE_SCAN_PDF.name


@pytest.mark.asyncio
@requires_ocr_runtime
async def test_ocr_scan_ingestion_live_engine_completed(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
) -> None:
    """真 OCR 引擎：RUN_OCR_TESTS=1 时扫描 fixture 可 completed（CI 默认 skip）。"""
    headers, user = await register_and_login(prefix="ocr-live-e2e")
    kb = await _create_kb(client, headers, user)
    kb_id = uuid.UUID(kb["id"])
    user_id = uuid.UUID(user["id"])

    doc = await _ingest_scan_fixture(
        kb_id=kb_id,
        user_id=user_id,
        upload_dir=upload_dir,
    )

    assert doc.status == DocumentStatus.completed
    chunks = await _load_chunks(doc.id)
    assert chunks
    assert any(c.page_number is not None for c in chunks)
