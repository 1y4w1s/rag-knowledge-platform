"""Markdown / 纯文本表格识别（Plan-RAG R2-2）。"""

from __future__ import annotations

import re

_PIPE_ROW = re.compile(r"^\s*\|.+\|\s*$")


def is_markdown_table_block(text: str) -> bool:
    """连续多行 pipe 表格（含分隔行 |---|）。"""
    lines = [line for line in text.strip().splitlines() if line.strip()]
    if len(lines) < 2:
        return False
    pipe_lines = sum(1 for line in lines if _PIPE_ROW.match(line))
    return pipe_lines >= 2 and pipe_lines == len(lines)


def table_row_count(text: str) -> int:
    return len([line for line in text.strip().splitlines() if line.strip()])
