"""显式降级阶梯（DegradationLevel + DegradationManager）。

L0-L4 降级策略，在外部依赖不可用时通过阶梯式降级保证系统仍能输出
有用信息，而不是裸报错。

面试关键概念：「降级不是撞墙了才想，是设计时就定义好的阶跃函数」。
"""

from __future__ import annotations

import dataclasses
import logging
import time
from enum import IntEnum

from app.core.config import settings
from app.core.retry import CircuitBreaker, get_breaker

logger = logging.getLogger(__name__)


class DegradationLevel(IntEnum):
    """降级阶梯 L0-L4（数字越大降级越严重）。

    L0 — 正常：所有服务在线。
    L1 — LLM 降级：LLM 不可用，改用纯关键词匹配 + 返回原文片段。
    L2 — Rerank 降级：Rerank 不可用，使用 RRF 原始排序。
    L3 — 嵌入降级：嵌入服务不可用，仅使用全文检索（FTS）。
    L4 — 全降级：关键依赖全部不可用，返回结构化错误页。
    """
    NORMAL = 0
    LLM_DOWN = 1
    RERANK_DOWN = 2
    EMBED_DOWN = 3
    ALL_DOWN = 4


# ── 服务健康状态查询 ──────────────────────────────────────────────────

def _breaker_health(breaker: CircuitBreaker) -> bool:
    """熔断器是否允许请求（CLOSED 或 HALF_OPEN 且未耗尽半开配额）。"""
    return breaker.allow_request


# ── 降级抖动抑制 ──────────────────────────────────────────────────────

_effective_level: DegradationLevel = DegradationLevel.NORMAL
_last_downgrade_time: float = 0.0  # time.monotonic()


def apply_stabilization(theoretical: DegradationLevel) -> DegradationLevel:
    """防抖动：恶化立即生效，改善需等待冷却窗口。

    规则：
    - L4→*（全降级中恢复）：立即生效。
    - 恶化（level 升高）：立即生效，重置冷却计时器。
    - 改善（level 降低）：若冷却窗口未过，保持当前等级；否则生效。
    - 等级不变：无操作。
    """
    global _effective_level, _last_downgrade_time

    current = _effective_level

    # L4 恢复 → 立即生效
    if current == DegradationLevel.ALL_DOWN and theoretical < current:
        _effective_level = theoretical
        _last_downgrade_time = 0.0
        _record_degradation_event(current, theoretical)
        logger.info("降级恢复: L4 → L%d (%s)", int(theoretical), degradation_label(theoretical))
        return _effective_level

    # 恶化（level 升高）→ 立即生效
    if theoretical > current:
        _effective_level = theoretical
        _last_downgrade_time = time.monotonic()
        _record_degradation_event(current, theoretical)
        logger.info("降级恶化: L%d → L%d (%s)", int(current), int(theoretical), degradation_label(theoretical))
        return _effective_level

    # 改善（level 降低）→ 需等待冷却窗口
    if theoretical < current:
        elapsed = time.monotonic() - _last_downgrade_time
        cooldown = settings.degradation_cooldown_seconds
        if elapsed >= cooldown:
            _effective_level = theoretical
            _last_downgrade_time = 0.0
            _record_degradation_event(current, theoretical)
            logger.info(
                "降级恢复（冷却 %.0fs/%.0fs）: L%d → L%d (%s)",
                elapsed, cooldown, int(current), int(theoretical),
                degradation_label(theoretical),
            )
        else:
            logger.debug(
                "降级抖动抑制: 理论 L%d, 实际保持 L%d（冷却剩余 %.0fs）",
                int(theoretical), int(current), cooldown - elapsed,
            )
        return _effective_level

    # 等级不变
    return current


def reset_stabilization() -> None:
    """测试/运维用：重置抖动抑制状态到 L0。"""
    global _effective_level, _last_downgrade_time
    _effective_level = DegradationLevel.NORMAL
    _last_downgrade_time = 0.0


# ── 降级事件跟踪（可观测性） ──────────────────────────────────────────

DEGRADATION_EVENT_MAX = 50  # 最多保留最近 50 条事件


@dataclasses.dataclass
class DegradationEvent:
    timestamp: float
    old_level: int
    new_level: int
    label: str


_degradation_events: list[DegradationEvent] = []


def _record_degradation_event(old: DegradationLevel, new: DegradationLevel) -> None:
    global _degradation_events
    event = DegradationEvent(
        timestamp=time.time(),
        old_level=int(old),
        new_level=int(new),
        label=degradation_label(new),
    )
    _degradation_events.append(event)
    if len(_degradation_events) > DEGRADATION_EVENT_MAX:
        _degradation_events = _degradation_events[-DEGRADATION_EVENT_MAX:]


def get_degradation_events(limit: int = 10) -> list[dict]:
    """返回最近 N 条降级事件（用于 /health 端点和监控）。"""
    recent = _degradation_events[-limit:]
    return [
        {
            "timestamp": e.timestamp,
            "old_level": e.old_level,
            "new_level": e.new_level,
            "label": e.label,
        }
        for e in recent
    ]


def current_degradation_duration() -> float:
    """当前降级等级已持续秒数（用于 metrics）。"""
    if _last_downgrade_time > 0:
        return time.monotonic() - _last_downgrade_time
    return 0.0


# ── 服务健康状态查询 ──────────────────────────────────────────────────


def assess_degradation() -> DegradationLevel:
    """综合评估当前系统健康状态，返回当前应使用的降级阶梯。

    评估维度：
    1. LLM 熔断器 → L1
    2. Rerank 熔断器 → L2（单独影响 rerank 步骤）
    3. 嵌入熔断器 → L3
    4. 多服务同时熔断 → L4
    5. degradation_enabled=False → 始终 L0
    """
    if not settings.degradation_enabled:
        return apply_stabilization(DegradationLevel.NORMAL)

    llm_ok = _breaker_health(get_breaker("deepseek_llm"))
    rerank_ok = _breaker_health(get_breaker("tongyi_rerank"))
    embed_ok = _breaker_health(get_breaker("tongyi_embed"))

    # 多服务同时熔断 → L4
    degraded_count = sum(not ok for ok in (llm_ok, rerank_ok, embed_ok))
    if degraded_count >= 2:
        return apply_stabilization(DegradationLevel.ALL_DOWN)

    # 单服务熔断
    if not llm_ok:
        return apply_stabilization(DegradationLevel.LLM_DOWN)
    if not embed_ok:
        return apply_stabilization(DegradationLevel.EMBED_DOWN)
    if not rerank_ok:
        return apply_stabilization(DegradationLevel.RERANK_DOWN)

    return apply_stabilization(DegradationLevel.NORMAL)


# ── 降级行为描述 ──────────────────────────────────────────────────────

def degradation_label(level: DegradationLevel) -> str:
    labels = {
        DegradationLevel.NORMAL: "正常",
        DegradationLevel.LLM_DOWN: "LLM 降级 → 返回关键词匹配结果",
        DegradationLevel.RERANK_DOWN: "Rerank 降级 → 使用 RRF 原始排序",
        DegradationLevel.EMBED_DOWN: "嵌入降级 → 仅使用全文检索",
        DegradationLevel.ALL_DOWN: "全降级 → 返回服务不可用提示",
    }
    return labels.get(level, "未知降级")


def degradation_message(level: DegradationLevel) -> str:
    """返回面向用户的降级说明文本。"""
    messages = {
        DegradationLevel.NORMAL: "",
        DegradationLevel.LLM_DOWN: (
            "AI 回答服务暂时不可用，以下是最相关的文档片段供您参考。"
            "请稍后再试以获得完整回答。"
        ),
        DegradationLevel.RERANK_DOWN: "",
        DegradationLevel.EMBED_DOWN: (
            "语义检索暂时不可用，已切换到关键词搜索模式，"
            "结果可能不够精确，请稍后再试。"
        ),
        DegradationLevel.ALL_DOWN: (
            "知识库服务暂时不可用，请稍后再试。"
            "如持续异常，请联系技术支持。"
        ),
    }
    return messages.get(level, "服务暂时不可用，请稍后再试。")


def degradation_requires_llm(level: DegradationLevel) -> bool:
    """当前降级等级是否还需要 LLM 调用。"""
    return level < DegradationLevel.LLM_DOWN


def degradation_requires_rerank(level: DegradationLevel) -> bool:
    """当前降级等级是否还需要 Rerank 调用。"""
    return level < DegradationLevel.RERANK_DOWN


def degradation_requires_embed(level: DegradationLevel) -> bool:
    """当前降级等级是否还需要 Embedding 调用。"""
    return level < DegradationLevel.EMBED_DOWN
