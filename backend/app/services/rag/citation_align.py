"""F1：引用与答案硬对齐（解析正文 [片段N]，裁剪 done/落库 citation）。

流式仍可先吐候选；终态以本模块输出为准。漏标（无合法标记）→ keep-all。
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import TypeVar

from app.services.rag.types import RetrievedChunk

_FRAGMENT_MARK = re.compile(r"\[片段\s*(\d+)\]")

T = TypeVar("T")


def parse_fragment_indices(answer: str) -> list[int]:
    """从正文提取 1-based 片段下标；去重且保首次出现顺序。"""
    if not answer:
        return []
    seen: set[int] = set()
    ordered: list[int] = []
    for match in _FRAGMENT_MARK.finditer(answer):
        idx = int(match.group(1))
        if idx in seen:
            continue
        seen.add(idx)
        ordered.append(idx)
    return ordered


def _body_for_align(answer: str, strip_prefix: str | None) -> str:
    text = answer or ""
    if strip_prefix and text.startswith(strip_prefix):
        rest = text[len(strip_prefix) :]
        return rest.lstrip("\n") if rest.startswith("\n") else rest
    return text


def align_chunks_to_answer(
    answer: str,
    chunks: list[RetrievedChunk],
    *,
    strip_prefix: str | None = None,
) -> list[RetrievedChunk]:
    """按正文标记裁剪 chunk；无合法标记则返回原列表（keep-all）。

    编号映射与 build_messages 一致（similarity 升序，H1）：
    LLM 看到的 [片段N] 是 build_messages 排序后的编号，此处必须按同一
    排序解析，否则相似度顺序与检索顺序不同时引用会错位（GQ-47 实测：
    4.1 被 LLM 正确标为片段2，原序解析却映射到 6.3）。
    """
    if not chunks:
        return []
    body = _body_for_align(answer, strip_prefix)
    indices = parse_fragment_indices(body)
    valid = [i for i in indices if 1 <= i <= len(chunks)]
    if not valid:
        return list(chunks)
    sorted_chunks = sorted(chunks, key=lambda c: c.similarity, reverse=False)
    return [sorted_chunks[i - 1] for i in valid]


def align_citations_to_answer(
    answer: str,
    chunks: list[RetrievedChunk],
    *,
    to_citation: Callable[[RetrievedChunk], T],
    strip_prefix: str | None = None,
) -> list[T]:
    """硬对齐终态 citation 列表（供 done / 落库）。"""
    aligned = align_chunks_to_answer(
        answer, chunks, strip_prefix=strip_prefix
    )
    return [to_citation(c) for c in aligned]
