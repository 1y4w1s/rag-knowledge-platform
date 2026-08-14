"""进程级 Prometheus 计数器 / 积压查询（无 prometheus_client）。

由 ``api/metrics`` 导出；对话路径调用 ``inc_*``；限流 429 调用 ``inc_rate_limit_rejected``。
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict

from sqlalchemy import func, select

from app.core.latency import LatencyTracker, all_tracker_stats
from app.models.document import Document
from app.models.enums import DocumentStatus
from app.services.rag.chat_llm import ChatUsage

# ── 进程级计数器 ──────────────────────────────────────────────────────

_chats_total: int = 0
_llm_calls_success: int = 0
_llm_calls_failure: int = 0
_chat_answers: dict[tuple[str, str], int] = defaultdict(int)
_rate_limit_rejected: dict[str, int] = defaultdict(int)
_rate_limit_backend_fallback: dict[str, int] = defaultdict(int)
_agent_tool_calls: dict[tuple[str, str, bool], int] = defaultdict(int)
_agent_tool_window_rejected: dict[str, int] = defaultdict(int)
_agent_llm_planner_calls: dict[tuple[str, str], int] = defaultdict(int)
_agent_llm_planner_tokens: dict[str, int] = defaultdict(int)  # prompt | response
_agent_llm_planner_usage: dict[tuple[str, str, str], int] = defaultdict(int)
_llm_chat_usage: dict[tuple[str, str], int] = defaultdict(int)
_agent_tool_latency: dict[str, LatencyTracker] = {}
_agent_tool_latency_lock = threading.Lock()
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

# P1-S4：Redis 限流后端失败回退 memory 的计数维度（module=login|api）。
# 与 RATE_LIMIT_REJECT_KINDS 不同：这是降级告警面，不是 429 拒绝面。
RATE_LIMIT_FALLBACK_MODULES = ("login", "api", "agent_tool")

AGENT_TOOL_STATUSES = ("ok", "failed", "limited", "breaker_open")
AGENT_PLANNER_STAGES = ("plan", "replan")
AGENT_PLANNER_STATUSES = ("ok", "failed")
AGENT_PLANNER_USAGE_PROVIDERS = ("deepseek", "tongyi")
LLM_CHAT_USAGE_KINDS = ("prompt", "completion", "cache_hit", "cache_miss")

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


def inc_rate_limit_backend_fallback(module: str) -> None:
    """Redis 限流后端失败、回退 memory 时计数（module=login|api），供降级告警。"""
    if module not in RATE_LIMIT_FALLBACK_MODULES:
        return
    _rate_limit_backend_fallback[module] += 1


def rate_limit_rejected_snapshot() -> dict[str, int]:
    return dict(_rate_limit_rejected)


def rate_limit_backend_fallback_snapshot() -> dict[str, int]:
    return dict(_rate_limit_backend_fallback)


def reset_process_counters_for_tests() -> None:
    """仅测试用：清零进程计数器与积压缓存。"""
    global _chats_total, _llm_calls_success, _llm_calls_failure
    global _backlog_cache, _backlog_cached_at
    _chats_total = 0
    _llm_calls_success = 0
    _llm_calls_failure = 0
    _chat_answers.clear()
    _rate_limit_rejected.clear()
    _rate_limit_backend_fallback.clear()
    _agent_tool_calls.clear()
    _agent_tool_window_rejected.clear()
    _agent_llm_planner_calls.clear()
    _agent_llm_planner_tokens.clear()
    _agent_llm_planner_usage.clear()
    _llm_chat_usage.clear()
    with _agent_tool_latency_lock:
        _agent_tool_latency.clear()
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


def embedding_en_coverage_gauge_lines(stats: dict[str, object]) -> list[str]:
    lines = [
        "# HELP ruige_embedding_en_coverage Share of searchable chunks with embedding_en",
        "# TYPE ruige_embedding_en_coverage gauge",
        f"ruige_embedding_en_coverage {float(stats.get('embedding_en_coverage', 0.0))}",
        "# HELP ruige_embedding_en_chunks Searchable chunks with embedding_en",
        "# TYPE ruige_embedding_en_chunks gauge",
        f"ruige_embedding_en_chunks {int(stats.get('embedding_en_chunks', 0))}",
        "# HELP ruige_searchable_chunks Searchable chunks",
        "# TYPE ruige_searchable_chunks gauge",
        f"ruige_searchable_chunks {int(stats.get('searchable_chunks', 0))}",
    ]
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


def rate_limit_backend_fallback_counter_lines() -> list[str]:
    lines = [
        "# HELP ruige_rate_limit_backend_fallback_total Redis rate-limit backend fallbacks to memory",
        "# TYPE ruige_rate_limit_backend_fallback_total counter",
    ]
    for module in RATE_LIMIT_FALLBACK_MODULES:
        n = _rate_limit_backend_fallback.get(module, 0)
        lines.append(
            f'ruige_rate_limit_backend_fallback_total{{module="{module}"}} {n}'
        )
    return lines


def inc_agent_tool_call(tool: str, status: str, *, external: bool = False) -> None:
    """工具调用计数；status 不在 AGENT_TOOL_STATUSES 时忽略。"""
    if status not in AGENT_TOOL_STATUSES:
        return
    _agent_tool_calls[(tool, status, external)] += 1


def agent_tool_calls_snapshot() -> dict[tuple[str, str, bool], int]:
    return dict(_agent_tool_calls)


def agent_tool_calls_counter_lines() -> list[str]:
    lines = [
        "# HELP ruige_agent_tool_calls_total Agent tool executions by tool and status",
        "# TYPE ruige_agent_tool_calls_total counter",
    ]
    for (tool, status, external), n in sorted(_agent_tool_calls.items()):
        ext = "true" if external else "false"
        lines.append(
            f'ruige_agent_tool_calls_total{{tool="{tool}",status="{status}",'
            f'external="{ext}"}} {n}'
        )
    return lines


def inc_agent_tool_window_rejected(tool: str) -> None:
    """窗口限流拒绝计数（tool 维度）。"""
    _agent_tool_window_rejected[tool] += 1


def agent_tool_window_rejected_snapshot() -> dict[str, int]:
    return dict(_agent_tool_window_rejected)


def agent_tool_window_rejected_counter_lines() -> list[str]:
    lines = [
        "# HELP ruige_agent_tool_window_rejected_total Agent tool window rate-limit rejections",
        "# TYPE ruige_agent_tool_window_rejected_total counter",
    ]
    for tool, n in sorted(_agent_tool_window_rejected.items()):
        lines.append(
            f'ruige_agent_tool_window_rejected_total{{tool="{tool}"}} {n}'
        )
    return lines


def inc_agent_llm_planner_call(
    stage: str,
    status: str,
    *,
    prompt_tokens: int = 0,
    response_tokens: int = 0,
) -> None:
    """planner LLM 调用计数；stage/status 不在白名单时忽略，token 按 kind 累加。"""
    if stage not in AGENT_PLANNER_STAGES or status not in AGENT_PLANNER_STATUSES:
        return
    _agent_llm_planner_calls[(stage, status)] += 1
    if prompt_tokens > 0:
        _agent_llm_planner_tokens["prompt"] += prompt_tokens
    if response_tokens > 0:
        _agent_llm_planner_tokens["response"] += response_tokens


def agent_llm_planner_calls_snapshot() -> dict[tuple[str, str], int]:
    """(stage, status) -> count，供测试。"""
    return dict(_agent_llm_planner_calls)


def agent_llm_planner_tokens_snapshot() -> dict[str, int]:
    """kind -> count，供测试。"""
    return dict(_agent_llm_planner_tokens)


def agent_llm_planner_calls_counter_lines() -> list[str]:
    lines = [
        "# HELP ruige_agent_llm_planner_calls_total LLM planner calls by stage and status",
        "# TYPE ruige_agent_llm_planner_calls_total counter",
    ]
    for stage in AGENT_PLANNER_STAGES:
        for status in AGENT_PLANNER_STATUSES:
            n = _agent_llm_planner_calls.get((stage, status), 0)
            lines.append(
                f'ruige_agent_llm_planner_calls_total{{stage="{stage}",'
                f'status="{status}"}} {n}'
            )
    return lines


def agent_llm_planner_tokens_counter_lines() -> list[str]:
    lines = [
        "# HELP ruige_agent_llm_planner_tokens_total Estimated planner LLM tokens by kind",
        "# TYPE ruige_agent_llm_planner_tokens_total counter",
    ]
    for kind in ("prompt", "response"):
        n = _agent_llm_planner_tokens.get(kind, 0)
        lines.append(f'ruige_agent_llm_planner_tokens_total{{kind="{kind}"}} {n}')
    return lines


def inc_agent_llm_planner_usage(stage: str, usage: ChatUsage) -> None:
    """planner 真实 usage 计数（stage × provider × kind）；无真实值/非法 stage 忽略。"""
    if stage not in AGENT_PLANNER_STAGES or not usage.has_value:
        return
    _agent_llm_planner_usage[(stage, usage.provider, "prompt")] += usage.prompt_tokens
    _agent_llm_planner_usage[(stage, usage.provider, "completion")] += (
        usage.completion_tokens
    )
    _agent_llm_planner_usage[(stage, usage.provider, "cache_hit")] += (
        usage.prompt_cache_hit_tokens
    )
    _agent_llm_planner_usage[(stage, usage.provider, "cache_miss")] += (
        usage.prompt_cache_miss_tokens
    )


def agent_llm_planner_usage_snapshot() -> dict[tuple[str, str, str], int]:
    """(stage, provider, kind) -> tokens，供测试。"""
    return dict(_agent_llm_planner_usage)


def agent_llm_planner_usage_counter_lines() -> list[str]:
    """固定 2 stage × 2 provider × 4 kind 行；无真实 usage 时输出 0。"""
    lines = [
        "# HELP ruige_agent_llm_planner_usage_tokens_total "
        "LLM planner real usage tokens by stage, provider and kind",
        "# TYPE ruige_agent_llm_planner_usage_tokens_total counter",
    ]
    for stage in AGENT_PLANNER_STAGES:
        for provider in AGENT_PLANNER_USAGE_PROVIDERS:
            for kind in LLM_CHAT_USAGE_KINDS:
                n = _agent_llm_planner_usage.get((stage, provider, kind), 0)
                lines.append(
                    f'ruige_agent_llm_planner_usage_tokens_total{{stage="{stage}",'
                    f'provider="{provider}",kind="{kind}"}} {n}'
                )
    return lines


def inc_llm_chat_usage(provider: str, usage: ChatUsage) -> None:
    """全局 chat LLM 真实 usage 计数（provider × kind）；无真实值忽略。"""
    if not usage.has_value:
        return
    _llm_chat_usage[(provider, "prompt")] += usage.prompt_tokens
    _llm_chat_usage[(provider, "completion")] += usage.completion_tokens
    _llm_chat_usage[(provider, "cache_hit")] += usage.prompt_cache_hit_tokens
    _llm_chat_usage[(provider, "cache_miss")] += usage.prompt_cache_miss_tokens


def llm_chat_usage_snapshot() -> dict[tuple[str, str], int]:
    """(provider, kind) -> tokens，供测试。"""
    return dict(_llm_chat_usage)


def llm_chat_usage_counter_lines() -> list[str]:
    lines = [
        "# HELP ruige_llm_chat_usage_tokens_total Chat LLM real usage tokens by provider and kind",
        "# TYPE ruige_llm_chat_usage_tokens_total counter",
    ]
    for (provider, kind), n in sorted(_llm_chat_usage.items()):
        lines.append(
            f'ruige_llm_chat_usage_tokens_total{{provider="{provider}",'
            f'kind="{kind}"}} {n}'
        )
    return lines


def record_agent_tool_latency(tool: str, latency_ms: float) -> None:
    """按工具记录 LatencyTracker 观测值。"""
    with _agent_tool_latency_lock:
        tracker = _agent_tool_latency.get(tool)
        if tracker is None:
            tracker = LatencyTracker(name=f"agent_tool.{tool}")
            _agent_tool_latency[tool] = tracker
    tracker.record(latency_ms)


def agent_tool_latency_snapshot() -> dict[str, dict]:
    """tool -> tracker stats，供测试。"""
    with _agent_tool_latency_lock:
        return {
            name: dict(tracker.stats())
            for name, tracker in sorted(_agent_tool_latency.items())
        }


def agent_tool_latency_gauge_lines(
    *,
    min_count: int = _LATENCY_MIN_COUNT,
) -> list[str]:
    """导出 ruige_agent_tool_latency_ms{tool,quantile}。"""
    lines = [
        "# HELP ruige_agent_tool_latency_ms Agent tool latency percentiles (ms)",
        "# TYPE ruige_agent_tool_latency_ms gauge",
    ]
    with _agent_tool_latency_lock:
        items = sorted(_agent_tool_latency.items())
    for tool, tracker in items:
        st = tracker.stats(min_count=min_count)
        if "p50" not in st:
            continue
        for q in _QUANTILES:
            if q in st:
                lines.append(
                    f'ruige_agent_tool_latency_ms{{tool="{tool}",quantile="{q}"}} {st[q]}'
                )
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
