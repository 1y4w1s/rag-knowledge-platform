"""Prometheus /metrics 端点（不含 prometheus_client 依赖）。

输出格式：
  # HELP ruige_llm_calls_total Total LLM call attempts
  # TYPE ruige_llm_calls_total counter
  ruige_llm_calls_total{status="success"} 42
  ruige_llm_calls_total{status="failure"} 3
"""

from __future__ import annotations

import hmac

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response

from app.core.config import settings

from app.core.degradation import (
    assess_degradation,
    current_degradation_duration,
    degradation_label,
    get_degradation_events,
)
from app.core.retry import get_breaker
from app.services.observability.metrics_registry import (
    backlog_gauge_lines,
    cache_hit_counter_lines,
    chat_answers_counter_lines,
    chats_total,
    documents_backlog_counts,
    inc_chat_answer,
    inc_chats_total,
    inc_llm_failure,
    inc_llm_success,
    latency_gauge_lines,
    llm_failure_count,
    llm_success_count,
    rate_limit_rejected_counter_lines,
    uptime_seconds,
)

router = APIRouter(tags=["metrics"])

# 对外保持原 import 路径（对话路径 / 测试）
__all__ = [
    "router",
    "inc_chats_total",
    "inc_llm_success",
    "inc_llm_failure",
    "inc_chat_answer",
]

def require_metrics_token(request: Request) -> None:
    """阻断匿名读取 /metrics：需持有 ``METRICS_BEARER_TOKEN``（运维/监控专用静态令牌）。

    保持 /metrics 不在 /api/v1 前缀下，避免全局 JWTAuthMiddleware 强制用户 JWT 而破坏
    Prometheus 抓取；改由本路由级依赖校验静态令牌，未配置则 fail-closed 拒绝。
    """
    expected = settings.metrics_bearer_token
    if not expected:
        raise HTTPException(status_code=401, detail="指标端点未启用")
    token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
    if not token or not hmac.compare_digest(token, expected):
        raise HTTPException(status_code=401, detail="未授权")


_METRICS_MEDIA = "text/plain; version=0.0.4; charset=utf-8"


def _label(key: str, value: str) -> str:
    return f'{key}="{value}"'


@router.get("/metrics", dependencies=[Depends(require_metrics_token)])
async def metrics() -> Response:
    lines: list[str] = []

    lines.append("# HELP ruige_uptime_seconds Process uptime")
    lines.append("# TYPE ruige_uptime_seconds gauge")
    lines.append(f"ruige_uptime_seconds {uptime_seconds():.0f}")
    lines.append("")

    lines.append("# HELP ruige_chats_total Total chat requests handled")
    lines.append("# TYPE ruige_chats_total counter")
    lines.append(f"ruige_chats_total {chats_total()}")
    lines.append("")

    lines.append("# HELP ruige_llm_calls_total Total LLM API calls")
    lines.append("# TYPE ruige_llm_calls_total counter")
    lines.append(
        f'ruige_llm_calls_total{{{_label("status","success")}}} {llm_success_count()}'
    )
    lines.append(
        f'ruige_llm_calls_total{{{_label("status","failure")}}} {llm_failure_count()}'
    )
    lines.append("")

    lines.extend(chat_answers_counter_lines())
    lines.append("")

    lines.extend(rate_limit_rejected_counter_lines())
    lines.append("")

    # Celery 队列长度（死信 / 待处理）
    try:
        from app.core.redis import get_redis as _redis
        r = await _redis()
        for q in ("celery", "celery.dead"):
            qlen = await r.llen(q)
            lines.append(f'ruige_celery_queue_length{{queue="{q}"}} {qlen}')
        lines.append("")
    except Exception:
        pass

    lines.extend(cache_hit_counter_lines())
    lines.append("")

    lines.extend(latency_gauge_lines())
    lines.append("")

    backlog = await documents_backlog_counts()
    lines.extend(backlog_gauge_lines(backlog))
    lines.append("")

    level = assess_degradation()
    duration = current_degradation_duration()
    lines.append("# HELP ruige_degradation_level Current degradation level (0-4)")
    lines.append("# TYPE ruige_degradation_level gauge")
    lines.append(
        f'ruige_degradation_level{{{_label("label",degradation_label(level))}}} {int(level)}'
    )
    lines.append("# HELP ruige_degradation_duration_seconds Seconds at current level")
    lines.append("# TYPE ruige_degradation_duration_seconds gauge")
    lines.append(f"ruige_degradation_duration_seconds {duration:.0f}")
    lines.append("")

    lines.append("# HELP ruige_circuit_breaker_info Circuit breaker per service")
    lines.append("# TYPE ruige_circuit_breaker_info gauge")
    for name in (
        "deepseek_llm",
        "tongyi_llm",
        "bge_rerank",
        "tongyi_rerank",
        "bge_embed",
        "tongyi_embed",
        "agent_tool_dispatch",
    ):
        try:
            cb = get_breaker(name)
            st = cb.status()
            lines.append(
                f'ruige_circuit_breaker_info{{{_label("breaker",name)},{_label("state",st["state"])}}} {st["failures"]}'
            )
        except Exception:
            pass
    lines.append("")

    events = get_degradation_events(limit=5)
    lines.append("# HELP ruige_degradation_events Recent degradation level changes")
    lines.append("# TYPE ruige_degradation_events gauge")
    for ev in events:
        from_l = str(ev["old_level"])
        to_l = str(ev["new_level"])
        lines.append(
            f'ruige_degradation_events{{{_label("from_level",from_l)},{_label("to_level",to_l)},{_label("label",ev["label"])}}} {ev["timestamp"]:.0f}'
        )

    body = "\n".join(lines) + "\n"
    return Response(content=body, media_type=_METRICS_MEDIA)
