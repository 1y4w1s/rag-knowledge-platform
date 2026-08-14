"""T5 记忆治理核心：来源优先级、同 key 覆盖、抑制与跨 key 清理。"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_memory import AgentMemory
from app.services.agent.memory_summary import update_memory_summary
from app.services.audit.agent import (
    audit_agent_memory_conflict_resolved,
    audit_agent_memory_risk_detected,
    audit_agent_memory_suppressed,
    safe_audit,
)

_CJK_CHAR = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff\u3040-\u30ff\uac00-\ud7af]")
_DECAY_RATE = 0.01
_CHURN_THRESHOLD = 3
_CHURN_WINDOW_SECONDS = 86400
_STALE_DAYS = 30
_STALE_CONFIDENCE = 0.3
_REINFORCE_DELTA = 0.05
_LANG_KEYS = frozenset({"lang", "language"})

class MemorySource(str, Enum):
    user_explicit = "user_explicit"
    conversation = "conversation"
    tool_observation = "tool_observation"
    rule_inference = "rule_inference"

_SOURCE_PRIORITY = {
    MemorySource.user_explicit: 4,
    MemorySource.conversation: 3,
    MemorySource.tool_observation: 2,
    MemorySource.rule_inference: 1,
}
_SOURCE_CONFIDENCE = {
    MemorySource.user_explicit: 1.0,
    MemorySource.conversation: 0.9,
    MemorySource.tool_observation: 0.8,
    MemorySource.rule_inference: 0.7,
}

@dataclass(frozen=True, slots=True)
class MemoryObservation:
    user_id: UUID
    memory_type: str
    key: str
    value: dict | str
    source: MemorySource
    kb_id: UUID | None = None

@dataclass(frozen=True, slots=True)
class MemoryWriteResult:
    memory_id: UUID | None
    action: Literal["created", "overwritten", "reinforced", "ignored", "superseded"]

def source_priority(source: MemorySource) -> int:
    return _SOURCE_PRIORITY[source]

def values_equivalent(left: Any, right: Any) -> bool:
    if isinstance(left, dict) and isinstance(right, dict):
        return left == right
    if isinstance(left, dict) != isinstance(right, dict):
        structured, scalar = (left, right) if isinstance(left, dict) else (right, left)
        return len(structured) == 1 and next(iter(structured.values())) == scalar
    return left == right

def language_rule(query: str, *, cjk_ratio: float) -> tuple[str, str] | None:
    text = query.strip()
    if not text:
        return None
    if all(ord(c) < 128 for c in text):
        return ("lang", "en")
    if len(_CJK_CHAR.findall(text)) / len(text) >= cjk_ratio:
        return ("lang", "zh")
    return None

def depth_rule(mode: str, successful_searches: int, *, min_searches: int) -> tuple[str, dict] | None:
    if mode == "thorough" and successful_searches >= min_searches:
        return ("retrieval_depth", {"mode": "thorough"})
    return None

def _priority(source: MemorySource | str) -> int:
    try:
        return _SOURCE_PRIORITY[MemorySource(source)]
    except ValueError:
        return 0

def _confidence(source: MemorySource) -> float:
    return _SOURCE_CONFIDENCE[source]

def _dimension(memory_type: str, key: str) -> str | None:
    return "lang" if memory_type == "preference" and key in _LANG_KEYS else None

def _decayed(confidence: float, last_at: datetime | None) -> float:
    if last_at is None:
        return confidence
    if last_at.tzinfo is None:
        last_at = last_at.replace(tzinfo=timezone.utc)
    days = max(0.0, (datetime.now(timezone.utc) - last_at).total_seconds() / 86400)
    return confidence * math.exp(-_DECAY_RATE * days)

async def _superseded_by_dimension(
    mem_db: AsyncSession,
    *,
    user_id: UUID,
    memory_type: str,
    key: str,
    memory_id: UUID,
) -> bool:
    if _dimension(memory_type, key) != "lang":
        return False
    return memory_id in await resolve_known_dimension_conflicts(
        mem_db, user_id=user_id, memory_type=memory_type, key=key
    )


async def _refresh_summary(
    mem_db: AsyncSession,
    *,
    memory_id: UUID,
    actor_user_id: UUID,
) -> None:
    """写完 value 后尽力刷新 summary；失败不阻塞主写入（W5 §4.5）。"""
    try:
        await update_memory_summary(
            mem_db, memory_id=memory_id, actor_user_id=actor_user_id
        )
    except Exception:
        pass


async def apply_observation(db: AsyncSession, *, observation: MemoryObservation) -> MemoryWriteResult:
    from app.core.database import SessionLocal
    now = datetime.now(timezone.utc)
    async with SessionLocal() as mem_db:
        existing = await mem_db.scalar(
            select(AgentMemory).where(
                AgentMemory.user_id == observation.user_id,
                AgentMemory.key == observation.key,
            )
        )
        if existing is None:
            memory = AgentMemory(
                user_id=observation.user_id,
                kb_id=observation.kb_id,
                memory_type=observation.memory_type,
                key=observation.key,
                value=observation.value,
                confidence=_confidence(observation.source),
                last_accessed_at=now,
                source=observation.source.value,
                last_observed_at=now,
                status="active",
                churn_count=0,
            )
            mem_db.add(memory)
            await mem_db.commit()
            await mem_db.refresh(memory)
            await _refresh_summary(
                mem_db, memory_id=memory.id, actor_user_id=observation.user_id
            )
            if await _superseded_by_dimension(mem_db, user_id=observation.user_id, memory_type=observation.memory_type, key=observation.key, memory_id=memory.id):
                return MemoryWriteResult(memory_id=memory.id, action="superseded")
            return MemoryWriteResult(memory_id=memory.id, action="created")
        if existing.status == "suppressed" and existing.suppress_until is not None and existing.suppress_until > now:
            return MemoryWriteResult(memory_id=existing.id, action="ignored")
        if _priority(observation.source) < _priority(existing.source):
            existing.last_accessed_at = now
            await mem_db.commit()
            return MemoryWriteResult(memory_id=existing.id, action="ignored")
        revive = existing.status in ("conflicted", "suppressed")
        if values_equivalent(existing.value, observation.value):
            existing.confidence = min(1.0, existing.confidence + _REINFORCE_DELTA)
            existing.last_accessed_at = now
            existing.last_observed_at = now
            if revive:
                existing.status = "active"
                existing.suppress_until = None
            action = "reinforced"
        else:
            new_churn = existing.churn_count
            if existing.last_observed_at is not None and (now - existing.last_observed_at).total_seconds() < _CHURN_WINDOW_SECONDS:
                new_churn += 1
            crossed = existing.churn_count < _CHURN_THRESHOLD <= new_churn
            existing.value = observation.value
            existing.source = observation.source.value
            existing.confidence = _confidence(observation.source)
            existing.last_accessed_at = now
            existing.last_observed_at = now
            existing.churn_count = new_churn
            if revive:
                existing.status = "active"
                existing.suppress_until = None
            if new_churn >= _CHURN_THRESHOLD:
                existing.confidence = min(existing.confidence, 0.5)
            if crossed:
                await safe_audit(audit_agent_memory_risk_detected(mem_db, actor_user_id=observation.user_id, memory_id=existing.id, key=existing.key, memory_type=existing.memory_type, signal="churn", churn_count=new_churn))
            action = "overwritten"
        await mem_db.commit()
        await _refresh_summary(
            mem_db, memory_id=existing.id, actor_user_id=observation.user_id
        )
        if await _superseded_by_dimension(mem_db, user_id=observation.user_id, memory_type=observation.memory_type, key=observation.key, memory_id=existing.id):
            return MemoryWriteResult(memory_id=existing.id, action="superseded")
        return MemoryWriteResult(memory_id=existing.id, action=action)

async def suppress_memory(db: AsyncSession, *, memory_id: UUID, actor_user_id: UUID, reason: str, suppress_seconds: int) -> bool:
    from app.core.database import SessionLocal
    async with SessionLocal() as mem_db:
        memory = await mem_db.get(AgentMemory, memory_id)
        if memory is None or memory.user_id != actor_user_id:
            return False
        memory.status = "suppressed"
        memory.suppress_until = datetime.now(timezone.utc) + timedelta(seconds=suppress_seconds)
        await safe_audit(audit_agent_memory_suppressed(mem_db, actor_user_id=actor_user_id, memory_id=memory.id, key=memory.key, memory_type=memory.memory_type, reason=reason))
        await mem_db.commit()
        return True

async def find_risky_memories(db: AsyncSession, user_id: UUID, *, limit: int = 20) -> list[AgentMemory]:
    rows = (await db.scalars(select(AgentMemory).where(AgentMemory.user_id == user_id))).all()
    risky: list[AgentMemory] = []
    now = datetime.now(timezone.utc)
    for row in rows:
        if row.status == "conflicted" or row.churn_count >= _CHURN_THRESHOLD:
            risky.append(row)
            continue
        if row.last_accessed_at is not None:
            elapsed = (now - row.last_accessed_at).total_seconds()
            if elapsed >= _STALE_DAYS * 86400 and _decayed(row.confidence, row.last_accessed_at) < _STALE_CONFIDENCE:
                risky.append(row)
    risky.sort(key=lambda row: (row.status != "conflicted", -row.churn_count))
    return risky[:limit]

async def resolve_known_dimension_conflicts(db: AsyncSession, *, user_id: UUID, memory_type: str, key: str) -> list[UUID]:
    if _dimension(memory_type, key) != "lang":
        return []
    from app.core.database import SessionLocal
    async with SessionLocal() as mem_db:
        rows = (await mem_db.scalars(select(AgentMemory).where(AgentMemory.user_id == user_id, AgentMemory.memory_type == "preference", AgentMemory.status == "active"))).all()
        candidates = [row for row in rows if _dimension(row.memory_type, row.key) == "lang"]
        if len(candidates) <= 1:
            return []
        winner = max(candidates, key=lambda row: (_priority(row.source), row.last_observed_at or datetime.min.replace(tzinfo=timezone.utc)))
        superseded: list[UUID] = []
        for row in candidates:
            if row.id == winner.id:
                continue
            row.status = "conflicted"
            superseded.append(row.id)
            await safe_audit(audit_agent_memory_conflict_resolved(mem_db, actor_user_id=user_id, memory_id=row.id, key=row.key, memory_type=row.memory_type, resolution="keep_winner", superseded_memory_id=winner.id))
        await mem_db.commit()
        return superseded
