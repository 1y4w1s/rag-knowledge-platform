"""G2 W1：agent 工具级熔断 / 限流 / token 估算基础设施。

W1 只提供可复用基座，不接线 runtime；W2 接入工具级熔断，W3 接入
每轮计数、窗口限流与 metrics 输出。
"""

from __future__ import annotations

import logging
import math
import threading
from collections import defaultdict
from dataclasses import dataclass

from app.core.config import settings
from app.core.retry import get_breaker
from app.services.agent.tools.registry import (
    ALL_AGENT_TOOL_NAMES,
    AgentToolName,
)
from app.services.auth.rate_limit_store import (
    get_rate_limit_backend,
    redis_sliding_allow,
    wall_now,
)

logger = logging.getLogger(__name__)

AGENT_TOOL_BREAKER_PREFIX = "agent_tool"

EXTERNAL_TOOL_NAMES: frozenset[str] = frozenset(
    {AgentToolName.web_search.value}
)

AGENT_TOOL_BREAKER_TOOL_NAMES: frozenset[str] = frozenset(
    ALL_AGENT_TOOL_NAMES - {AgentToolName.sql_query.value}
)


def tool_breaker_name(tool_name: str) -> str:
    """返回 agent_tool:{tool_name}。纯函数，不做 tool 名校验。"""
    return f"{AGENT_TOOL_BREAKER_PREFIX}:{tool_name}"


def ensure_agent_tool_breakers() -> set[str]:
    """预注册全部工具 breaker；重复调用安全，不重置任何 breaker 状态。"""
    overrides = settings.agent_tool_breaker_overrides
    for tool_name in sorted(AGENT_TOOL_BREAKER_TOOL_NAMES):
        tool_override = overrides.get(tool_name)
        if not isinstance(tool_override, dict):
            tool_override = {}
        get_breaker(
            tool_breaker_name(tool_name),
            failure_threshold=tool_override.get("failure_threshold"),
            recovery_timeout=tool_override.get("recovery_timeout"),
        )
    return {tool_breaker_name(t) for t in AGENT_TOOL_BREAKER_TOOL_NAMES}


def resolve_tool_run_limit(tool_name: str) -> int | None:
    """返回该工具每轮最大调用次数；None 表示不限制（受 max_steps 约束）。"""
    override = settings.agent_tool_max_calls_per_run_override.get(tool_name)
    if override is not None:
        return override if override > 0 else None
    if tool_name == AgentToolName.web_search.value:
        return settings.agent_max_external_calls_per_conversation
    return None


def tool_window_limit(tool_name: str) -> tuple[int, int] | None:
    """返回 (max, window_seconds)；未启用 / 未配置返回 None。"""
    if not settings.agent_tool_window_rate_limit_enabled:
        return None
    cfg = settings.agent_tool_window_rate_limit.get(tool_name)
    if not isinstance(cfg, dict):
        return None
    max_requests = cfg.get("max")
    window_seconds = cfg.get("window_seconds")
    if not isinstance(max_requests, int) or not isinstance(window_seconds, int):
        return None
    if max_requests <= 0 or window_seconds <= 0:
        return None
    return max_requests, window_seconds


def tool_window_limit_key(tool_name: str) -> str:
    """固定全局窗口键：rl:agent_tool:{tool}:global。"""
    return f"rl:{tool_breaker_name(tool_name)}:global"


_window_timestamps: dict[str, list[float]] = defaultdict(list)
_window_lock = threading.Lock()


def _allow_tool_window_memory(
    key: str,
    *,
    max_requests: int,
    window_seconds: int,
    now: float,
) -> bool:
    window_start = now - window_seconds
    with _window_lock:
        kept = [t for t in _window_timestamps.get(key, []) if t > window_start]
        if len(kept) >= max_requests:
            _window_timestamps[key] = kept
            return False
        kept.append(now)
        _window_timestamps[key] = kept
        return True


def _inc_tool_window_rejected(tool_name: str) -> None:
    from app.services.observability.metrics_registry import (
        inc_agent_tool_window_rejected,
    )

    inc_agent_tool_window_rejected(tool_name)


def _inc_rate_limit_backend_fallback() -> None:
    from app.services.observability.metrics_registry import (
        inc_rate_limit_backend_fallback,
    )

    inc_rate_limit_backend_fallback("agent_tool")


async def allow_tool_window(tool_name: str, *, now: float | None = None) -> bool:
    """True=放行并计数；False=达到全局窗口上限（拒绝）。"""
    limits = tool_window_limit(tool_name)
    if limits is None:
        return True
    max_requests, window_seconds = limits
    key = tool_window_limit_key(tool_name)

    if get_rate_limit_backend() == "redis":
        try:
            allowed = await redis_sliding_allow(
                key,
                max_requests=max_requests,
                window_seconds=window_seconds,
                now=now,
            )
        except Exception as exc:
            logger.warning("Redis 工具窗口限流失败，回退 memory: %s", exc)
            _inc_rate_limit_backend_fallback()
            allowed = _allow_tool_window_memory(
                key,
                max_requests=max_requests,
                window_seconds=window_seconds,
                now=wall_now(now),
            )
        if not allowed:
            _inc_tool_window_rejected(tool_name)
        return allowed

    allowed = _allow_tool_window_memory(
        key,
        max_requests=max_requests,
        window_seconds=window_seconds,
        now=wall_now(now),
    )
    if not allowed:
        _inc_tool_window_rejected(tool_name)
    return allowed


def reset_tool_window_limits() -> None:
    """测试隔离：清空内存滑动窗口。"""
    with _window_lock:
        _window_timestamps.clear()


TOKEN_PER_CJK_CHAR = 1
OTHER_CHARS_PER_TOKEN = 4


def _is_cjk(ch: str) -> bool:
    code = ord(ch)
    return (
        0x3400 <= code <= 0x4DBF
        or 0x4E00 <= code <= 0x9FFF
        or 0xF900 <= code <= 0xFAFF
        or 0x20000 <= code <= 0x2A6DF
    )


def estimate_tokens(text: str) -> int:
    """CJK 字符 1 token/字；其余非空白字符 ceil(n/4)；空串/纯空白为 0。"""
    if not text.strip():
        return 0
    cjk_chars = sum(1 for ch in text if _is_cjk(ch))
    other_chars = sum(1 for ch in text if not ch.isspace() and not _is_cjk(ch))
    return cjk_chars * TOKEN_PER_CJK_CHAR + math.ceil(
        other_chars / OTHER_CHARS_PER_TOKEN
    )


@dataclass(frozen=True, slots=True)
class PlannerTokenEstimate:
    prompt_tokens: int
    response_tokens: int

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.response_tokens


def estimate_planner_tokens(prompt: str, response: str) -> PlannerTokenEstimate:
    """prompt/response 分别估算，供 planner 调用计数使用。"""
    return PlannerTokenEstimate(
        prompt_tokens=estimate_tokens(prompt),
        response_tokens=estimate_tokens(response),
    )
