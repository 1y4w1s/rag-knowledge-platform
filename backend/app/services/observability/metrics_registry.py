"""进程级 Prometheus 计数器 / 积压查询（无 prometheus_client）。

由 ``api/metrics`` 导出；对话路径调用 ``inc_*``；限流 429 调用 ``inc_rate_limit_rejected``。
"""
from __future__ import annotations

import time
from collections import defaultdict

from sqlalchemy import func, select

from app.core.latency import all_tracker_stats
from app.models.document import Document
from app.models.enums import DocumentStatus

# ── 进程级计数器 ──────────────────────────────────────────────────────

_chats_total: int = 0
_llm_calls_success: int = 0
_llm_calls_failure: int = 0
_chat_answers: dict[tuple[str, str], int] = defaultdict(int)
_rate_limit_rejected: dict[str, int] = defaultdict(int)
_start_time: float = time.time()

# NW-26：限流 429 五档 → T6-O-7：补 register（注册/邀请码校验复用桶）+ global（全局限流中间件）
RATE_LIMIT_REJECT_KINDS = (
    "login",
    "forgot",
    "chat",
    "upload",
    "search",
    "register",
    "global",
)

_BACKLOG_TTL_S = 10.0
_backlog_cache: dict[str, int] | None = None
_backlog_cached_at: float = 0.0

_LATENCY_MIN_COUNT = 5
_QUANTILES = ("p50", "p95", "p99")
_BACKLOG_STATUSES = (DocumentStatus.queued, DocumentStatus.processing)


def uptime_seconds() -> float:
    return time.time() - _start_time


def chats_total() -> int:
    return _chats_total


def llm_success_count() -> int:
    return _llm_calls_success


def llm_failure_count() -> int:
    return _llm_calls_failure


def chat_answers_snapshot() -> dict[tuple[str, str], int]:
    return dict(_chat_answers)


def inc_chats_total() -> None:
    global _chats_total
    _chats_total += 1


def inc_llm_success() -> None:
    global _llm_calls_success
    _llm_calls_success += 1


def inc_llm_failure() -> None:
    global _llm_calls_failure
    _llm_calls_failure += 1


def inc_chat_answer(confidence: str, mode: str) -> None:
    """对话终态置信度计数（confidence=refuse|low|normal · mode=fast|thorough）。"""
    _chat_answers[(confidence, mode)] += 1


def inc_rate_limit_rejected(kind: str) -> None:
    """限流拒绝（429）计数。kind=login|forgot|chat|upload|search|register|global。"""
    if kind not in RATE_LIMIT_REJECT_KINDS:
        return
    _rate_limit_rejected[kind] += 1


def rate_limit_rejected_snapshot() -> dict[str, int]:
    return dict(_rate_limit_rejected)


def reset_process_counters_for_tests() -> None:
    """仅测试用：清零进程计数器与积压缓存。"""
    global _chats_total, _llm_calls_success, _llm_calls_failure
    global _backlog_cache, _backlog_cached_at
    _chats_total = 0
    _llm_calls_success = 0
    _llm_calls_failure = 0
    _chat_answers.clear()
    _rate_limit_rejected.clear()
    _backlog_cache = None
    _backlog_cached_at = 0.0
    from app.services.rag.cache import _reset_cache_hit_counters
    _reset_cache_hit_counters()


def _stage_label(tracker_name: str) -> str:
    if tracker_name.startswith("retrieval."):
        return tracker_name[len("retrieval.") :]
    return tracker_name


def latency_gauge_lines(*, min_count: int = _LATENCY_MIN_COUNT) -> list[str]:
    """从 LatencyTracker 导出分位 gauge（与 /health/detailed 同源）。"""
    lines: list[str] = [
        "# HELP ruige_latency_ms Retrieval stage latency percentiles (ms)",
        "# TYPE ruige_latency_ms gauge",
    ]
    stats_by_name = all_tracker_stats(min_count=min_count)
    for name, st in stats_by_name.items():
        if "p50" not in st:
            continue
        stage = _stage_label(name)
        for q in _QUANTILES:
            if q not in st:
                continue
            lines.append(
                f'ruige_latency_ms{{stage="{stage}",quantile="{q}"}} {st[q]}'
            )
    return lines


async def documents_backlog_counts() -> dict[str, int]:
    """全局 queued/processing 文档数（短 TTL 缓存；多副本 scrape 用 max）。"""
    global _backlog_cache, _backlog_cached_at
    now = time.time()
    if _backlog_cache is not None and (now - _backlog_cached_at) < _BACKLOG_TTL_S:
        return dict(_backlog_cache)

    counts = {s.value: 0 for s in _BACKLOG_STATUSES}
    try:
        from app.core.database import SessionLocal

        async with SessionLocal() as db:
            result = await db.execute(
                select(Document.status, func.count())
                .where(Document.status.in_(_BACKLOG_STATUSES))
                .group_by(Document.status)
            )
            for status, n in result.all():
                key = status.value if hasattr(status, "value") else str(status)
                if key in counts:
                    counts[key] = int(n)
    except Exception:
        # scrape 不因 DB 短暂失败而 500；保留上次缓存或 0
        if _backlog_cache is not None:
            return dict(_backlog_cache)

    _backlog_cache = counts
    _backlog_cached_at = now
    return dict(counts)


def backlog_gauge_lines(counts: dict[str, int]) -> list[str]:
    lines = [
        "# HELP ruige_documents_backlog Documents in ingestion backlog",
        "# TYPE ruige_documents_backlog gauge",
    ]
    for status in ("queued", "processing"):
        lines.append(
            f'ruige_documents_backlog{{status="{status}"}} {counts.get(status, 0)}'
        )
    return lines


def chat_answers_counter_lines() -> list[str]:
    lines = [
        "# HELP ruige_chat_answers_total Chat answers by confidence and mode",
        "# TYPE ruige_chat_answers_total counter",
    ]
    # 固定输出三档 × 两模式，便于 scrape 稳定
    for confidence in ("refuse", "low", "normal"):
        for mode in ("fast", "thorough"):
            n = _chat_answers.get((confidence, mode), 0)
            lines.append(
                f'ruige_chat_answers_total{{confidence="{confidence}",mode="{mode}"}} {n}'
            )
    return lines


def rate_limit_rejected_counter_lines() -> list[str]:
    lines = [
        "# HELP ruige_rate_limit_rejected_total Rate-limit rejections (HTTP 429)",
        "# TYPE ruige_rate_limit_rejected_total counter",
    ]
    for kind in RATE_LIMIT_REJECT_KINDS:
        n = _rate_limit_rejected.get(kind, 0)
        lines.append(f'ruige_rate_limit_rejected_total{{kind="{kind}"}} {n}')
    return lines


def cache_hit_counter_lines() -> list[str]:
    """缓存命中/未命中计数。kind=query_chunks|llm_response。"""
    from app.services.rag.cache import cache_hit_snapshot

    snap = cache_hit_snapshot()
    lines = [
        "# HELP ruige_cache_hit_total Cache hit/miss by kind",
        "# TYPE ruige_cache_hit_total counter",
    ]
    for kind in ("query_chunks", "query_chunks_miss", "llm_response", "llm_response_miss"):
        n = snap.get(kind, 0)
        lines.append(f'ruige_cache_hit_total{{kind="{kind}"}} {n}')
    return lines
