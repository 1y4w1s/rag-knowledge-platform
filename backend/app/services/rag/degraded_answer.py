"""L1 降级回答：LLM 全挂时返回原文片段 + 降级说明（确定性、无 LLM）。"""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from typing import Literal

from app.core.degradation import DegradationLevel, degradation_message
from app.services.rag.confidence_reply import _is_english_message
from app.services.rag.types import RetrievedChunk

FRAGMENT_BODY_MAX_CHARS = 300


def _language_for(query: str) -> Literal["zh", "en"]:
    """复用 R4-2 / E3 同款判定：ASCII 字母多于 CJK 字符 → 英文，否则中文。"""
    return "en" if _is_english_message(query) else "zh"


def _fragment_line(
    index: int,
    chunk: RetrievedChunk,
    *,
    language: Literal["zh", "en"] = "zh",
) -> str:
    body = (chunk.parent_content or chunk.content or "").strip()
    body = body[:FRAGMENT_BODY_MAX_CHARS]

    if language == "en":
        meta: list[str] = []
        if chunk.doc_name:
            meta.append(f'"{chunk.doc_name}"')
        if chunk.page_number is not None:
            meta.append(f"Page {chunk.page_number}")
        if chunk.section_title:
            meta.append(f"Section: {chunk.section_title}")
        label = f"[Fragment {index}]"
        if meta:
            return f"{label} {' · '.join(meta)}: {body}"
        return f"{label} {body}"

    meta: list[str] = []
    if chunk.doc_name:
        meta.append(f"《{chunk.doc_name}》")
    if chunk.page_number is not None:
        meta.append(f"第{chunk.page_number}页")
    if chunk.section_title:
        meta.append(f"章节：{chunk.section_title}")

    label = f"[片段{index}]"
    if meta:
        return f"{label} {' · '.join(meta)}：{body}"
    return f"{label} {body}"


def build_degraded_fragment_reply(
    query: str,
    chunks: Sequence[RetrievedChunk],
) -> str:
    """组装 L1 降级回答：按 query 语言输出说明与片段 meta，正文始终原文。"""
    language = _language_for(query)
    lines = [
        degradation_message(DegradationLevel.LLM_DOWN, language=language)
    ]
    lines.extend(
        _fragment_line(index, chunk, language=language)
        for index, chunk in enumerate(chunks, start=1)
    )
    return "\n".join(lines)


async def stream_degraded_fragment_reply(
    query: str,
    chunks: Sequence[RetrievedChunk],
) -> AsyncIterator[str]:
    """按段 yield 降级回答，与 stream_no_context_reply 同属确定性流。"""
    text = build_degraded_fragment_reply(query, chunks)
    for line in text.splitlines(keepends=True):
        if line:
            yield line
