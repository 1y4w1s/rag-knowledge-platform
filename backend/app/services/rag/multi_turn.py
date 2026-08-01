"""Thread 内多轮上下文：载历史 + 查询改写（E1 · 供 fast / thorough 共用）。

换题门闩：同 thread 突然换全新主题时跳过 contextualize，生成不带旧 history。
"""

from __future__ import annotations

import re
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.rag.generation import contextualize_query
from app.services.rag.persistence import list_thread_messages

# 命中任一 → 不当换题（优先保追问改写）
_FOLLOW_UP_ZH = (
    "那",
    "呢",
    "它",
    "他",
    "她",
    "这个",
    "那个",
    "上述",
    "刚才",
    "还有",
    "继续",
    "同上",
    "怎么算",
    "怎么办",
    "啥时候",
)
_FOLLOW_UP_EN = re.compile(
    r"\b(?:it|that|this|those|these|they|he|she|above)\b|"
    r"\b(?:what|how)\s+about\b",
    re.IGNORECASE,
)

_TOPIC_SHIFT_MIN_LEN = 8
_TOPIC_SHIFT_JACCARD_MAX = 0.12


def _last_user_content(history: list[dict[str, str]]) -> str | None:
    for msg in reversed(history):
        if msg.get("role") == "user":
            text = (msg.get("content") or "").strip()
            if text:
                return text
    return None


def _char_bigrams(text: str) -> set[str]:
    s = "".join(text.split())
    if len(s) < 2:
        return set()
    return {s[i : i + 2] for i in range(len(s) - 1)}


def _bigram_jaccard(a: str, b: str) -> float:
    ba, bb = _char_bigrams(a), _char_bigrams(b)
    if not ba and not bb:
        return 0.0
    if not ba or not bb:
        return 0.0
    inter = len(ba & bb)
    union = len(ba | bb)
    return inter / union if union else 0.0


def _has_follow_up_marker(message: str) -> bool:
    if any(token in message for token in _FOLLOW_UP_ZH):
        return True
    return bool(_FOLLOW_UP_EN.search(message))


def is_topic_shift(message: str, history: list[dict[str, str]]) -> bool:
    """廉价启发式：无指代 + 与上轮用户问重叠低 + 足够长 → 换题。

    保守偏追问：宁可少判换题，也不误杀指代。
    """
    text = (message or "").strip()
    if len(text) < _TOPIC_SHIFT_MIN_LEN:
        return False
    prev = _last_user_content(history)
    if prev is None:
        return False
    if _has_follow_up_marker(text):
        return False
    return _bigram_jaccard(text, prev) < _TOPIC_SHIFT_JACCARD_MAX


async def load_thread_history(
    db: AsyncSession,
    *,
    thread_id: UUID,
    user_id: UUID,
) -> list[dict[str, str]]:
    """返回本 user + thread 的 role/content 历史（时间正序；不含尚未落库的本轮）。"""
    rows = await list_thread_messages(db, thread_id=thread_id, user_id=user_id)
    return [{"role": msg.role.value, "content": msg.content} for msg in rows]


async def prepare_multi_turn_query(
    db: AsyncSession,
    *,
    message: str,
    user_id: UUID,
    thread_id: UUID | None,
) -> tuple[list[dict[str, str]] | None, str]:
    """载历史并 contextualize；无 thread / 无历史时返回 (None, 原文)。

    换题时：检索用原文、返回空 history（生成不带旧轮）。
    """
    if thread_id is None:
        return None, message
    history = await load_thread_history(db, thread_id=thread_id, user_id=user_id)
    if not history:
        return None, message
    if is_topic_shift(message, history):
        return [], message
    retrieval_query = await contextualize_query(message, history)
    return history, retrieval_query
