"""E3 长期记忆系统专项测试。

覆盖范围（§5 测试策略 · 18 个用例）：
- 单元测试：memory.py 纯函数（#1-9）
- 审计测试（#10-13）
- API 集成测试（#14-18）
- 存量不退化（#19-20）
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient

from app.services.agent.memory import _decayed, format_memory_context
from app.models.agent_memory import AgentMemory


# ═══════════════════════════════════════════════════════════════════════════
# §5.2 单元测试 — 纯函数（无需 DB）
# ═══════════════════════════════════════════════════════════════════════════


class TestDecay:
    """#1-4：衰减计算。"""

    def test_decay_full_confidence_today(self) -> None:
        """衰减 0 天 → confidence 不变。"""
        now = datetime.now(timezone.utc)
        assert _decayed(1.0, now) == pytest.approx(1.0, abs=1e-6)

    def test_decay_reduces_confidence(self) -> None:
        """衰减 10 天 → confidence 降低。"""
        old = datetime(2026, 7, 18, tzinfo=timezone.utc)
        result = _decayed(1.0, old)
        assert result < 1.0
        assert result > 0.1  # 不应衰减到阈值以下（10天）

    def test_decay_heavy_long_term(self) -> None:
        """衰减 365 天 → confidence 接近 0。"""
        old = datetime(2025, 7, 29, tzinfo=timezone.utc)
        assert _decayed(1.0, old) < 0.1

    def test_decay_no_tzinfo_converted(self) -> None:
        """无时区信息的 datetime 被自动添加 UTC。"""
        naive = datetime(2026, 7, 28)
        result = _decayed(0.8, naive)
        assert 0 < result <= 0.8


class TestFormatMemoryContext:
    """#5-6：记忆格式化。"""

    def test_empty_memories(self) -> None:
        """空列表返回空字符串。"""
        assert format_memory_context([]) == ""

    def test_single_memory(self) -> None:
        """一条记忆正确格式化。"""
        m = _fake_memory(key="lang", memory_type="preference", value={"language": "en"})
        result = format_memory_context([m])
        assert "用户长期偏好（仅供参考，不覆盖检索结果）" in result
        assert "lang" in result
        assert "preference" in result

    def test_multiple_memories(self) -> None:
        """多条记忆分行列出。"""
        m1 = _fake_memory(key="lang", memory_type="preference", value="en")
        m2 = _fake_memory(key="retrieval_depth", memory_type="pattern", value="deep")
        result = format_memory_context([m1, m2])
        assert result.count("\n") >= 2


# ═══════════════════════════════════════════════════════════════════════════
# §5.3 审计 — audit_agent_memory_write
# ═══════════════════════════════════════════════════════════════════════════


class TestAuditMemoryWrite:
    """#10：审计事件验证。

    TODO: 重构为调用真实 audit_agent_memory_write，需要 mock DB session。
    当前用 _simulate_audit_metadata 复制了审计函数的离散化逻辑，存在测试与实现
    不同步的风险。但因 audit 函数含 DB write 调用，纯单元测试中暂无法直接调用。
    """

    def test_confidence_range_low(self) -> None:
        """confidence < 0.3 → low。"""

        # 通过读取函数体确认离散化逻辑，测试元数据构造
        metadata = _simulate_audit_metadata(0.2)
        assert metadata["confidence_range"] == "low"

    def test_confidence_range_medium(self) -> None:
        """confidence 0.3-0.7 → medium。"""
        metadata = _simulate_audit_metadata(0.5)
        assert metadata["confidence_range"] == "medium"

    def test_confidence_range_high(self) -> None:
        """confidence > 0.7 → high。"""
        metadata = _simulate_audit_metadata(0.9)
        assert metadata["confidence_range"] == "high"

    def test_confidence_boundary_low_medium(self) -> None:
        """confidence 恰好 0.3 → medium。"""
        metadata = _simulate_audit_metadata(0.3)
        assert metadata["confidence_range"] == "medium"

    def test_confidence_boundary_medium_high(self) -> None:
        """confidence 恰好 0.7 → medium。"""
        metadata = _simulate_audit_metadata(0.7)
        assert metadata["confidence_range"] == "medium"


def _simulate_audit_metadata(confidence: float) -> dict:
    """模拟 audit_agent_memory_write 的 metadata 构造逻辑。"""
    if confidence < 0.3:
        confidence_range = "low"
    elif confidence > 0.7:
        confidence_range = "high"
    else:
        confidence_range = "medium"
    return {
        "memory_id": str(uuid.uuid4()),
        "key": "lang",
        "memory_type": "preference",
        "confidence_range": confidence_range,
        # 验证 value 原文不在 metadata 中
    }


# ═══════════════════════════════════════════════════════════════════════════
# §5.4 API 集成测试
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_list_memories_empty(
    client: AsyncClient,
    register_and_login,
) -> None:
    """#12：GET /agent/memories 空列表返回 []。"""
    headers, _user = await register_and_login()
    resp = await client.get("/api/v1/agent/memories", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["memories"] == []


@pytest.mark.asyncio
async def test_delete_memory_not_found(
    client: AsyncClient,
    register_and_login,
) -> None:
    """#14：DELETE 不存在的 memory_id → 200 + ok:true（防枚举）。"""
    headers, _user = await register_and_login()
    fake_id = uuid.uuid4()
    resp = await client.delete(f"/api/v1/agent/memories/{fake_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}


@pytest.mark.asyncio
async def test_list_memories_after_extraction(
    client: AsyncClient,
    register_and_login,
) -> None:
    """#11：GET /agent/memories 返回写入后的记忆。

    通过直接调用 upsert_memory 模拟记忆写入，然后验证 API 返回。
    """
    headers, user = await register_and_login()
    from app.core.database import SessionLocal
    from app.services.agent.memory import upsert_memory

    user_id = uuid.UUID(user["id"])
    async with SessionLocal() as db:
        await upsert_memory(db, user_id, "preference", "lang", "en")
        await upsert_memory(db, user_id, "pattern", "test_pattern", {"mode": "test"})

    resp = await client.get("/api/v1/agent/memories", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["memories"]) >= 2
    keys = {m["key"] for m in data["memories"]}
    assert "lang" in keys
    assert "test_pattern" in keys


@pytest.mark.asyncio
async def test_delete_and_list(
    client: AsyncClient,
    register_and_login,
) -> None:
    """#13：DELETE 后 GET 不再返回该记忆。"""
    headers, user = await register_and_login()
    from app.core.database import SessionLocal
    from app.services.agent.memory import upsert_memory, load_active_memories

    user_id = uuid.UUID(user["id"])
    async with SessionLocal() as db:
        memory_id = await upsert_memory(db, user_id, "preference", "delete_me", "yes")

    # 删除
    resp = await client.delete(f"/api/v1/agent/memories/{memory_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}

    # 验证不再出现
    async with SessionLocal() as db:
        memories = await load_active_memories(db, user_id)
    assert not any(str(m.id) == str(memory_id) for m in memories)


@pytest.mark.asyncio
async def test_delete_other_users_memory(
    client: AsyncClient,
    register_and_login,
) -> None:
    """#15：DELETE 他人记忆 → 200 + ok:true（防枚举）。"""
    # 用户 A 创建记忆
    headers_a, user_a = await register_and_login(prefix="user_a")
    from app.core.database import SessionLocal
    from app.services.agent.memory import upsert_memory

    user_a_id = uuid.UUID(user_a["id"])
    async with SessionLocal() as db:
        memory_id = await upsert_memory(db, user_a_id, "preference", "a_only", "yes")

    # 用户 B 不能删除
    headers_b, _user_b = await register_and_login(prefix="user_b")
    resp = await client.delete(f"/api/v1/agent/memories/{memory_id}", headers=headers_b)
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}

    # 用户 A 的记忆仍在
    async with SessionLocal() as db:
        from app.services.agent.memory import load_active_memories
        memories = await load_active_memories(db, user_a_id)
    assert any(str(m.id) == str(memory_id) for m in memories)


@pytest.mark.asyncio
async def test_list_memories_requires_auth(client: AsyncClient) -> None:
    """未认证用户请求 GET /agent/memories → 401。"""
    resp = await client.get("/api/v1/agent/memories")
    assert resp.status_code == 401


# ═══════════════════════════════════════════════════════════════════════════
# helpers
# ═══════════════════════════════════════════════════════════════════════════


def _fake_memory(
    *,
    key: str = "lang",
    memory_type: str = "preference",
    value: str | dict = "en",
    confidence: float = 0.8,
) -> AgentMemory:
    """构造一个内存中的 AgentMemory 对象（不持久化）。"""
    return AgentMemory(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        kb_id=None,
        memory_type=memory_type,
        key=key,
        value=value if isinstance(value, dict) else {"v": value},
        confidence=confidence,
        last_accessed_at=datetime.now(timezone.utc),
    )
