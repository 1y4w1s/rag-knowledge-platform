"""T6 长期记忆分层 · W3 重要性评分（规则式因子 + promote/demote + 审计信号）。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Literal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.agent_memory import AgentMemory
from app.services.agent.memory_governance import MemorySource, source_priority
from app.services.agent.memory_summary import update_memory_summary
from app.services.audit.agent import safe_audit
from app.services.audit.log import write_audit_log

_EPSILON = 1e-9
_FALLBACK_WEIGHT = 0.2
_FEEDBACK_STATUSES = frozenset({"suppressed", "conflicted"})


class MemoryTier(str, Enum):
    working = "working"
    long_term = "long_term"


@dataclass(frozen=True, slots=True)
class ImportanceInput:
    source: MemorySource | str
    confidence: float
    last_accessed_at: datetime | None
    churn_count: int
    status: str


@dataclass(frozen=True, slots=True)
class ImportanceConfig:
    source_weight: float = 0.30
    recency_weight: float = 0.25
    frequency_weight: float = 0.20
    feedback_weight: float = 0.15
    governance_weight: float = 0.10
    recency_half_life_days: float = 14.0
    feedback_penalty: float = 0.4
    churn_penalty: float = 0.5
    churn_threshold: int = 3
    promote_threshold: float = 0.7
    demote_threshold: float = 0.35

    def __post_init__(self) -> None:
        if self.promote_threshold <= self.demote_threshold:
            raise ValueError("promote_threshold must be > demote_threshold")


@dataclass(frozen=True, slots=True)
class TierChangeResult:
    action: Literal["promoted", "demoted", "unchanged"]
    importance_score: float
    from_tier: str
    to_tier: str


def importance_config_from_settings() -> ImportanceConfig:
    """从 settings 读取 agent_memory_importance_* 与 agent_memory_churn_threshold。"""
    return ImportanceConfig(
        source_weight=settings.agent_memory_importance_source_weight,
        recency_weight=settings.agent_memory_importance_recency_weight,
        frequency_weight=settings.agent_memory_importance_frequency_weight,
        feedback_weight=settings.agent_memory_importance_feedback_weight,
        governance_weight=settings.agent_memory_importance_governance_weight,
        recency_half_life_days=settings.agent_memory_importance_recency_half_life_days,
        feedback_penalty=settings.agent_memory_importance_feedback_penalty,
        churn_penalty=settings.agent_memory_importance_churn_penalty,
        churn_threshold=settings.agent_memory_churn_threshold,
        promote_threshold=settings.agent_memory_importance_promote_threshold,
        demote_threshold=settings.agent_memory_importance_demote_threshold,
    )


def _source_factor(source: MemorySource | str) -> float:
    try:
        return source_priority(MemorySource(source)) / 4
    except (TypeError, ValueError, KeyError):
        return 0.0


def _recency_factor(
    last_accessed_at: datetime | None,
    *,
    now: datetime,
    half_life_days: float,
) -> float:
    if last_accessed_at is None:
        return 0.0
    last_at = last_accessed_at
    if last_at.tzinfo is None:
        last_at = last_at.replace(tzinfo=timezone.utc)
    days = max(0.0, (now - last_at).total_seconds() / 86400)
    return 2.0 ** (-days / half_life_days)


def compute_importance_score(
    factors: ImportanceInput,
    *,
    config: ImportanceConfig | None = None,
    now: datetime | None = None,
) -> float:
    """规则式重要性评分（0.0~1.0）。纯函数、确定性、零 LLM。

    now 仅作测试注入固定时间用；缺省取当前 UTC 时间。
    """
    cfg = config or importance_config_from_settings()
    now_utc = now or datetime.now(timezone.utc)
    if now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=timezone.utc)

    weights = (
        cfg.source_weight,
        cfg.recency_weight,
        cfg.frequency_weight,
        cfg.feedback_weight,
        cfg.governance_weight,
    )
    total_weight = sum(weights)
    if total_weight <= 0:
        total_weight = 1.0
        weights = (_FALLBACK_WEIGHT,) * 5

    source_factor = _source_factor(factors.source)
    recency_factor = _recency_factor(
        factors.last_accessed_at,
        now=now_utc,
        half_life_days=cfg.recency_half_life_days,
    )
    frequency_factor = max(0.0, min(1.0, factors.confidence))
    feedback_factor = (
        cfg.feedback_penalty if factors.status in _FEEDBACK_STATUSES else 1.0
    )
    governance_factor = (
        cfg.churn_penalty if factors.churn_count >= cfg.churn_threshold else 1.0
    )

    raw = (
        weights[0] * source_factor
        + weights[1] * recency_factor
        + weights[2] * frequency_factor
        + weights[3] * feedback_factor
        + weights[4] * governance_factor
    )
    return max(0.0, min(1.0, raw / max(total_weight, _EPSILON)))


def _importance_range(score: float, config: ImportanceConfig) -> str:
    if score < config.demote_threshold:
        return "low"
    if score >= config.promote_threshold:
        return "high"
    return "medium"


async def reevaluate_importance(
    db: AsyncSession,
    *,
    memory_id: UUID,
    actor_user_id: UUID,
    config: ImportanceConfig | None = None,
) -> TierChangeResult | None:
    """重算 importance_score 并落库；按阈值促升 / 促降 tier；tier 变更时写审计。

    返回 None 表示未找到或 memory.user_id != actor_user_id（跨用户隔离，不落库）。
    使用独立 session 立即 commit，不触碰调用方事务。
    """
    from app.core.database import SessionLocal

    cfg = config or importance_config_from_settings()
    async with SessionLocal() as mem_db:
        memory = await mem_db.get(AgentMemory, memory_id)
        if memory is None or memory.user_id != actor_user_id:
            return None

        score = compute_importance_score(
            ImportanceInput(
                source=memory.source,
                confidence=memory.confidence,
                last_accessed_at=memory.last_accessed_at,
                churn_count=memory.churn_count,
                status=memory.status,
            ),
            config=cfg,
        )
        from_tier = memory.tier
        to_tier = from_tier
        action: Literal["promoted", "demoted", "unchanged"] = "unchanged"
        if (
            from_tier == MemoryTier.long_term.value
            and score >= cfg.promote_threshold
        ):
            to_tier = MemoryTier.working.value
            action = "promoted"
        elif (
            from_tier == MemoryTier.working.value
            and score < cfg.demote_threshold
        ):
            to_tier = MemoryTier.long_term.value
            action = "demoted"

        memory.importance_score = score
        if action != "unchanged":
            memory.tier = to_tier
            await safe_audit(
                write_audit_log(
                    mem_db,
                    action="agent.memory_tier_changed",
                    actor_user_id=actor_user_id,
                    resource_type="agent_memory",
                    resource_id=memory.id,
                    metadata={
                        "memory_id": str(memory.id),
                        "key": memory.key,
                        "memory_type": memory.memory_type,
                        "from_tier": from_tier,
                        "to_tier": to_tier,
                        "importance_range": _importance_range(score, cfg),
                    },
                )
            )
        await mem_db.commit()
        try:
            # 重算落库后尽力刷新 summary（W5 §4.5），失败不阻塞主流程。
            await update_memory_summary(
                mem_db, memory_id=memory.id, actor_user_id=actor_user_id
            )
        except Exception:
            pass
        return TierChangeResult(
            action=action,
            importance_score=score,
            from_tier=from_tier,
            to_tier=to_tier,
        )
