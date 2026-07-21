"""B2：超长 Markdown 表格按行窗切分（每窗自带表头）。"""

from __future__ import annotations

from app.services.ingestion.table_md import parse_markdown_table, rebuild_markdown_table
from app.services.ingestion.types import ChunkDraft, ParsedBlock


def split_table_block(
    block: ParsedBlock,
    *,
    max_chars: int,
    row_overlap: int = 1,
    parent_max_chars: int = 8000,
    enabled: bool = True,
) -> list[ChunkDraft]:
    """将单个 table ParsedBlock 切成 table leaf（可选 parent）。"""
    text = block.content.strip()
    if not text:
        return []

    if not enabled or len(text) <= max_chars:
        return [
            ChunkDraft(
                content=text,
                page_number=block.page_number,
                section_title=block.section_title,
                heading_path=block.heading_path,
                chunk_kind="table",
            )
        ]

    parsed = parse_markdown_table(text)
    if not parsed:
        # 无法按行切则整块保留（与旧行为一致）
        return [
            ChunkDraft(
                content=text,
                page_number=block.page_number,
                section_title=block.section_title,
                heading_path=block.heading_path,
                chunk_kind="table",
            )
        ]

    header, data_rows = parsed
    if not data_rows:
        return [
            ChunkDraft(
                content=text,
                page_number=block.page_number,
                section_title=block.section_title,
                heading_path=block.heading_path,
                chunk_kind="table",
            )
        ]

    windows = _window_data_rows(header, data_rows, max_chars=max_chars, row_overlap=row_overlap)
    leaves: list[ChunkDraft] = [
        ChunkDraft(
            content=rebuild_markdown_table(header, rows),
            page_number=block.page_number,
            section_title=block.section_title,
            heading_path=block.heading_path,
            chunk_kind="table",
        )
        for rows in windows
    ]

    if len(leaves) <= 1:
        return leaves

    if len(text) > parent_max_chars:
        return leaves

    group = block.heading_path or block.section_title or "__table__"
    parent = ChunkDraft(
        content=text,
        page_number=block.page_number,
        section_title=block.section_title,
        heading_path=block.heading_path,
        chunk_kind="parent",
        parent_group=group,
    )
    for leaf in leaves:
        leaf.parent_group = group
    return [parent, *leaves]


def _window_data_rows(
    header: list[str],
    data_rows: list[list[str]],
    *,
    max_chars: int,
    row_overlap: int,
) -> list[list[list[str]]]:
    """按字符预算切数据行；每窗至少 1 行。"""
    overlap = max(0, row_overlap)
    windows: list[list[list[str]]] = []
    i = 0
    n = len(data_rows)
    while i < n:
        window: list[list[str]] = []
        # grow until adding next row would exceed budget (always allow first row)
        while i + len(window) < n:
            candidate = window + [data_rows[i + len(window)]]
            content = rebuild_markdown_table(header, candidate)
            if window and len(content) > max_chars:
                break
            window = candidate
            if len(content) > max_chars and len(window) == 1:
                # 单行仍超长：硬收该行，避免死循环
                break
        if not window:
            window = [data_rows[i]]
        windows.append(window)
        advance = len(window) - overlap
        if advance < 1:
            advance = 1
        i += advance
        # 最后一窗若与上一窗完全重叠则停
        if i >= n:
            break
    return windows
