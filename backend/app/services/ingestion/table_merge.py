"""B2：PDF 相邻页同列表格启发式合并。"""

from __future__ import annotations

import re

from app.services.ingestion.table_md import (
    headers_similar,
    parse_markdown_table,
    rebuild_markdown_table,
    row_looks_like_data,
)
from app.services.ingestion.types import ParsedBlock

_SPAN_START = re.compile(r"第\s*(\d+)\s*[–-]")
_SPAN_END = re.compile(r"[–-]\s*(\d+)\s*页")


def merge_cross_page_tables(blocks: list[ParsedBlock]) -> list[ParsedBlock]:
    """链式合并页码连续、列数相同的 table block。

    - 续页表头 ≈ 上表表头 → 去重表头后拼数据行
    - 续页「表头」行更像数据 → 整段当数据拼上
    - 否则不合并（防同列数异表误拼）
    """
    if not blocks:
        return []

    out: list[ParsedBlock] = []
    for block in blocks:
        if block.block_kind != "table":
            out.append(block)
            continue
        if not out or out[-1].block_kind != "table":
            out.append(_copy_block(block))
            continue

        merged = _try_merge(out[-1], block)
        if merged is None:
            out.append(_copy_block(block))
        else:
            out[-1] = merged
    return out


def _copy_block(block: ParsedBlock) -> ParsedBlock:
    return ParsedBlock(
        content=block.content,
        page_number=block.page_number,
        section_title=block.section_title,
        heading_path=block.heading_path,
        block_kind=block.block_kind,
    )


def _start_page(block: ParsedBlock) -> int | None:
    title = block.section_title or ""
    m = _SPAN_START.search(title)
    if m:
        return int(m.group(1))
    return block.page_number


def _end_page(block: ParsedBlock) -> int | None:
    title = block.section_title or ""
    m = _SPAN_END.search(title)
    if m:
        return int(m.group(1))
    return block.page_number


def _try_merge(prev: ParsedBlock, nxt: ParsedBlock) -> ParsedBlock | None:
    end = _end_page(prev)
    n_page = nxt.page_number
    if end is None or n_page is None or n_page != end + 1:
        return None

    parsed_prev = parse_markdown_table(prev.content)
    parsed_next = parse_markdown_table(nxt.content)
    if not parsed_prev or not parsed_next:
        return None

    header_p, data_p = parsed_prev
    header_n, data_n = parsed_next
    if len(header_p) != len(header_n):
        return None

    if headers_similar(header_p, header_n):
        combined_data = data_p + data_n
    elif row_looks_like_data(header_n):
        combined_data = data_p + [header_n] + data_n
    else:
        return None

    start = _start_page(prev) or end
    title = f"第{start}–{n_page}页表格"
    return ParsedBlock(
        content=rebuild_markdown_table(header_p, combined_data),
        page_number=start,
        section_title=title,
        heading_path=title,
        block_kind="table",
    )
