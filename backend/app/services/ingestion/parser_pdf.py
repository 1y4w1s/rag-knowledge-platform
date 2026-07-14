"""PDF 解析：文字层 pdfplumber · 扫描件 OCR（Format-F4）。"""

from __future__ import annotations

import re
from pathlib import Path

from app.services.ingestion.types import ParsedBlock

CHAPTER_RE = re.compile(
    r"^(?:第[一二三四五六七八九十百千\d]+章[^\n]{0,40}|"
    r"Chapter\s+\d+[^\n]{0,40}|"
    r"\d+(?:\.\d+)*\s+[^\n]{1,60}|"
    r"#{1,3}\s+.+)$"
)

SCANNED_TEXT_THRESHOLD = 50
SCANNED_SAMPLE_PAGES = 3


def _merge_cross_page_blocks(blocks: list[ParsedBlock]) -> list[ParsedBlock]:
    """PDF 跨页：上一页末句未结束则与下一页首段合并。"""
    if not blocks:
        return []

    merged: list[ParsedBlock] = []
    for block in blocks:
        text = block.content.strip()
        if not text:
            continue

        if merged and not re.search(r"[。！？!?；;][\"'）)]?\s*$", merged[-1].content):
            prev = merged[-1]
            joiner = "" if prev.content.endswith(("-", "—")) else " "
            prev.content = f"{prev.content.rstrip()}{joiner}{text}".strip()
            if block.page_number is not None:
                prev.page_number = block.page_number
            if block.section_title:
                prev.section_title = block.section_title
                prev.heading_path = block.heading_path
            continue

        merged.append(
            ParsedBlock(
                content=text,
                page_number=block.page_number,
                section_title=block.section_title,
                heading_path=block.heading_path,
            )
        )
    return merged


def detect_scanned_pdf(path: Path) -> bool:
    """前 ``min(3, 页数)`` 页可抽文字去空白后总长 < 50 → 扫描件。"""
    import pdfplumber

    with pdfplumber.open(path) as pdf:
        if not pdf.pages:
            return False
        sample_count = min(SCANNED_SAMPLE_PAGES, len(pdf.pages))
        total_chars = 0
        for page_idx in range(sample_count):
            text = pdf.pages[page_idx].extract_text() or ""
            total_chars += len(re.sub(r"\s+", "", text))
        return total_chars < SCANNED_TEXT_THRESHOLD


def _pdf_table_to_markdown(table_data: list[list[str | None]]) -> list[str]:
    """Convert pdfplumber table data to pipe-markdown table lines."""
    if not table_data or not table_data[0]:
        return []
    lines: list[str] = []
    # Header row
    lines.append("| " + " | ".join(str(c or "") for c in table_data[0]) + " |")
    # Separator
    lines.append("| " + " | ".join("---" for _ in table_data[0]) + " |")
    # Data rows
    for row in table_data[1:]:
        lines.append("| " + " | ".join(str(c or "") for c in row) + " |")
    return lines


def _parse_pdf_tables_only(path: Path, *, batch_pages: int = 10) -> list[ParsedBlock]:
    """Extract tables from PDF, each as a standalone table block."""
    import pdfplumber

    blocks: list[ParsedBlock] = []
    with pdfplumber.open(path) as pdf:
        if not pdf.pages:
            return []

        for batch_start in range(0, len(pdf.pages), batch_pages):
            batch_end = min(batch_start + batch_pages, len(pdf.pages))

            for page_idx in range(batch_start, batch_end):
                page = pdf.pages[page_idx]
                page_number = page_idx + 1
                tables = page.extract_tables()
                for table in tables:
                    if not table or len(table) < 2:
                        continue
                    md_lines = _pdf_table_to_markdown(table)
                    blocks.append(
                        ParsedBlock(
                            content="\n".join(md_lines),
                            page_number=page_number,
                            section_title=f"第{page_number}页表格",
                            heading_path=f"第{page_number}页表格",
                            block_kind="table",
                        )
                    )
    return blocks


def parse_pdf(path: Path, *, batch_pages: int = 10) -> list[ParsedBlock]:
    import pdfplumber

    blocks: list[ParsedBlock] = []
    heading_stack: list[str] = []
    doc_title: str | None = None

    with pdfplumber.open(path) as pdf:
        if not pdf.pages:
            return []

        for batch_start in range(0, len(pdf.pages), batch_pages):
            batch_end = min(batch_start + batch_pages, len(pdf.pages))
            batch_blocks: list[ParsedBlock] = []

            for page_idx in range(batch_start, batch_end):
                page = pdf.pages[page_idx]
                page_number = page_idx + 1
                lines = (page.extract_text() or "").splitlines()
                buffer: list[str] = []
                current_meta = ParsedBlock(content="")

                def flush() -> None:
                    nonlocal buffer, current_meta
                    if not buffer:
                        return
                    text = "\n".join(buffer).strip()
                    if text:
                        batch_blocks.append(
                            ParsedBlock(
                                content=text,
                                page_number=page_number,
                                section_title=current_meta.section_title,
                                heading_path=current_meta.heading_path,
                            )
                        )
                    buffer = []

                for raw_line in lines:
                    line = raw_line.strip()
                    if not line:
                        flush()
                        continue

                    if CHAPTER_RE.match(line):
                        flush()
                        title = re.sub(r"^#+\s*", "", line)
                        if doc_title is None:
                            doc_title = title
                            heading_stack = [title]
                        elif title != doc_title:
                            if title.startswith("Chapter") or title.startswith("第"):
                                heading_stack = [doc_title, title]
                            else:
                                heading_stack = [doc_title] + [title]
                        current_meta = ParsedBlock(
                            content="",
                            page_number=page_number,
                            section_title=title,
                            heading_path=">".join(heading_stack),
                        )
                        continue

                    buffer.append(line)

                flush()

            blocks.extend(_merge_cross_page_blocks(batch_blocks))

    # Append table blocks extracted from PDF
    table_blocks = _parse_pdf_tables_only(path, batch_pages=batch_pages)
    blocks.extend(table_blocks)

    return blocks


def parse_pdf_ocr(path: Path) -> list[ParsedBlock]:
    """扫描 PDF：按页 OCR → ``ParsedBlock``，再跨页合并。"""
    from app.services.ingestion.ocr import ocr_pdf_pages

    page_blocks: list[ParsedBlock] = []
    for page_number, text in ocr_pdf_pages(path):
        cleaned = text.strip()
        if cleaned:
            page_blocks.append(
                ParsedBlock(content=cleaned, page_number=page_number)
            )

    if not page_blocks:
        raise ValueError("OCR 未识别到文字")

    return _merge_cross_page_blocks(page_blocks)
