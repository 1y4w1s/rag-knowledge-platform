"""Wave 2.3 入库管道 + golden_qa 章节/页码元数据测试。"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.enums import DocumentStatus
from app.services.ingestion.pipeline import process_document_ingestion

FIXTURES = Path(__file__).parent / "fixtures"
GOLDEN_MD = FIXTURES / "golden_handbook.md"


from tests.conftest import create_test_kb as _create_kb


async def _ingest_fixture(
    *,
    kb_id: uuid.UUID,
    user_id: uuid.UUID,
    source: Path,
    file_type: str,
    upload_dir: Path,
) -> Document:
    doc_id = uuid.uuid4()
    storage_dir = upload_dir / str(kb_id) / str(doc_id)
    storage_dir.mkdir(parents=True, exist_ok=True)
    storage_path = storage_dir / f"{uuid.uuid4()}.{file_type}"
    storage_path.write_bytes(source.read_bytes())

    async with SessionLocal() as db:
        doc = Document(
            id=doc_id,
            kb_id=kb_id,
            filename=source.name,
            file_type=file_type,
            file_size=storage_path.stat().st_size,
            storage_path=str(storage_path),
            status=DocumentStatus.queued,
            uploaded_by=user_id,
        )
        db.add(doc)
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


def _make_golden_pdf(path: Path) -> None:
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas

    c = canvas.Canvas(str(path), pagesize=letter)
    c.drawString(72, 720, "Employee Handbook")
    c.drawString(72, 690, "Chapter 1 Attendance")
    c.drawString(72, 660, "Apply annual leave two weeks")
    c.showPage()
    c.drawString(72, 720, "in advance. After one year: annual leave 10 days.")
    c.save()


@pytest.fixture
def upload_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    return tmp_path


@pytest.mark.asyncio
async def test_golden_md_chunks_have_section_and_heading(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
) -> None:
    headers, user = await register_and_login(prefix="golden-md")
    kb = await _create_kb(client, headers, user)
    kb_id = uuid.UUID(kb["id"])
    user_id = uuid.UUID(user["id"])

    doc = await _ingest_fixture(
        kb_id=kb_id,
        user_id=user_id,
        source=GOLDEN_MD,
        file_type="md",
        upload_dir=upload_dir,
    )

    assert doc.status == DocumentStatus.completed
    assert doc.chunk_count is not None and doc.chunk_count > 0
    assert doc.processing_completed_at is not None
    assert doc.processing_started_at is not None

    chunks = await _load_chunks(doc.id)
    assert len(chunks) == doc.chunk_count
    assert all(c.embedding is not None for c in chunks)

    annual = next(c for c in chunks if "年假10天" in c.content)
    assert annual.section_title == "1.1 年假"
    assert annual.heading_path is not None
    assert "考勤制度" in annual.heading_path

    late = next(c for c in chunks if "迟到 30 分钟" in c.content)
    assert late.section_title == "1.2 迟到"

    bonus = next(c for c in chunks if "12 月" in c.content)
    assert bonus.section_title == "2.1 年终奖"
    assert bonus.heading_path is not None
    assert "薪酬福利" in bonus.heading_path


@pytest.mark.asyncio
async def test_golden_pdf_chunk_has_page_number(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
    tmp_path: Path,
) -> None:
    pytest.importorskip("reportlab")
    pdf_path = tmp_path / "golden_handbook.pdf"
    _make_golden_pdf(pdf_path)

    headers, user = await register_and_login(prefix="golden-pdf")
    kb = await _create_kb(client, headers, user)
    kb_id = uuid.UUID(kb["id"])
    user_id = uuid.UUID(user["id"])

    doc = await _ingest_fixture(
        kb_id=kb_id,
        user_id=user_id,
        source=pdf_path,
        file_type="pdf",
        upload_dir=upload_dir,
    )

    assert doc.status == DocumentStatus.completed
    chunks = await _load_chunks(doc.id)

    annual_chunks = [c for c in chunks if "annual leave 10 days" in c.content]
    assert annual_chunks, "应命中含 annual leave 10 days 的切片"
    assert any(c.page_number == 2 for c in annual_chunks)

    title_chunks = [c for c in chunks if c.section_title and "Attendance" in c.section_title]
    assert title_chunks


@pytest.mark.asyncio
async def test_ingestion_marks_failed_for_missing_file(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
) -> None:
    headers, user = await register_and_login(prefix="golden-fail")
    kb = await _create_kb(client, headers, user)
    kb_id = uuid.UUID(kb["id"])
    user_id = uuid.UUID(user["id"])
    doc_id = uuid.uuid4()

    async with SessionLocal() as db:
        db.add(
            Document(
                id=doc_id,
                kb_id=kb_id,
                filename="ghost.txt",
                file_type="txt",
                file_size=1,
                storage_path=str(upload_dir / "missing.txt"),
                status=DocumentStatus.queued,
                uploaded_by=user_id,
            )
        )
        await db.commit()

    await process_document_ingestion(doc_id)

    async with SessionLocal() as db:
        doc = await db.get(Document, doc_id)
        assert doc is not None
        assert doc.status == DocumentStatus.failed
        assert doc.error_message is not None
