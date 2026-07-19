"""Prometheus /metrics 端点（不含 prometheus_client 依赖）。

输出格式：
  # HELP ruige_llm_calls_total Total LLM call attempts
  # TYPE ruige_llm_calls_total counter
  ruige_llm_calls_total{status="success"} 42
  ruige_llm_calls_total{status="failure"} 3
"""

from __future__ import annotations

import time

from fastapi import APIRouter

from app.core.degradation import DegradationLevel, assess_degradation, current_degradation_duration, get_degradation_events, degradation_label
from app.core.retry import get_breaker

router = APIRouter(tags=["metrics"])

# ── 进程级计数器 ──────────────────────────────────────────────────────

_chats_total: int = 0
_llm_calls_success: int = 0
_llm_calls_failure: int = 0
_start_time: float = time.time()


def inc_chats_total() -> None:
    global _chats_total
    _chats_total += 1


def inc_llm_success() -> None:
    global _llm_calls_success
    _llm_calls_success += 1


def inc_llm_failure() -> None:
    global _llm_calls_failure
    _llm_calls_failure += 1


# ── 格式化 ────────────────────────────────────────────────────────────

def _label(key: str, value: str) -> str:
    return f'{key}="{value}"'


@router.get("/metrics")
async def metrics() -> str:
    lines: list[str] = []
    uptime = time.time() - _start_time

    # 基本信息
    lines.append("# HELP ruige_uptime_seconds Process uptime")
    lines.append("# TYPE ruige_uptime_seconds gauge")
    lines.append(f"ruige_uptime_seconds {uptime:.0f}")
    lines.append("")

    # 计数器
    lines.append("# HELP ruige_chats_total Total chat requests handled")
    lines.append("# TYPE ruige_chats_total counter")
    lines.append(f"ruige_chats_total {_chats_total}")
    lines.append("")

    lines.append("# HELP ruige_llm_calls_total Total LLM API calls")
    lines.append("# TYPE ruige_llm_calls_total counter")
    lines.append(f'ruige_llm_calls_total{{{_label("status","success")}}} {_llm_calls_success}')
    lines.append(f'ruige_llm_calls_total{{{_label("status","failure")}}} {_llm_calls_failure}')
    lines.append("")

    # 降级等级
    level = assess_degradation()
    duration = current_degradation_duration()
    lines.append("# HELP ruige_degradation_level Current degradation level (0-4)")
    lines.append("# TYPE ruige_degradation_level gauge")
    lines.append(f'ruige_degradation_level{{{_label("label",degradation_label(level))}}} {int(level)}')
    lines.append("# HELP ruige_degradation_duration_seconds Seconds at current level")
    lines.append("# TYPE ruige_degradation_duration_seconds gauge")
    lines.append(f'ruige_degradation_duration_seconds {duration:.0f}')
    lines.append("")

    # 熔断器
    lines.append("# HELP ruige_circuit_breaker_info Circuit breaker per service")
    lines.append("# TYPE ruige_circuit_breaker_info gauge")
    for name in ("deepseek_llm", "tongyi_rerank", "tongyi_embed", "agent_tool_dispatch"):
        try:
            cb = get_breaker(name)
            st = cb.status()
            lines.append(
                f'ruige_circuit_breaker_info{{{_label("breaker",name)},{_label("state",st["state"])}}} {st["failures"]}'
            )
        except Exception:
            pass
    lines.append("")

    # 最近降级事件
    events = get_degradation_events(limit=5)
    lines.append("# HELP ruige_degradation_events Recent degradation level changes")
    lines.append("# TYPE ruige_degradation_events gauge")
    for ev in events:
        from_l = str(ev["old_level"])
        to_l = str(ev["new_level"])
        lines.append(
            f'ruige_degradation_events{{{_label("from_level",from_l)},{_label("to_level",to_l)},{_label("label",ev["label"])}}} {ev["timestamp"]:.0f}'
        )

    return "\n".join(lines) + "\n"
