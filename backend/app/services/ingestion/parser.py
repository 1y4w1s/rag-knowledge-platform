"""多格式文档解析（TECH-4.2）。"""

from __future__ import annotations

import re
from pathlib import Path

from app.services.ingestion.parser_pdf import (
    _merge_cross_page_blocks,
    detect_scanned_pdf,
    parse_pdf,
    parse_pdf_ocr,
)
from app.services.ingestion.table_detection import is_markdown_table_block
from app.services.ingestion.types import ParsedBlock

CHAPTER_RE = re.compile(
    r"^(?:第[一二三四五六七八九十百千\d]+章[^\n]{0,40}|"
    r"Chapter\s+\d+[^\n]{0,40}|"
    r"\d+(?:\.\d+)*\s+[^\n]{1,60}|"
    r"#{1,3}\s+.+)$"
)
MD_HEADER_RE = re.compile(r"^(#{1,3})\s+(.+)$")


def parse_txt(content: str) -> list[ParsedBlock]:
    blocks: list[ParsedBlock] = []
    heading_stack: list[str] = []
    doc_title: str | None = None

    for para in re.split(r"\n\s*\n", content.strip()):
        text = para.strip()
        if not text:
            continue

        if CHAPTER_RE.match(text.split("\n", 1)[0]):
            title_line = text.split("\n", 1)[0].strip()
            title = re.sub(r"^#+\s*", "", title_line)
            if doc_title is None and not title.startswith("第") and "." not in title[:4]:
                doc_title = title
                heading_stack = [title]
            else:
                heading_stack = ([doc_title] if doc_title else []) + [title]
            body = text.split("\n", 1)[1].strip() if "\n" in text else ""
            if body:
                blocks.append(
                    ParsedBlock(
                        content=body,
                        section_title=title,
                        heading_path=">".join(heading_stack),
                    )
                )
            continue

        blocks.append(
            ParsedBlock(
                content=text,
                section_title=heading_stack[-1] if heading_stack else None,
                heading_path=">".join(heading_stack) if heading_stack else None,
                block_kind="table" if is_markdown_table_block(text) else "prose",
            )
        )
    return blocks


def parse_md(content: str) -> list[ParsedBlock]:
    blocks: list[ParsedBlock] = []
    heading_stack: list[tuple[int, str]] = []
    doc_title: str | None = None

    for para in re.split(r"\n\s*\n", content.strip()):
        text = para.strip()
        if not text:
            continue

        header_match = MD_HEADER_RE.match(text.split("\n", 1)[0])
        if header_match:
            level = len(header_match.group(1))
            title = header_match.group(2).strip()
            if level == 1 and doc_title is None:
                doc_title = title
            heading_stack = [(lvl, name) for lvl, name in heading_stack if lvl < level]
            heading_stack.append((level, title))
            path = ">".join(name for _, name in heading_stack)
            body = text.split("\n", 1)[1].strip() if "\n" in text else ""
            if body:
                blocks.append(
                    ParsedBlock(
                        content=body,
                        section_title=title,
                        heading_path=path,
                    )
                )
            continue

        path = ">".join(name for _, name in heading_stack) if heading_stack else None
        kind = "table" if is_markdown_table_block(text) else "prose"
        blocks.append(
            ParsedBlock(
                content=text,
                section_title=heading_stack[-1][1] if heading_stack else None,
                heading_path=path,
                block_kind=kind,
            )
        )
    return blocks


def _docx_table_to_markdown(table) -> str:
    rows: list[str] = []
    for row in table.rows:
        cells = [cell.text.strip().replace("\n", " ") for cell in row.cells]
        rows.append("| " + " | ".join(cells) + " |")
    return "\n".join(rows)


def _iter_docx_body(doc) -> list:
    from docx.oxml.table import CT_Tbl
    from docx.oxml.text.paragraph import CT_P
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    for child in doc.element.body:
        if isinstance(child, CT_P):
            yield Paragraph(child, doc)
        elif isinstance(child, CT_Tbl):
            yield Table(child, doc)


def parse_docx(path: Path) -> list[ParsedBlock]:
    from docx import Document as DocxDocument

    blocks: list[ParsedBlock] = []
    heading_stack: list[str] = []
    doc_title: str | None = None

    doc = DocxDocument(str(path))
    buffer: list[str] = []
    current_meta = ParsedBlock(content="")

    def flush() -> None:
        nonlocal buffer, current_meta
        if not buffer:
            return
        text = "\n".join(buffer).strip()
        if text:
            blocks.append(
                ParsedBlock(
                    content=text,
                    section_title=current_meta.section_title,
                    heading_path=current_meta.heading_path,
                    block_kind="prose",
                )
            )
        buffer = []

    for item in _iter_docx_body(doc):
        if hasattr(item, "rows"):
            flush()
            table_text = _docx_table_to_markdown(item)
            if table_text.strip():
                blocks.append(
                    ParsedBlock(
                        content=table_text,
                        section_title=current_meta.section_title,
                        heading_path=current_meta.heading_path,
                        block_kind="table",
                    )
                )
            continue

        para = item
        text = para.text.strip()
        if not text:
            flush()
            continue

        style_name = para.style.name if para.style else ""
        if style_name.startswith("Heading"):
            flush()
            try:
                level = int(style_name.replace("Heading", "").strip() or "1")
            except ValueError:
                level = 1
            if level == 1 and doc_title is None:
                doc_title = text
            heading_stack = heading_stack[: max(0, level - 1)]
            heading_stack.append(text)
            current_meta = ParsedBlock(
                content="",
                section_title=text,
                heading_path=">".join(heading_stack),
            )
            continue

        if CHAPTER_RE.match(text):
            flush()
            if doc_title is None:
                doc_title = text
            heading_stack = [doc_title] if doc_title else []
            if text != doc_title:
                heading_stack.append(text)
            current_meta = ParsedBlock(
                content="",
                section_title=text,
                heading_path=">".join(heading_stack),
            )
            continue

        buffer.append(text)

    flush()
    return blocks


def parse_document(path: Path, file_type: str, *, pdf_batch_pages: int = 10) -> list[ParsedBlock]:
    ext = file_type.lower().lstrip(".")
    if ext == "pdf":
        if detect_scanned_pdf(path):
            from app.services.ingestion.ocr import is_ocr_enabled, is_ocr_runtime_available

            if not is_ocr_enabled():
                raise ValueError("不支持扫描件")
            if not is_ocr_runtime_available():
                raise ValueError("OCR 服务未启用")
            return parse_pdf_ocr(path)

        blocks = parse_pdf(path, batch_pages=pdf_batch_pages)
        if not blocks:
            raise ValueError("不支持扫描件")
        return blocks
    if ext == "txt":
        return parse_txt(path.read_text(encoding="utf-8"))
    if ext == "md":
        return parse_md(path.read_text(encoding="utf-8"))
    if ext == "docx":
        return parse_docx(path)
    raise ValueError(f"不支持的文件类型: {file_type}")
