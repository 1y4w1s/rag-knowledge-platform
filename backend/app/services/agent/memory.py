"""E3 长期记忆服务：upsert / load / decay / delete。"""

from __future__ import annotations

import json
import math
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.agent_memory import AgentMemory
from app.services.agent.memory_governance import (
    MemoryObservation,
    MemorySource,
    apply_observation,
    depth_rule,
    language_rule,
)
from app.services.agent.memory_summary import update_memory_summary

# ── 阈值 ──
_MEMORY_DECAY_RATE = 0.01  # 每日衰减率
_MEMORY_CONFIDENCE_FLOOR = 0.1  # 低于此值过滤


def _decayed(confidence: float, last_at: datetime) -> float:
    """计算衰减后的置信度。"""
    now = datetime.now(timezone.utc)
    if last_at.tzinfo is None:
        last_at = last_at.replace(tzinfo=timezone.utc)
    days = max(0, (now - last_at).total_seconds() / 86400)
    return confidence * math.exp(-_MEMORY_DECAY_RATE * days)


# ═══════════════════════════════════════════════════════════════
# 写入
# ═══════════════════════════════════════════════════════════════

async def upsert_memory(
    db: AsyncSession,
    user_id: uuid.UUID,
    memory_type: str,
    key: str,
    value: Any,
    kb_id: uuid.UUID | None = None,
    *,
    source: MemorySource = MemorySource.rule_inference,
    confidence: float | None = None,
) -> uuid.UUID:
    """写入/更新一条记忆，返回 memory_id。

    UPSERT：user_id + key 冲突时覆盖 value + 重置 confidence。

    A3（H4/P1-05）：写入走**独立 session 立即 commit**，绝不触碰调用方事务——
    agent run 流式期间 upsert 不再把半成品 run/steps/审批提前持久化，也不破坏
    主 session（commit 失败不污染 SSE 长事务）。``db`` 参数保留仅为兼容签名。
    """
    from app.core.database import SessionLocal

    now = datetime.now(timezone.utc)
    effective_confidence = 1.0 if confidence is None else confidence
    stmt = text("""
        INSERT INTO agent_memories (id, user_id, kb_id, memory_type, key, value, confidence, last_accessed_at, source)
        VALUES (:id, :user_id, :kb_id, :memory_type, :key, :value, :confidence, :now, :source)
        ON CONFLICT (user_id, key) DO UPDATE SET
            value = EXCLUDED.value,
            confidence = EXCLUDED.confidence,
            last_accessed_at = EXCLUDED.last_accessed_at,
            source = EXCLUDED.source
        -- 注意：ON CONFLICT 不更新 memory_type/kb_id，此设计是刻意的。
        -- memory_type 在 key 首次创建时确定，后续不允许通过 upsert 变更类型。
        RETURNING id
    """)
    async with SessionLocal() as mem_db:
        result = await mem_db.execute(stmt, {
            "id": uuid.uuid4(),
            "user_id": user_id,
            "kb_id": kb_id,
            "memory_type": memory_type,
            "key": key,
            "value": json.dumps(value),
            "confidence": effective_confidence,
            "now": now,
            "source": source.value,
        })
        row = result.fetchone()
        await mem_db.commit()
        try:
            # 写完 value 后尽力刷新 summary（W5 §4.5），失败不阻塞主写入。
            await update_memory_summary(
                mem_db, memory_id=row[0], actor_user_id=user_id
            )
        except Exception:
            pass
        return row[0]


# ═══════════════════════════════════════════════════════════════
# 读取
# ═══════════════════════════════════════════════════════════════

async def load_active_memories(
    db: AsyncSession,
    user_id: uuid.UUID,
    limit: int = 20,
) -> list[AgentMemory]:
    """加载活跃记忆（衰减后 confidence >= 阈值），按分层排序。

    T6 W5 排序：working 优先 → importance_score DESC → 衰减 confidence DESC →
    last_accessed_at DESC → id ASC；过滤语义与签名保持不变。
    T5 治理过滤：仅返回 status='active' 且不在抑制窗口内的记忆。
    """
    rows = await db.execute(text("""
        SELECT id, user_id, kb_id, memory_type, key, value, confidence, last_accessed_at,
               source, last_observed_at, status, suppress_until, churn_count,
               tier, importance_score, summary
        FROM agent_memories
        WHERE user_id = :user_id
          AND status = 'active'
          AND (suppress_until IS NULL OR suppress_until <= :now)
          AND confidence * exp(:rate * EXTRACT(EPOCH FROM (:now - last_accessed_at)) / -86400) >= :floor
        ORDER BY CASE tier WHEN 'working' THEN 0 ELSE 1 END ASC,
                 importance_score DESC,
                 confidence * exp(:rate2 * EXTRACT(EPOCH FROM (:now - last_accessed_at)) / -86400) DESC,
                 last_accessed_at DESC,
                 id ASC
        LIMIT :limit
    """), {
        "user_id": user_id,
        "now": datetime.now(timezone.utc),
        "rate": _MEMORY_DECAY_RATE,
        "rate2": _MEMORY_DECAY_RATE,
        "floor": _MEMORY_CONFIDENCE_FLOOR,
        "limit": limit,
    })
    return [AgentMemory(**dict(r._mapping)) for r in rows]


async def bump_memory_confidence(
    db: AsyncSession,
    memory_id: uuid.UUID,
    *,
    delta: float,
) -> None:
    """为记忆置信度增加 delta（上限 1.0）。

    与 upsert 一致走独立 session 立即 commit；`db` 参数保留仅为兼容签名。
    """
    from sqlalchemy import func, update

    from app.core.database import SessionLocal

    async with SessionLocal() as mem_db:
        await mem_db.execute(
            update(AgentMemory)
            .where(AgentMemory.id == memory_id)
            .values(confidence=func.least(1.0, AgentMemory.confidence + delta))
        )
        await mem_db.commit()


def _memory_payload(memory: AgentMemory) -> str:
    payload = memory.summary if memory.summary is not None else memory.value
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def format_memory_context(memories: list[AgentMemory]) -> str:
    """分层注入格式：summary 优先、NULL 回退 value、tier/importance 标注。"""
    if not memories:
        return ""
    lines = [
        f"- [{m.tier or 'long_term'}] {m.key}: {_memory_payload(m)} "
        f"({m.memory_type}) importance="
        f"{(m.importance_score if m.importance_score is not None else 0.5):.2f}"
        for m in memories
    ]
    return "用户长期偏好（仅供参考，不覆盖检索结果）：\n" + "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
# 提取隐式偏好（runtime 调用）
# ═══════════════════════════════════════════════════════════════

async def extract_and_store_memory(
    db: AsyncSession,
    user_id: uuid.UUID,
    query: str,
    kb_id: uuid.UUID | None = None,
    *,
    tool_name: str | None = None,
    tool_data: Any = None,
    mode: str | None = None,
    search_successes: int = 0,
) -> None:
    """从检索工具执行结果中提取隐式偏好并写入（含审计）。"""
    if tool_name not in ("semantic_search", "search_documents"):
        return

    from app.services.audit.agent import audit_agent_memory_write

    async def _apply_and_audit(
        memory_type: str, key: str, value: dict,
    ) -> None:
        try:
            result = await apply_observation(
                db,
                observation=MemoryObservation(
                    user_id=user_id,
                    kb_id=kb_id,
                    memory_type=memory_type,
                    key=key,
                    value=value,
                    source=MemorySource.rule_inference,
                ),
            )
            if result.memory_id is None:
                return
            await audit_agent_memory_write(
                db,
                actor_user_id=user_id,
                memory_id=result.memory_id,
                key=key,
                memory_type=memory_type,
                confidence=settings.agent_memory_rule_confidence,
                source=MemorySource.rule_inference.value,
            )
        except Exception:
            pass

    # R1 语言偏好：全 ASCII → en；CJK 占比达标 → zh；混合不提取
    lang = language_rule(
        query,
        cjk_ratio=settings.agent_memory_lang_cjk_ratio,
    )
    if lang is not None:
        _key, _lang = lang
        await _apply_and_audit("preference", _key, {"language": _lang})

    # R2 检索深度偏好：thorough 且本 run 检索成功次数达标
    effective_mode = mode.value if hasattr(mode, "value") else (mode or "")
    depth = depth_rule(
        effective_mode,
        search_successes,
        min_searches=settings.agent_memory_depth_min_searches,
    )
    if depth is not None:
        _key, _value = depth
        await _apply_and_audit("pattern", _key, _value)


# ═══════════════════════════════════════════════════════════════
# 删除
# ═══════════════════════════════════════════════════════════════

async def delete_memory(db: AsyncSession, memory_id: uuid.UUID) -> bool:
    """删除一条记忆。返回是否找到并删除。

    A3（H4/P1-05）：独立 session 立即 commit，不触碰调用方事务。``db`` 参数保留仅为兼容签名。
    """
    from sqlalchemy import delete as sa_delete

    from app.core.database import SessionLocal

    async with SessionLocal() as mem_db:
        result = await mem_db.execute(
            sa_delete(AgentMemory).where(AgentMemory.id == memory_id)
        )
        await mem_db.commit()
        return result.rowcount > 0
