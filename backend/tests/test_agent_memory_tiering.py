"""T6 长期记忆分层 · W1 数据层与迁移测试。"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import text

from app.core.config import settings
from app.core.database import SessionLocal, engine
from app.models.agent_memory import AgentMemory
from app.services.agent.memory import format_memory_context, load_active_memories
from app.services.agent.planners import LLMPlanner, LLMPlannerFactory, SafetyFrame
from app.services.agent.runtime import ToolPlanner, run_react_loop
from app.services.agent.tools.scope import AgentToolScope
from app.services.rag.thread_persistence import create_workspace_thread
from app.services.workspace.scope import WorkspaceKind, WorkspaceScope

TIERING_COLUMNS = (
    "tier",
    "importance_score",
    "summary",
)


class TestModelColumns:
    """模型声明：新列类型 / nullable / 组合索引。"""

    def test_tiering_columns_declared(self) -> None:
        cols = AgentMemory.__table__.columns
        assert set(TIERING_COLUMNS) <= set(cols.keys())
        assert cols["tier"].type.length == 16
        assert cols["tier"].nullable is False
        assert cols["importance_score"].type.python_type is float
        assert cols["importance_score"].nullable is False
        assert cols["summary"].nullable is True

    def test_user_status_tier_index_declared(self) -> None:
        indexes = {idx.name: idx for idx in AgentMemory.__table__.indexes}
        assert "ix_agent_memories_user_status_tier" in indexes
        idx = indexes["ix_agent_memories_user_status_tier"]
        assert list(idx.columns.keys()) == ["user_id", "status", "tier"]


class TestOrmDefaults:
    """ORM 写入路径：Python 默认值生效。"""

    @pytest.mark.asyncio
    async def test_orm_insert_applies_tiering_defaults(
        self,
        register_and_login,
    ) -> None:
        _headers, user = await register_and_login(prefix="t6-w1-orm")
        user_id = uuid.UUID(user["id"])
        key = f"tier-{uuid.uuid4().hex[:8]}"

        async with SessionLocal() as db:
            memory = AgentMemory(
                user_id=user_id,
                memory_type="preference",
                key=key,
                value={"language": "en"},
            )
            db.add(memory)
            await db.commit()
            await db.refresh(memory)

            assert memory.tier == "long_term"
            assert memory.importance_score == pytest.approx(0.5)
            assert memory.summary is None

    @pytest.mark.asyncio
    async def test_explicit_tier_persists(
        self,
        register_and_login,
    ) -> None:
        _headers, user = await register_and_login(prefix="t6-w1-explicit")
        user_id = uuid.UUID(user["id"])
        key = f"working-{uuid.uuid4().hex[:8]}"

        async with SessionLocal() as db:
            memory = AgentMemory(
                user_id=user_id,
                memory_type="pattern",
                key=key,
                value={"mode": "thorough"},
                tier="working",
                importance_score=0.8,
                summary={"text": "用户偏好深入检索"},
            )
            db.add(memory)
            await db.commit()
            await db.refresh(memory)

            assert memory.tier == "working"
            assert memory.importance_score == pytest.approx(0.8)
            assert memory.summary == {"text": "用户偏好深入检索"}


class TestDbSchema:
    """迁移一致性：数据库列 / 默认值 / 索引与模型声明对齐。"""

    @pytest.mark.asyncio
    async def test_db_tiering_columns_with_defaults(self) -> None:
        async with engine.connect() as conn:
            rows = (
                await conn.execute(
                    text(
                        """
                        SELECT column_name, is_nullable, column_default
                        FROM information_schema.columns
                        WHERE table_name = 'agent_memories'
                          AND column_name = ANY(:names)
                        """
                    ),
                    {"names": list(TIERING_COLUMNS)},
                )
            ).mappings().all()

        by_name = {row["column_name"]: row for row in rows}
        assert set(by_name) == set(TIERING_COLUMNS)
        assert by_name["tier"]["is_nullable"] == "NO"
        assert "long_term" in by_name["tier"]["column_default"]
        assert by_name["importance_score"]["is_nullable"] == "NO"
        assert "0.5" in by_name["importance_score"]["column_default"]
        assert by_name["summary"]["is_nullable"] == "YES"
        assert by_name["summary"]["column_default"] is None

    @pytest.mark.asyncio
    async def test_db_user_status_tier_index_exists(self) -> None:
        async with engine.connect() as conn:
            indexdef = (
                await conn.execute(
                    text(
                        """
                        SELECT indexdef
                        FROM pg_indexes
                        WHERE tablename = 'agent_memories'
                          AND indexname = 'ix_agent_memories_user_status_tier'
                        """
                    )
                )
            ).scalar_one_or_none()

        assert indexdef is not None
        assert "agent_memories" in indexdef
        assert "USING btree (user_id, status, tier)" in indexdef


class TestLegacyInsertBackfill:
    """存储兼容：旧式 INSERT 不写新列时由 server_default 回填。"""

    @pytest.mark.asyncio
    async def test_legacy_insert_gets_tiering_defaults(
        self,
        register_and_login,
    ) -> None:
        _headers, user = await register_and_login(prefix="t6-w1-backfill")
        user_id = uuid.UUID(user["id"])
        key = f"legacy-tier-{uuid.uuid4().hex[:8]}"

        async with SessionLocal() as db:
            await db.execute(
                text(
                    """
                    INSERT INTO agent_memories
                        (id, user_id, kb_id, memory_type, key, value,
                         confidence, last_accessed_at)
                    VALUES (:id, :user_id, NULL, 'preference', :key, :value,
                            1.0, :now)
                    """
                ),
                {
                    "id": uuid.uuid4(),
                    "user_id": user_id,
                    "key": key,
                    "value": json.dumps({"language": "en"}),
                    "now": datetime.now(timezone.utc),
                },
            )
            await db.commit()
            row = (
                await db.execute(
                    text(
                        """
                        SELECT tier, importance_score, summary
                        FROM agent_memories
                        WHERE key = :key
                        """
                    ),
                    {"key": key},
                )
            ).mappings().one()

        assert row["tier"] == "long_term"
        assert row["importance_score"] == pytest.approx(0.5)
        assert row["summary"] is None


# ═══════════════════════════════════════════════════════════════════════════
# W5：分层读取 + 注入格式 + runtime 接线
# ═══════════════════════════════════════════════════════════════════════════


def _tiered_memory(
    *,
    key: str,
    memory_type: str = "preference",
    value: dict | None = None,
    summary: dict | None = None,
    tier: str = "long_term",
    importance: float = 0.5,
) -> AgentMemory:
    """构造内存中的分层记忆对象（不持久化）。"""
    return AgentMemory(
        id=uuid.uuid4(), user_id=uuid.uuid4(), kb_id=None,
        memory_type=memory_type, key=key,
        value={"v": "raw"} if value is None else value,
        confidence=1.0, last_accessed_at=datetime.now(timezone.utc),
        tier=tier, importance_score=importance, summary=summary,
    )


class _NoopPlanner:
    """非 LLMPlanner 的最小 planner：直接结束循环。"""

    async def next_tool_call(self, **kwargs: object) -> None:
        return None


def _llm_planner(query: str = "列出我的偏好") -> LLMPlanner:
    frame = SafetyFrame(query, default_kb_id=None)
    planner = LLMPlanner(query, safety_frame=frame, tool_specs=frame.all_tool_specs())
    planner.next_tool_call = AsyncMock(return_value=None)
    return planner


async def _run_agent_loop(user_id: uuid.UUID, planner: ToolPlanner) -> object:
    async with SessionLocal() as db:
        thread = await create_workspace_thread(db, user_id=user_id, workspace_kind=WorkspaceKind.personal, workspace_org_id=None, department_id=None)
        await db.commit()
        await run_react_loop(
            db, user_id=user_id, thread_id=thread.id,
            query="列出我的偏好",
            workspace=WorkspaceScope(kind=WorkspaceKind.personal, user_id=user_id, org_id=None),
            tool_scope=AgentToolScope(), planner=planner, max_steps=5,
        )
        await db.commit()


class TestLoadActiveMemoriesTiered:
    """W5 #1-5：分层排序 / 补列 / 过滤语义。"""

    @pytest.mark.asyncio
    async def test_working_first_then_importance_desc(self, register_and_login) -> None:
        _h, user = await register_and_login(prefix="t6-w5-sort")
        uid = uuid.UUID(user["id"])
        async with SessionLocal() as db:
            db.add_all([
                AgentMemory(user_id=uid, memory_type="preference", key="lt_hi", value={"language": "en"}, tier="long_term", importance_score=0.9),
                AgentMemory(user_id=uid, memory_type="preference", key="wk_lo", value={"language": "zh"}, tier="working", importance_score=0.5),
                AgentMemory(user_id=uid, memory_type="pattern", key="lt_lo", value={"mode": "deep"}, tier="long_term", importance_score=0.5),
            ])
            await db.commit()
            memories = await load_active_memories(db, uid)
        assert [m.key for m in memories] == ["wk_lo", "lt_hi", "lt_lo"]

    @pytest.mark.asyncio
    async def test_decayed_confidence_tie_breaker(self, register_and_login) -> None:
        _h, user = await register_and_login(prefix="t6-w5-tie")
        uid = uuid.UUID(user["id"])
        async with SessionLocal() as db:
            db.add_all([
                AgentMemory(user_id=uid, memory_type="preference", key="hi_conf", value={"language": "en"}, confidence=0.9, importance_score=0.5),
                AgentMemory(user_id=uid, memory_type="preference", key="lo_conf", value={"language": "zh"}, confidence=0.6, importance_score=0.5),
            ])
            await db.commit()
            memories = await load_active_memories(db, uid)
        assert [m.key for m in memories] == ["hi_conf", "lo_conf"]

    @pytest.mark.asyncio
    async def test_select_includes_tiering_columns(self, register_and_login) -> None:
        _h, user = await register_and_login(prefix="t6-w5-columns")
        uid = uuid.UUID(user["id"])
        key = f"tiered-{uuid.uuid4().hex[:8]}"
        async with SessionLocal() as db:
            db.add(AgentMemory(user_id=uid, memory_type="pattern", key=key, value={"mode": "thorough"}, tier="working", importance_score=0.77, summary={"mode": "thorough"}))
            await db.commit()
            memories = await load_active_memories(db, uid)
        loaded = next(m for m in memories if m.key == key)
        assert loaded.tier == "working"
        assert loaded.importance_score == pytest.approx(0.77)
        assert loaded.summary == {"mode": "thorough"}

    @pytest.mark.asyncio
    async def test_filter_semantics_unchanged(self, register_and_login) -> None:
        _h, user = await register_and_login(prefix="t6-w5-filter")
        uid = uuid.UUID(user["id"])
        now = datetime.now(timezone.utc)
        async with SessionLocal() as db:
            db.add_all([
                AgentMemory(user_id=uid, memory_type="preference", key="active_k", value={"language": "en"}),
                AgentMemory(user_id=uid, memory_type="preference", key="suppressed_k", value={"language": "zh"}, status="suppressed", suppress_until=now + timedelta(hours=1)),
                AgentMemory(user_id=uid, memory_type="preference", key="low_conf_k", value={"language": "en"}, confidence=0.01),
            ])
            await db.commit()
            memories = await load_active_memories(db, uid)
        assert {m.key for m in memories} == {"active_k"}


class TestFormatMemoryContextTiered:
    """W5 #6-11：summary 优先 / NULL 回退 / 标注 / 确定性 / 泄露面。"""

    def test_summary_preferred_over_value(self) -> None:
        m = _tiered_memory(key="lang", value={"language": "en", "secret": "raw"}, summary={"language": "en"}, tier="working", importance=0.9)
        result = format_memory_context([m])
        assert '- [working] lang: {"language": "en"} (preference) importance=0.90' in result
        assert "secret" not in result

    def test_null_summary_falls_back_to_value(self) -> None:
        result = format_memory_context([_tiered_memory(key="lang", value={"language": "en"})])
        assert '{"language": "en"}' in result and "[long_term]" in result
        assert "importance=0.50" in result

    def test_tier_and_importance_labels(self) -> None:
        m1 = _tiered_memory(key="lang", value={"language": "en"}, tier="working", importance=0.9)
        m2 = _tiered_memory(key="retrieval_depth", memory_type="pattern", value={"mode": "thorough"}, tier="long_term", importance=0.72)
        result = format_memory_context([m1, m2])
        assert "- [working] lang:" in result and "importance=0.90" in result
        assert "- [long_term] retrieval_depth:" in result and "importance=0.72" in result

    def test_deterministic_canonical_json(self) -> None:
        m = _tiered_memory(key="lang", value={"z": 1, "a": 2})
        first, second = format_memory_context([m]), format_memory_context([m])
        assert first == second
        assert '"a": 2' in first and '"z": 1' in first
        assert first.index('"a"') < first.index('"z"')

    def test_disclaimer_header_unchanged(self) -> None:
        result = format_memory_context([_tiered_memory(key="lang")])
        assert result.startswith("用户长期偏好（仅供参考，不覆盖检索结果）：")

    def test_no_governance_fields_leak(self) -> None:
        m = _tiered_memory(key="lang", value={"language": "en"})
        m.status = "suppressed"
        m.suppress_until = datetime.now(timezone.utc)
        m.churn_count = 5
        m.last_accessed_at = datetime.now(timezone.utc)
        result = format_memory_context([m])
        for forbidden in (
            "suppressed", "suppress_until", "churn_count", "last_accessed_at",
            "用户问题", "tool_data",
        ):
            assert forbidden not in result


class TestRuntimeMemoryInjection:
    """W5 #12：LLMPlanner 注入新格式；非 LLMPlanner / 开关关闭不注入；子 planner 同源。"""

    @pytest.mark.asyncio
    async def test_llm_planner_receives_tiered_format(self, register_and_login) -> None:
        _h, user = await register_and_login(prefix="t6-w5-inject")
        uid = uuid.UUID(user["id"])
        async with SessionLocal() as db:
            db.add_all([
                AgentMemory(user_id=uid, memory_type="preference", key="lang", value={"language": "en"}, tier="working", importance_score=0.9),
                AgentMemory(user_id=uid, memory_type="pattern", key="retrieval_depth", value={"mode": "thorough"}, tier="long_term", importance_score=0.72, summary={"mode": "thorough"}),
            ])
            await db.commit()
        planner = _llm_planner()
        await _run_agent_loop(uid, planner)
        assert "- [working] lang:" in planner._memory_context
        assert "- [long_term] retrieval_depth:" in planner._memory_context
        assert "importance=0.90" in planner._memory_context

    @pytest.mark.asyncio
    async def test_no_injection_when_non_llm_or_disabled(
        self, register_and_login, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _h, user = await register_and_login(prefix="t6-w5-noinject")
        uid = uuid.UUID(user["id"])
        load = AsyncMock(return_value=[])
        monkeypatch.setattr("app.services.agent.runtime.load_active_memories", load)
        await _run_agent_loop(uid, _NoopPlanner())
        load.assert_not_awaited()

        monkeypatch.setattr(settings, "agent_memory_enabled", False)
        await _run_agent_loop(uid, _llm_planner())
        load.assert_not_awaited()

    def test_sub_planner_reuses_same_ctx(self) -> None:
        ctx = format_memory_context([_tiered_memory(key="lang", value={"language": "en"}, tier="working", importance=0.9)])
        sub = LLMPlannerFactory.create("对比 A 与 B？再分别检索并总结？", memory_context=ctx or "")
        assert isinstance(sub, LLMPlanner) and sub._memory_context == ctx
