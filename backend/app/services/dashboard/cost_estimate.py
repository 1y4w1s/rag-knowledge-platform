"""Eval-Ops M4 · 用量成本粗估（非计费）。

单价为值班口播示意，须与 docs/tasks/eval-M4-cost-model.md 同步。
禁止在此模块实现扣费 / 余额 / 积分。
"""

from __future__ import annotations

# 示意单价（CNY）· 以厂商官网为准 · 见 eval-M4-cost-model.md §2
COST_PER_ASSISTANT_REPLY_CNY = 0.02
COST_PER_CHUNK_EMBED_CNY = 0.0001  # 文档手算用；7 日 API 粗估不含历史 chunk

COST_ESTIMATE_NOTE = (
    "粗估非账单：近7日助手回复×¥0.02/次；以厂商控制台为准。详见 docs/tasks/eval-M4-cost-model.md"
)


def estimate_chat_cost_cny_7d(assistant_replies: int) -> float:
    """近 7 日对话 API 粗估（CNY），保留 2 位小数。"""
    if assistant_replies <= 0:
        return 0.0
    return round(assistant_replies * COST_PER_ASSISTANT_REPLY_CNY, 2)


def estimate_embed_cost_cny(chunk_count: int) -> float:
    """入库嵌入一次性粗估（文档手算；API 7 日字段不用）。"""
    if chunk_count <= 0:
        return 0.0
    return round(chunk_count * COST_PER_CHUNK_EMBED_CNY, 4)
