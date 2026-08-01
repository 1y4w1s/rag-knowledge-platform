"""PDF 文字层版式降噪：跨页重复行（页眉/页脚）+ 页码短行。

B1：只服务 ``parse_pdf`` 散文路径；表格抽取与 OCR 不经过本模块。
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

# 页码行（辅）；条款号由 parser CHAPTER_RE 处理，此处只剔短页码
_PAGE_NUM_RES: tuple[re.Pattern[str], ...] = (
    re.compile(r"^第\s*\d+\s*页(?:\s*/\s*共\s*\d+\s*页)?$"),
    re.compile(r"^(?:Page|PAGE|page)\s*\d+(?:\s*(?:of|/|OF)\s*\d+)?$"),
    re.compile(r"^\d+\s*/\s*\d+$"),
    re.compile(r"^[-–—]?\s*\d+\s*[-–—]?$"),
)

_MAX_BARE_PAGE_NUM_CHARS = 6


@dataclass(frozen=True)
class DenoiseParams:
    header_candidate_lines: int = 2
    footer_candidate_lines: int = 2
    min_pages_for_vote: int = 3
    min_page_ratio: float = 0.5
    max_noise_line_chars: int = 80
    min_keep_chars: int = 30


DEFAULT_PARAMS = DenoiseParams()


def normalize_line(line: str) -> str:
    return re.sub(r"\s+", " ", line.strip())


def normalize_for_vote(line: str) -> str:
    """投票键：折叠空白并把数字换成 #，使「第 3 页」与「第 12 页」同键。"""
    return re.sub(r"\d+", "#", normalize_line(line))


def is_page_number_line(line: str) -> bool:
    text = normalize_line(line)
    if not text:
        return False
    for pat in _PAGE_NUM_RES[:-1]:
        if pat.match(text):
            return True
    # 裸数字页码：限制长度，避免误杀「3.」类短标题
    if len(text) <= _MAX_BARE_PAGE_NUM_CHARS and _PAGE_NUM_RES[-1].match(text):
        return True
    return False


def _nonempty_lines(lines: list[str]) -> list[str]:
    return [ln.strip() for ln in lines if ln.strip()]


def collect_noise_vote_keys(
    pages_lines: list[list[str]],
    params: DenoiseParams = DEFAULT_PARAMS,
) -> set[str]:
    """返回应剔除的投票键（``normalize_for_vote`` 结果）。"""
    n_pages = len(pages_lines)
    if n_pages < params.min_pages_for_vote:
        return set()

    # key -> 出现过的页集合
    page_hits: dict[str, set[int]] = {}
    for page_idx, lines in enumerate(pages_lines):
        nonempty = _nonempty_lines(lines)
        n = len(nonempty)
        if n == 0:
            continue

        # 顶/底候选不得重叠，避免短页把正文中间行打成「重复噪声」
        head_n = min(params.header_candidate_lines, n)
        foot_n = min(params.footer_candidate_lines, n)
        if head_n + foot_n > n:
            # 短页：只取首行 + 末行（若仅 1 行则只取首行）
            candidates = [nonempty[0]]
            if n >= 2:
                candidates.append(nonempty[-1])
        else:
            candidates = nonempty[:head_n] + nonempty[-foot_n:]

        seen_on_page: set[str] = set()
        for raw in candidates:
            if len(normalize_line(raw)) > params.max_noise_line_chars:
                continue
            key = normalize_for_vote(raw)
            if not key or key in seen_on_page:
                continue
            seen_on_page.add(key)
            page_hits.setdefault(key, set()).add(page_idx)

    threshold = max(2, math.ceil(params.min_page_ratio * n_pages))
    return {key for key, pages in page_hits.items() if len(pages) >= threshold}


def filter_page_lines(
    lines: list[str],
    noise_keys: set[str],
    *,
    params: DenoiseParams = DEFAULT_PARAMS,
    strip_page_numbers: bool = True,
) -> list[str]:
    """按噪声键与页码规则过滤；若剩余正文过短则回退原文（安全闸）。"""
    if not noise_keys and not strip_page_numbers:
        return lines

    kept: list[str] = []
    for raw in lines:
        stripped = raw.strip()
        if not stripped:
            kept.append(raw)
            continue
        if strip_page_numbers and is_page_number_line(stripped):
            continue
        if noise_keys and normalize_for_vote(stripped) in noise_keys:
            continue
        kept.append(raw)

    kept_chars = sum(len(ln.strip()) for ln in kept if ln.strip())
    if kept_chars < params.min_keep_chars:
        return lines
    return kept


def denoise_pages_lines(
    pages_lines: list[list[str]],
    *,
    enabled: bool = True,
    params: DenoiseParams = DEFAULT_PARAMS,
) -> list[list[str]]:
    """对整份 PDF 的按页行列表做降噪；关闭时恒等。"""
    if not enabled:
        return pages_lines
    noise_keys = collect_noise_vote_keys(pages_lines, params)
    return [
        filter_page_lines(lines, noise_keys, params=params, strip_page_numbers=True)
        for lines in pages_lines
    ]
