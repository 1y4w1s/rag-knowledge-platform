"""E3 长期记忆服务：upsert / load / decay / delete。"""

from __future__ import annotations

import json
import math
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_memory import AgentMemory

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
) -> uuid.UUID:
    """写入/更新一条记忆，返回 memory_id。

    UPSERT：user_id + key 冲突时覆盖 value + 重置 confidence。

    A3（H4/P1-05）：写入走**独立 session 立即 commit**，绝不触碰调用方事务——
    agent run 流式期间 upsert 不再把半成品 run/steps/审批提前持久化，也不破坏
    主 session（commit 失败不污染 SSE 长事务）。``db`` 参数保留仅为兼容签名。
    """
    from app.core.database import SessionLocal

    now = datetime.now(timezone.utc)
    stmt = text("""
        INSERT INTO agent_memories (id, user_id, kb_id, memory_type, key, value, confidence, last_accessed_at)
        VALUES (:id, :user_id, :kb_id, :memory_type, :key, :value, 1.0, :now)
        ON CONFLICT (user_id, key) DO UPDATE SET
            value = EXCLUDED.value,
            confidence = 1.0,
            last_accessed_at = EXCLUDED.last_accessed_at
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
            "now": now,
        })
        row = result.fetchone()
        await mem_db.commit()
        return row[0]


# ═══════════════════════════════════════════════════════════════
# 读取
# ═══════════════════════════════════════════════════════════════

async def load_active_memories(
    db: AsyncSession,
    user_id: uuid.UUID,
    limit: int = 20,
) -> list[AgentMemory]:
    """加载活跃记忆（衰减后 confidence >= 阈值），按衰减值排序。"""
    rows = await db.execute(text("""
        SELECT id, user_id, kb_id, memory_type, key, value, confidence, last_accessed_at
        FROM agent_memories
        WHERE user_id = :user_id
          AND confidence * exp(:rate * EXTRACT(EPOCH FROM (:now - last_accessed_at)) / -86400) >= :floor
        ORDER BY confidence * exp(:rate2 * EXTRACT(EPOCH FROM (:now - last_accessed_at)) / -86400) DESC
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


def format_memory_context(memories: list[AgentMemory]) -> str:
    """将记忆列表格式化为 prompt 片段。"""
    if not memories:
        return ""
    lines = [f"- {m.key}: {m.value} ({m.memory_type})" for m in memories]
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
) -> None:
    """从检索工具执行结果中提取隐式偏好并写入（含审计）。"""
    if tool_name not in ("semantic_search", "search_documents"):
        return

    from app.services.audit.agent import audit_agent_memory_write

    async def _safe_upsert_and_audit(
        memory_type: str, key: str, value: Any,
    ) -> None:
        try:
            memory_id = await upsert_memory(db, user_id, memory_type, key, value, kb_id)
            await audit_agent_memory_write(
                db,
                actor_user_id=user_id,
                memory_id=memory_id,
                key=key,
                memory_type=memory_type,
                confidence=1.0,
            )
        except Exception:
            pass

    # 语言偏好：全 ASCII query → 偏好英文
    if query and all(ord(c) < 128 for c in query.strip()):
        await _safe_upsert_and_audit("preference", "lang", "en")


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
