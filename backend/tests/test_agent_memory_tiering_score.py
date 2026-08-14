"""T6 长期记忆分层 · W3 重要性评分服务测试（评分公式 / 阈值语义 / 审计契约 / 所有权隔离）。"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.agent_memory import AgentMemory
from app.models.audit_log import AuditLog
from app.services.agent.memory_governance import MemorySource
from app.services.agent.memory_tiering import (
    ImportanceConfig,
    ImportanceInput,
    compute_importance_score,
    importance_config_from_settings,
    reevaluate_importance,
)

NOW = datetime(2026, 8, 13, 12, 0, 0, tzinfo=timezone.utc)
OLD = datetime(2026, 7, 1, tzinfo=timezone.utc)
VERY_OLD = datetime(2025, 1, 1, tzinfo=timezone.utc)


def _factors(**kw: object) -> ImportanceInput:
    data = {
        "source": MemorySource.rule_inference,
        "confidence": 0.7,
        "last_accessed_at": NOW,
        "churn_count": 0,
        "status": "active",
    }
    data.update(kw)
    return ImportanceInput(**data)


def _score(**kw: object) -> float:
    return compute_importance_score(_factors(**kw), now=NOW)


class TestScoreFormula:
    """#1-7 评分公式纯函数用例。"""

    def test_source_priority_monotonic(self) -> None:
        scores = [
            _score(source=source)
            for source in (
                MemorySource.rule_inference,
                MemorySource.tool_observation,
                MemorySource.conversation,
                MemorySource.user_explicit,
            )
        ]
        assert scores == sorted(scores)
        assert all(a < b for a, b in zip(scores, scores[1:]))

    def test_recency_decay_and_none(self) -> None:
        cfg = ImportanceConfig(
            recency_weight=1.0,
            source_weight=0.0,
            frequency_weight=0.0,
            feedback_weight=0.0,
            governance_weight=0.0,
        )
        recent = compute_importance_score(_factors(last_accessed_at=NOW), config=cfg, now=NOW)
        old = compute_importance_score(_factors(last_accessed_at=NOW - timedelta(days=28)), config=cfg, now=NOW)
        missing = compute_importance_score(_factors(last_accessed_at=None), config=cfg, now=NOW)
        assert recent == pytest.approx(1.0)
        assert old == pytest.approx(0.25, abs=1e-9)
        assert missing == pytest.approx(0.0)

    def test_frequency_proxy_monotonic(self) -> None:
        assert _score(confidence=0.1) < _score(confidence=0.9)

    def test_churn_governance_penalty(self) -> None:
        cfg = ImportanceConfig(churn_threshold=3)
        clean = compute_importance_score(_factors(churn_count=2), config=cfg, now=NOW)
        risky = compute_importance_score(_factors(churn_count=3), config=cfg, now=NOW)
        also_risky = compute_importance_score(_factors(churn_count=5), config=cfg, now=NOW)
        assert risky < clean
        assert also_risky == pytest.approx(risky)

    def test_feedback_penalty(self) -> None:
        active = _score(status="active")
        suppressed = _score(status="suppressed")
        conflicted = _score(status="conflicted")
        assert suppressed < active
        assert conflicted == pytest.approx(suppressed)

    def test_weight_normalization_and_clamp(self) -> None:
        fallback = ImportanceConfig(source_weight=0.0, recency_weight=0.0, frequency_weight=0.0, feedback_weight=0.0, governance_weight=0.0)
        assert compute_importance_score(_factors(), config=fallback, now=NOW) == pytest.approx(0.79, abs=1e-9)
        peak = _score(source=MemorySource.user_explicit, confidence=1.0, last_accessed_at=NOW)
        assert peak == pytest.approx(1.0)
        bottom = _score(source="unknown_source", confidence=-1.0, last_accessed_at=None)
        assert 0.0 <= bottom <= 1.0

    def test_deterministic(self) -> None:
        factors = _factors()
        assert compute_importance_score(factors, now=NOW) == compute_importance_score(factors, now=NOW)


async def _create_memory(
    user_id: uuid.UUID,
    *,
    tier: str = "long_term",
    source: MemorySource = MemorySource.rule_inference,
    confidence: float = 0.7,
    last_accessed_at: datetime = NOW,
    status: str = "active",
    churn_count: int = 0,
    key: str | None = None,
    value: dict | None = None,
) -> AgentMemory:
    async with SessionLocal() as db:
        memory = AgentMemory(
            user_id=user_id,
            memory_type="preference",
            key=key or f"tier-{uuid.uuid4().hex[:8]}",
            value=value or {"language": "en"},
            tier=tier,
            source=source.value,
            confidence=confidence,
            last_accessed_at=last_accessed_at,
            status=status,
            churn_count=churn_count,
        )
        db.add(memory)
        await db.commit()
        await db.refresh(memory)
        return memory


async def _get_memory(memory_id: uuid.UUID) -> AgentMemory | None:
    async with SessionLocal() as db:
        return await db.get(AgentMemory, memory_id)


async def _tier_events(memory_id: uuid.UUID) -> list[AuditLog]:
    async with SessionLocal() as db:
        rows = await db.scalars(
            select(AuditLog)
            .where(
                AuditLog.action == "agent.memory_tier_changed",
                AuditLog.resource_id == memory_id,
            )
            .order_by(AuditLog.created_at)
        )
        return list(rows)


class TestPromoteDemote:
    """#8-15 阈值语义、滞回、边界、隔离与副作用。"""

    @pytest.mark.asyncio
    async def test_promote_long_term_to_working(self, register_and_login) -> None:
        _headers, user = await register_and_login(prefix="t6-w3-promote")
        uid = uuid.UUID(user["id"])
        memory = await _create_memory(
            uid, source=MemorySource.user_explicit, confidence=1.0,
            last_accessed_at=datetime.now(timezone.utc),
        )
        result = await reevaluate_importance(None, memory_id=memory.id, actor_user_id=uid)
        row = await _get_memory(memory.id)
        assert result is not None and result.action == "promoted"
        assert result.from_tier == "long_term" and result.to_tier == "working"
        assert result.importance_score >= 0.7
        assert row is not None and row.tier == "working"
        assert row.importance_score == pytest.approx(result.importance_score)

    @pytest.mark.asyncio
    async def test_demote_working_to_long_term(self, register_and_login) -> None:
        _headers, user = await register_and_login(prefix="t6-w3-demote")
        uid = uuid.UUID(user["id"])
        memory = await _create_memory(
            uid, tier="working", source=MemorySource.rule_inference,
            confidence=0.0, last_accessed_at=VERY_OLD,
        )
        result = await reevaluate_importance(None, memory_id=memory.id, actor_user_id=uid)
        row = await _get_memory(memory.id)
        assert result is not None and result.action == "demoted"
        assert result.from_tier == "working" and result.to_tier == "long_term"
        assert result.importance_score < 0.35
        assert row is not None and row.tier == "long_term"

    @pytest.mark.asyncio
    async def test_hysteresis_and_hard_constraint(self, register_and_login) -> None:
        _headers, user = await register_and_login(prefix="t6-w3-hysteresis")
        uid = uuid.UUID(user["id"])
        long_term = await _create_memory(
            uid, tier="long_term", source=MemorySource.conversation,
            confidence=0.5, last_accessed_at=OLD,
        )
        working = await _create_memory(
            uid, tier="working", source=MemorySource.conversation,
            confidence=0.5, last_accessed_at=OLD, key=f"wm-{uuid.uuid4().hex[:8]}",
        )
        long_result = await reevaluate_importance(None, memory_id=long_term.id, actor_user_id=uid)
        working_result = await reevaluate_importance(None, memory_id=working.id, actor_user_id=uid)
        assert long_result is not None and long_result.action == "unchanged"
        assert long_result.to_tier == "long_term"
        assert working_result is not None and working_result.action == "unchanged"
        assert working_result.to_tier == "working"
        assert (await _get_memory(long_term.id)).tier == "long_term"
        assert (await _get_memory(working.id)).tier == "working"
        assert ImportanceConfig().promote_threshold > ImportanceConfig().demote_threshold
        with pytest.raises(ValueError):
            ImportanceConfig(promote_threshold=0.4, demote_threshold=0.5)

    @pytest.mark.asyncio
    async def test_threshold_boundaries(self, register_and_login) -> None:
        _headers, user = await register_and_login(prefix="t6-w3-boundary")
        uid = uuid.UUID(user["id"])
        promote_config = ImportanceConfig(
            source_weight=0.4, frequency_weight=0.4, feedback_weight=0.2,
            recency_weight=0.0, governance_weight=0.0,
        )
        memory = await _create_memory(
            uid, tier="long_term", source=MemorySource.rule_inference, confidence=1.0,
        )
        promoted = await reevaluate_importance(
            None, memory_id=memory.id, actor_user_id=uid, config=promote_config,
        )
        assert promoted is not None and promoted.action == "promoted"
        assert promoted.importance_score == pytest.approx(0.7)

        demote_config = ImportanceConfig(
            source_weight=0.6, frequency_weight=0.4,
            recency_weight=0.0, feedback_weight=0.0, governance_weight=0.0,
        )
        working = await _create_memory(
            uid, tier="working", source=MemorySource.rule_inference,
            confidence=0.5, key=f"wm-{uuid.uuid4().hex[:8]}",
        )
        at_demote = await reevaluate_importance(
            None, memory_id=working.id, actor_user_id=uid, config=demote_config,
        )
        assert at_demote is not None and at_demote.action == "unchanged"
        assert at_demote.importance_score == pytest.approx(0.35)
        assert at_demote.to_tier == "working"

    @pytest.mark.asyncio
    async def test_ownership_isolation(self, register_and_login) -> None:
        _headers_a, user_a = await register_and_login(prefix="t6-w3-owner-a")
        _headers_b, user_b = await register_and_login(prefix="t6-w3-owner-b")
        uid_a = uuid.UUID(user_a["id"])
        uid_b = uuid.UUID(user_b["id"])
        memory = await _create_memory(
            uid_a, source=MemorySource.user_explicit, confidence=1.0,
        )
        cross = await reevaluate_importance(None, memory_id=memory.id, actor_user_id=uid_b)
        missing = await reevaluate_importance(None, memory_id=uuid.uuid4(), actor_user_id=uid_a)
        assert cross is None and missing is None
        assert await _tier_events(memory.id) == []
        row = await _get_memory(memory.id)
        assert row is not None and row.tier == "long_term"
        assert row.importance_score == pytest.approx(0.5)

    @pytest.mark.asyncio
    async def test_side_effect_boundary(self, register_and_login) -> None:
        _headers, user = await register_and_login(prefix="t6-w3-sideeffect")
        uid = uuid.UUID(user["id"])
        suppress_until = datetime.now(timezone.utc) + timedelta(hours=1)
        value = {"language": "en", "note": "unchanged-value"}
        async with SessionLocal() as db:
            memory = AgentMemory(
                user_id=uid,
                memory_type="preference",
                key=f"tier-{uuid.uuid4().hex[:8]}",
                value=value,
                tier="long_term",
                source=MemorySource.conversation.value,
                confidence=0.5,
                last_accessed_at=OLD,
                status="suppressed",
                suppress_until=suppress_until,
                churn_count=1,
                importance_score=0.5,
            )
            db.add(memory)
            await db.commit()
            await db.refresh(memory)
            memory_id = memory.id
        result = await reevaluate_importance(None, memory_id=memory_id, actor_user_id=uid)
        row = await _get_memory(memory_id)
        assert result is not None and result.action == "unchanged"
        assert row is not None
        assert row.value == value
        assert row.status == "suppressed"
        assert row.suppress_until == suppress_until
        assert row.churn_count == 1
        assert row.importance_score != pytest.approx(0.5)
        assert row.tier == "long_term"


class TestAudit:
    """#12-13 审计契约与无变更不审计。"""

    @pytest.mark.asyncio
    async def test_tier_change_audit_without_value(self, register_and_login) -> None:
        _headers, user = await register_and_login(prefix="t6-w3-audit")
        uid = uuid.UUID(user["id"])
        secret_value = {
            "language": "en",
            "note": "secret-memory-value-w3",
            "question": "secret-user-question-full-text",
        }
        memory = await _create_memory(
            uid, source=MemorySource.user_explicit, confidence=1.0,
            last_accessed_at=datetime.now(timezone.utc), value=secret_value,
        )
        async with SessionLocal() as db:
            row = await db.get(AgentMemory, memory.id)
            row.summary = {"text": "secret-summary-w3"}
            await db.commit()
        result = await reevaluate_importance(None, memory_id=memory.id, actor_user_id=uid)
        events = await _tier_events(memory.id)
        assert result is not None and result.action == "promoted"
        assert len(events) == 1
        details = events[0].details
        assert set(details) == {
            "memory_id", "key", "memory_type", "from_tier", "to_tier", "importance_range",
        }
        assert details["from_tier"] == "long_term" and details["to_tier"] == "working"
        assert details["importance_range"] == "high"
        serialized = json.dumps(details, ensure_ascii=False)
        assert "secret-memory-value-w3" not in serialized
        assert "secret-summary-w3" not in serialized
        assert "secret-user-question-full-text" not in serialized

    @pytest.mark.asyncio
    async def test_unchanged_writes_no_audit(self, register_and_login) -> None:
        _headers, user = await register_and_login(prefix="t6-w3-noaudit")
        uid = uuid.UUID(user["id"])
        memory = await _create_memory(
            uid, source=MemorySource.conversation, confidence=0.5, last_accessed_at=OLD,
        )
        result = await reevaluate_importance(None, memory_id=memory.id, actor_user_id=uid)
        assert result is not None and result.action == "unchanged"
        assert await _tier_events(memory.id) == []


class TestConfigWiring:
    """#16 配置接线。"""

    def test_settings_defaults_match_doc(self) -> None:
        assert settings.agent_memory_importance_promote_threshold == 0.7
        assert settings.agent_memory_importance_demote_threshold == 0.35
        assert settings.agent_memory_importance_source_weight == 0.30
        assert settings.agent_memory_importance_recency_weight == 0.25
        assert settings.agent_memory_importance_frequency_weight == 0.20
        assert settings.agent_memory_importance_feedback_weight == 0.15
        assert settings.agent_memory_importance_governance_weight == 0.10
        assert settings.agent_memory_importance_recency_half_life_days == 14.0
        assert settings.agent_memory_importance_feedback_penalty == 0.4
        assert settings.agent_memory_importance_churn_penalty == 0.5
        assert settings.agent_memory_churn_threshold == 3

    def test_config_from_settings_maps_all_fields(self) -> None:
        config = importance_config_from_settings()
        assert config.source_weight == settings.agent_memory_importance_source_weight
        assert config.recency_weight == settings.agent_memory_importance_recency_weight
        assert config.frequency_weight == settings.agent_memory_importance_frequency_weight
        assert config.feedback_weight == settings.agent_memory_importance_feedback_weight
        assert config.governance_weight == settings.agent_memory_importance_governance_weight
        assert config.recency_half_life_days == settings.agent_memory_importance_recency_half_life_days
        assert config.feedback_penalty == settings.agent_memory_importance_feedback_penalty
        assert config.churn_penalty == settings.agent_memory_importance_churn_penalty
        assert config.churn_threshold == settings.agent_memory_churn_threshold
        assert config.promote_threshold == settings.agent_memory_importance_promote_threshold
        assert config.demote_threshold == settings.agent_memory_importance_demote_threshold
