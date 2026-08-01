"""A3 路由：问法抽取 + 加法注入（无 DB）。"""

from __future__ import annotations

import re
from uuid import UUID

from app.core.config import settings
from app.services.rag.types import _RecallRow

_CLAUSE_DECIMAL = re.compile(r"\b\d+\.\d+\b")
_CLAUSE_CN = re.compile(r"第[一二三四五六七八九十百千零〇\d]+条")
_ASCII_TOKEN = re.compile(r"[A-Za-z][A-Za-z0-9_-]{1,31}")
_CJK_RUN = re.compile(r"[\u4e00-\u9fff]{2,8}")

_STOP = frozenset(
    {
        "什么",
        "多少",
        "怎么",
        "如何",
        "是否",
        "哪些",
        "有没有",
        "请问",
        "帮忙",
        "一下",
        "那个",
        "这个",
        "一个",
        "可以",
        "需要",
        "应该",
        "如果",
        "还是",
        "或者",
        "以及",
        "同时",
        "因为",
        "所以",
        "为什么",
        "怎样",
        "哪里",
        "谁的",
        "多少钱",
        "the",
        "and",
        "for",
        "with",
        "what",
        "how",
        "are",
        "is",
    }
)


def extract_clause_tokens(query: str) -> list[str]:
    q = (query or "").strip()
    if not q:
        return []
    seen: set[str] = set()
    out: list[str] = []
    for m in _CLAUSE_DECIMAL.findall(q):
        if m not in seen:
            seen.add(m)
            out.append(m)
    for m in _CLAUSE_CN.findall(q):
        if m not in seen:
            seen.add(m)
            out.append(m)
    return out


def extract_filename_cues(query: str) -> list[str]:
    """问法中可能对齐文档名的 token（通用，不写死库内文件名）。"""
    q = (query or "").strip()
    if not q:
        return []
    seen: set[str] = set()
    out: list[str] = []
    for m in _ASCII_TOKEN.findall(q):
        key = m.lower()
        if key in _STOP or key in seen:
            continue
        seen.add(key)
        out.append(m)
    try:
        import jieba

        for m in jieba.lcut(q):
            m = m.strip()
            if len(m) < 2 or m in _STOP or m in seen:
                continue
            if _ASCII_TOKEN.fullmatch(m):
                continue  # 已由 ASCII 路径收录
            if not re.search(r"[\u4e00-\u9fff]", m):
                continue
            seen.add(m)
            out.append(m)
    except Exception:
        for m in _CJK_RUN.findall(q):
            if m in _STOP or m in seen:
                continue
            seen.add(m)
            out.append(m)
    return out[:12]


def should_attempt_route(query: str) -> bool:
    return bool(extract_clause_tokens(query) or extract_filename_cues(query))


def escape_ilike(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def inject_route_hits(
    fused: list[tuple[UUID, float]],
    merged: dict[UUID, _RecallRow],
    route_rows: list[_RecallRow],
    *,
    extra_slots: int | None = None,
    protect_top: int = 3,
) -> tuple[list[tuple[UUID, float]], dict[UUID, _RecallRow]]:
    """高精度路由写入 Top-N 窗口尾部（不挤掉 Top-`protect_top`）。

    与「纯追加到 N 之外」不同：保证条款/专名命中落在诊断 Hit@20 / 送精排池内。
    """
    slots = extra_slots if extra_slots is not None else settings.clause_route_extra_slots
    if not route_rows or slots <= 0 or not fused:
        return fused, merged

    base_ids = {cid for cid, _ in fused}
    newcomers: list[tuple[UUID, float]] = []
    for row in route_rows:
        cid = row.chunk.id
        if cid in base_ids:
            continue
        if cid not in merged:
            merged[cid] = row
        newcomers.append((cid, 0.0))
        base_ids.add(cid)
        if len(newcomers) >= slots:
            break
    if not newcomers:
        return fused, merged

    protect = min(protect_top, len(fused))
    replaceable = max(0, len(fused) - protect)
    take = min(len(newcomers), replaceable, slots)
    if take <= 0:
        # 池太短无法替换：退回追加（供 rerank 大池）
        return list(fused) + newcomers[:slots], merged
    kept = list(fused[: len(fused) - take])
    return kept + newcomers[:take], merged
