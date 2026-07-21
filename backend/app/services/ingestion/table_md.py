"""Markdown pipe 表解析/重建（B2 大表切窗 · 跨页合并共用）。"""

from __future__ import annotations

import re

_PIPE_ROW = re.compile(r"^\s*\|.+\|\s*$")
_SEP_CELL = re.compile(r"^:?-+:?$")


def pipe_cells(line: str) -> list[str]:
    raw = line.strip()
    if raw.startswith("|"):
        raw = raw[1:]
    if raw.endswith("|"):
        raw = raw[:-1]
    return [c.strip() for c in raw.split("|")]


def is_separator_row(line: str) -> bool:
    cells = pipe_cells(line)
    return bool(cells) and all(_SEP_CELL.match(c.replace(" ", "")) for c in cells)


def format_pipe_row(cells: list[str]) -> str:
    return "| " + " | ".join(cells) + " |"


def format_separator(n_cols: int) -> str:
    return "| " + " | ".join("---" for _ in range(n_cols)) + " |"


def rebuild_markdown_table(header: list[str], data_rows: list[list[str]]) -> str:
    lines = [format_pipe_row(header), format_separator(len(header))]
    for row in data_rows:
        # pad / trim to header width
        padded = list(row) + [""] * max(0, len(header) - len(row))
        lines.append(format_pipe_row(padded[: len(header)]))
    return "\n".join(lines)


def parse_markdown_table(text: str) -> tuple[list[str], list[list[str]]] | None:
    """返回 (header, data_rows)；无法解析则 None。"""
    lines = [ln for ln in text.strip().splitlines() if ln.strip()]
    if len(lines) < 2:
        return None
    if not all(_PIPE_ROW.match(ln) for ln in lines):
        return None
    header = pipe_cells(lines[0])
    if not header:
        return None
    data_start = 1
    if is_separator_row(lines[1]):
        data_start = 2
    elif len(lines) > 2 and is_separator_row(lines[2]):
        # atypical; still require a separator somewhere early
        return None
    else:
        return None
    data_rows = [pipe_cells(ln) for ln in lines[data_start:]]
    return header, data_rows


def normalize_cell(value: str) -> str:
    return re.sub(r"\s+", "", (value or "").strip().lower())


def headers_similar(a: list[str], b: list[str], *, min_ratio: float = 0.8) -> bool:
    if len(a) != len(b) or not a:
        return False
    matches = sum(1 for x, y in zip(a, b) if normalize_cell(x) == normalize_cell(y))
    return matches / len(a) >= min_ratio


_STRONG_DATA = re.compile(
    r"^("
    r"\d{1,4}([./年-]\d{1,2}([./月-]\d{1,2})?)?日?"  # dates / years
    r"|[\d,.]+%?"  # numbers / percents
    r"|[A-Z]{1,6}-?\d{2,}"  # codes like HR-01
    r")$"
)


def row_looks_like_data(cells: list[str]) -> bool:
    """至少一半非空单元格是强数据信号（数字/日期/编码）→ 更像续页数据行。

    纯中文列名（如 产品|单价）不算数据，避免同列数异表误合并。
    """
    if not cells:
        return False
    non_empty = [(c or "").strip() for c in cells if (c or "").strip()]
    if not non_empty:
        return False
    strong = sum(1 for n in non_empty if _STRONG_DATA.match(n))
    return strong >= max(1, (len(non_empty) + 1) // 2)
