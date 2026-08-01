"""E3：回答置信度三档与低置信度确定性话术（部分依据 / 建议换问）。

refuse 仍走 R4-2；本模块不改拒答阈值与检索默认。
"""

from __future__ import annotations

from enum import Enum

from app.services.rag.relevance import (
    _vector_scores_universally_weak,
    should_refuse_answer,
)
from app.services.rag.types import RetrievedChunk

# 与 generation.build_messages 片段标签阈值对齐；≥ 此值视为强命中（非 low）
LOW_CONFIDENCE_SIM_CEILING = 0.5

PARTIAL_DISCLAIMER_ZH = (
    "以下回答仅依据部分相关片段，可能无法完整覆盖您的问题；"
    "若不符预期，建议换更具体的问法（如条款号、岗位或文档名）。"
)
PARTIAL_DISCLAIMER_EN = (
    "This answer is based on partially matching passages and may not fully "
    "cover your question. If it looks off, try a more specific phrasing "
    "(e.g. clause number, role, or document name)."
)

PARTIAL_ANSWER_PROMPT_NOTE = (
    "【低置信度约束】检索依据偏弱或覆盖不足：只回答片段中明确支持的部分；"
    "未覆盖的方面直接说明未找到；禁止推测或编造；可建议用户换更具体问法。"
)


class AnswerConfidence(str, Enum):
    refuse = "refuse"
    low = "low"
    normal = "normal"


def _max_scored_similarity(chunks: list[RetrievedChunk]) -> float | None:
    scored = [getattr(c, "similarity", 0.0) or 0.0 for c in chunks[:3] if getattr(c, "similarity", 0.0) and getattr(c, "similarity", 0.0) > 0.0]
    if not scored:
        return None
    return max(scored)


def is_low_confidence(chunks: list[RetrievedChunk]) -> bool:
    """在已通过有依据门禁后，判断是否进入 partial / low 档。

    - 强向量（max_sim ≥ 0.5）→ 否（避免 adaptive_top_k=2 的高置信被误标）
    - S1：有向量分且 max < 0.5
    - S3：向量普遍弱（settings.retrieval_min_top1_similarity）
    - S2：片段数 ≤2 且无强向量（含纯 FTS）
    """
    if not chunks:
        return False

    max_sim = _max_scored_similarity(chunks)
    if max_sim is not None and max_sim >= LOW_CONFIDENCE_SIM_CEILING:
        return False

    # S1
    if max_sim is not None and max_sim < LOW_CONFIDENCE_SIM_CEILING:
        return True

    # S3（与 S1 有重叠；显式保留弱向量设定）
    if _vector_scores_universally_weak(chunks):
        return True

    # S2：稀疏且无强向量
    if len(chunks) <= 2:
        return True

    return False


def classify_answer_confidence(
    chunks: list[RetrievedChunk],
    query: str,
) -> AnswerConfidence:
    if not chunks or should_refuse_answer(chunks, query):
        return AnswerConfidence.refuse
    if is_low_confidence(chunks):
        return AnswerConfidence.low
    return AnswerConfidence.normal


def _is_english_message(user_message: str) -> bool:
    ascii_letters = sum(1 for char in user_message if char.isascii() and char.isalpha())
    cjk_chars = sum(1 for char in user_message if "\u4e00" <= char <= "\u9fff")
    return ascii_letters > cjk_chars


def partial_answer_disclaimer_for(user_message: str) -> str:
    if _is_english_message(user_message):
        return PARTIAL_DISCLAIMER_EN
    return PARTIAL_DISCLAIMER_ZH


def with_partial_disclaimer(user_message: str, body: str) -> str:
    """确保正文以确定性 disclaimer 为前缀（幂等）。"""
    disclaimer = partial_answer_disclaimer_for(user_message)
    text = body or ""
    if text.startswith(disclaimer):
        return text
    if not text.strip():
        return disclaimer
    return f"{disclaimer}\n\n{text}"
