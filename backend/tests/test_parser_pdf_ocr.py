"""Format-F4 · 扫描 PDF 检测与 parser 分支。"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from app.services.ingestion.parser import parse_document
from app.services.ingestion.parser_pdf import detect_scanned_pdf, parse_pdf


def _make_text_pdf(path: Path) -> None:
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas

    c = canvas.Canvas(str(path), pagesize=letter)
    c.drawString(72, 720, "Employee Handbook with enough extractable text for detection.")
    c.drawString(72, 690, "Chapter 1 Attendance policy details.")
    c.showPage()
    c.save()


def _make_blank_pdf(path: Path) -> None:
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas

    c = canvas.Canvas(str(path), pagesize=letter)
    c.showPage()
    c.save()


def test_detect_scanned_pdf_text_layer_false(tmp_path: Path) -> None:
    pdf_path = tmp_path / "text.pdf"
    _make_text_pdf(pdf_path)
    assert detect_scanned_pdf(pdf_path) is False


def test_detect_scanned_pdf_blank_true(tmp_path: Path) -> None:
    pdf_path = tmp_path / "blank.pdf"
    _make_blank_pdf(pdf_path)
    assert detect_scanned_pdf(pdf_path) is True


def test_parse_document_text_layer_unchanged(tmp_path: Path) -> None:
    pdf_path = tmp_path / "text.pdf"
    _make_text_pdf(pdf_path)
    blocks = parse_document(pdf_path, "pdf")
    assert blocks
    assert any("Employee Handbook" in block.content for block in blocks)
    assert all(block.page_number is not None for block in blocks)


def test_parse_document_scanned_ocr_disabled(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.config import Settings

    pdf_path = tmp_path / "blank.pdf"
    _make_blank_pdf(pdf_path)
    disabled = Settings(_env_file=None, ocr_enabled=False)
    monkeypatch.setattr("app.services.ingestion.ocr.settings", disabled)

    with pytest.raises(ValueError, match="不支持扫描件"):
        parse_document(pdf_path, "pdf")


def test_parse_document_scanned_uses_ocr_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pdf_path = tmp_path / "blank.pdf"
    _make_blank_pdf(pdf_path)
    monkeypatch.setattr(
        "app.services.ingestion.ocr.is_ocr_runtime_available", lambda: True
    )

    with patch(
        "app.services.ingestion.ocr.ocr_pdf_pages",
        return_value=[(1, "扫描件识别文本")],
    ):
        blocks = parse_document(pdf_path, "pdf")

    assert len(blocks) == 1
    assert blocks[0].content == "扫描件识别文本"
    assert blocks[0].page_number == 1


def test_parse_pdf_text_layer_direct(tmp_path: Path) -> None:
    pdf_path = tmp_path / "text.pdf"
    _make_text_pdf(pdf_path)
    blocks = parse_pdf(pdf_path)
    assert blocks
    assert any("Employee Handbook" in block.content for block in blocks)
