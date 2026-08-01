"""B1：异构 PDF 版式降噪单测。"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.services.ingestion.pdf_denoise import (
    collect_noise_vote_keys,
    denoise_pages_lines,
    filter_page_lines,
    is_page_number_line,
    normalize_for_vote,
)
from app.services.ingestion.parser_pdf import parse_pdf


def _make_dirty_pdf(path: Path, *, pages: int = 4) -> None:
    """每页固定页眉 + 独特正文 + 页脚页码（ASCII，避免 reportlab 缺中文字体）。"""
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas

    c = canvas.Canvas(str(path), pagesize=letter)
    for i in range(pages):
        c.drawString(72, 750, "ACME Employee Handbook")
        c.drawString(72, 700, f"Unique body page {i + 1} annual leave policy.")
        c.drawString(72, 50, f"Page {i + 1}")
        c.showPage()
    c.save()


def _make_clean_pdf(path: Path, *, pages: int = 3) -> None:
    """无重复页眉页脚；每页正文不同。"""
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas

    c = canvas.Canvas(str(path), pagesize=letter)
    for i in range(pages):
        c.drawString(72, 720, f"Section {i + 1} unique title and clause {i + 1}")
        c.drawString(72, 690, f"Once-only sentence number {i + 1}.")
        c.showPage()
    c.save()


def test_is_page_number_line() -> None:
    assert is_page_number_line("第 3 页")
    assert is_page_number_line("第12页")
    assert is_page_number_line("Page 2 of 10")
    assert is_page_number_line("3 / 10")
    assert is_page_number_line("- 5 -")
    assert not is_page_number_line("第3章 考勤")
    assert not is_page_number_line("年假政策说明")


def test_collect_noise_vote_keys_repeated_header() -> None:
    pages = [
        ["ACME Employee Handbook", f"body {i} unique clause text here", f"Page {i}"]
        for i in range(1, 5)
    ]
    keys = collect_noise_vote_keys(pages)
    assert normalize_for_vote("ACME Employee Handbook") in keys
    assert normalize_for_vote("Page 1") in keys
    # 短页中间正文不得进噪声集
    assert normalize_for_vote("body 1 unique clause text here") not in keys


def test_short_page_candidates_do_not_mark_body_as_noise() -> None:
    """3 行页：仅首末参与投票，避免正文被 digit-normalize 后误杀。"""
    pages = [
        [
            "ACME Employee Handbook",
            f"Unique body page {i} annual leave policy.",
            f"Page {i}",
        ]
        for i in range(1, 5)
    ]
    keys = collect_noise_vote_keys(pages)
    assert normalize_for_vote("ACME Employee Handbook") in keys
    assert normalize_for_vote("Page 1") in keys
    assert normalize_for_vote("Unique body page 1 annual leave policy.") not in keys


def test_collect_noise_skip_short_doc() -> None:
    pages = [
        ["ACME Employee Handbook", "body 1", "Page 1"],
        ["ACME Employee Handbook", "body 2", "Page 2"],
    ]
    assert collect_noise_vote_keys(pages) == set()


def test_filter_safety_gate_keeps_short_page() -> None:
    lines = ["ACME Employee Handbook", "short"]
    noise = {normalize_for_vote("ACME Employee Handbook")}
    # 剔页眉后只剩「short」< 30 字 → 回退
    assert filter_page_lines(lines, noise) == lines


def test_denoise_pages_lines_disabled_identity() -> None:
    pages = [["H", "body", "Page 1"]]
    assert denoise_pages_lines(pages, enabled=False) == pages


def test_parse_pdf_dirty_strips_header_footer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "pdf_layout_denoise_enabled", True)
    pdf_path = tmp_path / "dirty.pdf"
    _make_dirty_pdf(pdf_path, pages=4)

    blocks = parse_pdf(pdf_path)
    prose = [b for b in blocks if b.block_kind == "prose"]
    joined = "\n".join(b.content for b in prose)

    assert "annual leave" in joined
    assert "Unique body page 1" in joined
    assert "Unique body page 4" in joined
    # 页眉不应在多个 block 里反复出现
    header_hits = sum(1 for b in prose if "ACME Employee Handbook" in b.content)
    assert header_hits <= 1
    assert "Page 1" not in joined
    assert "Page 4" not in joined


def test_parse_pdf_dirty_switch_off_keeps_noise(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "pdf_layout_denoise_enabled", False)
    pdf_path = tmp_path / "dirty-off.pdf"
    _make_dirty_pdf(pdf_path, pages=4)

    blocks = parse_pdf(pdf_path)
    joined = "\n".join(b.content for b in blocks if b.block_kind == "prose")
    assert joined.count("ACME Employee Handbook") >= 3
    assert "Page 1" in joined


def test_parse_pdf_clean_matches_switch_off(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.core.config import settings

    pdf_path = tmp_path / "clean.pdf"
    _make_clean_pdf(pdf_path, pages=3)

    monkeypatch.setattr(settings, "pdf_layout_denoise_enabled", True)
    on_blocks = parse_pdf(pdf_path)
    monkeypatch.setattr(settings, "pdf_layout_denoise_enabled", False)
    off_blocks = parse_pdf(pdf_path)

    on_text = [b.content for b in on_blocks if b.block_kind == "prose"]
    off_text = [b.content for b in off_blocks if b.block_kind == "prose"]
    assert on_text == off_text
    assert any("unique title" in t for t in on_text)
