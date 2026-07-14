"""F3：PDF 表格提取测试。"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.enums import DocumentStatus
from app.services.ingestion.pipeline import process_document_ingestion

from tests.conftest import create_test_kb as _create_kb

pytestmark = pytest.mark.asyncio


def _make_golden_table_pdf(path: Path) -> None:
    """Create a PDF with 2 tables on separate pages."""
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet

    doc = SimpleDocTemplate(str(path), pagesize=letter)
    styles = getSampleStyleSheet()
    story: list = []

    # Title
    story.append(Paragraph("部门预算报告", styles["Title"]))
    story.append(Spacer(1, 12))

    # Table 1: 部门预算
    story.append(Paragraph("Table 1: 各部门预算", styles["Heading2"]))
    data1 = [
        ["部门", "预算(万)", "实际(万)", "偏差"],
        ["研发部", "500", "480", "-20"],
        ["市场部", "300", "310", "+10"],
        ["行政部", "100", "95", "-5"],
    ]
    t1 = Table(data1, colWidths=[100, 80, 80, 60])
    t1.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
    ]))
    story.append(t1)
    story.append(Spacer(1, 24))

    # Text paragraph
    story.append(Paragraph("以下是项目支出明细表：", styles["Normal"]))
    story.append(Spacer(1, 12))

    story.append(Paragraph("Table 2: 项目支出", styles["Heading2"]))
    data2 = [
        ["项目名称", "负责人", "金额(万)", "状态"],
        ["知岸 v1", "张三", "200", "已完成"],
        ["OCR 模块", "李四", "80", "进行中"],
        ["数据迁移", "王五", "50", "未开始"],
    ]
    t2 = Table(data2, colWidths=[120, 80, 80, 80])
    t2.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
    ]))
    story.append(t2)

    doc.build(story)


async def _load_chunks(document_id: uuid.UUID) -> list[DocumentChunk]:
    async with SessionLocal() as db:
        result = await db.scalars(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.chunk_index)
        )
        return list(result.all())


@pytest.fixture
def upload_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    from app.core.config import settings
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    return tmp_path


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


async def test_pdf_table_extraction(
    client: AsyncClient,
    register_and_login,
    upload_dir: Path,
    tmp_path: Path,
) -> None:
    """PDF 表格提取：表格应为 table chunk，散文保留为 prose chunk。"""
    pytest.importorskip("reportlab")
    pdf_path = tmp_path / "golden_table_report.pdf"
    _make_golden_table_pdf(pdf_path)

    headers, user = await register_and_login(prefix="pdf-table-test")
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
    assert doc.chunk_count is not None and doc.chunk_count > 0
    assert doc.processing_completed_at is not None

    chunks = await _load_chunks(doc.id)
    assert len(chunks) == doc.chunk_count
    assert all(c.embedding is not None for c in chunks)

    # There should be at least one table chunk
    table_chunks = [c for c in chunks if c.chunk_kind == "table"]
    assert len(table_chunks) >= 1, f"Expected >=1 table chunk, got {len(table_chunks)}"

    # Verify table content contains expected numeric data
    table_contents = " ".join(c.content for c in table_chunks)
    assert "500" in table_contents, f"Missing '500' in {table_contents}"
    assert "200" in table_contents
    assert "80" in table_contents

    # Verify prose chunks still exist (text between tables)
    prose_chunks = [c for c in chunks if c.chunk_kind == "text" or c.chunk_kind == "parent"]
    assert len(prose_chunks) >= 1, "Expected at least 1 prose/parent chunk"


async def test_pdf_table_upload_and_chat(
    client: AsyncClient,
    register_and_login,
    tmp_path: Path,
) -> None:
    """通过上传 API 验证带表格的 PDF 正常入库。"""
    pytest.importorskip("reportlab")
    pdf_path = tmp_path / "test_table_report.pdf"
    _make_golden_table_pdf(pdf_path)

    headers, user = await register_and_login(prefix="pdf-table-upload")
    kb = await _create_kb(client, headers, user)
    kb_id = kb["id"]

    with open(pdf_path, "rb") as f:
        upload_resp = await client.post(
            f"/api/v1/knowledge-bases/{kb_id}/documents",
            files={"files": ("table_report.pdf", f, "application/pdf")},
            headers=headers,
        )
    assert upload_resp.status_code == 201, upload_resp.text
    data = upload_resp.json()
    docs = data["documents"]
    assert len(docs) == 1
    assert docs[0]["file_type"] == "pdf"
    assert docs[0]["status"] in ("queued", "completed")
