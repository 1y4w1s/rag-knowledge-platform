"""T5 记忆治理：W1 数据层 + W2 治理核心。"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient
from sqlalchemy import select, text

from app.core.config import settings
from app.core.database import SessionLocal, engine
from app.models.agent_memory import AgentMemory
from app.models.audit_log import AuditLog
from app.models.enums import AgentRunMode
from app.services.agent.memory import (
    bump_memory_confidence,
    extract_and_store_memory,
    load_active_memories,
    upsert_memory,
)
from app.services.agent.memory_governance import (
    MemoryObservation,
    MemorySource,
    apply_observation,
    depth_rule,
    find_risky_memories,
    language_rule,
    source_priority,
    suppress_memory,
    values_equivalent,
)
from app.services.agent.runtime import run_react_loop
from app.services.agent.tools.scope import AgentToolScope
from app.services.agent.tools.search_documents import SearchDocumentsToolResult
from app.services.agent.tools.semantic_search import SemanticSearchToolResult
from app.services.agent.types import ToolCallPlan
from app.services.rag.thread_persistence import create_workspace_thread
from app.services.workspace.scope import WorkspaceKind, WorkspaceScope
from tests.conftest import RegisterAndLogin

GOVERNANCE_COLUMNS = (
    "source",
    "last_observed_at",
    "status",
    "suppress_until",
    "churn_count",
)


class TestModelColumns:
    """模型声明：新列类型 / nullable / 组合索引。"""

    def test_governance_columns_declared(self) -> None:
        cols = AgentMemory.__table__.columns
        assert set(GOVERNANCE_COLUMNS) <= set(cols.keys())
        assert cols["source"].type.length == 16
        assert cols["status"].type.length == 16
        assert cols["churn_count"].type.python_type is int
        assert cols["suppress_until"].nullable is True
        assert cols["last_observed_at"].nullable is False

    def test_user_status_index_declared(self) -> None:
        indexes = {idx.name: idx for idx in AgentMemory.__table__.indexes}
        assert "ix_agent_memories_user_status" in indexes
        idx = indexes["ix_agent_memories_user_status"]
        assert list(idx.columns.keys()) == ["user_id", "status"]


class TestOrmDefaults:
    """ORM 写入路径：Python 默认值生效。"""

    @pytest.mark.asyncio
    async def test_orm_insert_applies_governance_defaults(
        self,
        register_and_login: RegisterAndLogin,
    ) -> None:
        _headers, user = await register_and_login(prefix="t5-w1-orm")
        user_id = uuid.UUID(user["id"])
        key = f"lang-{uuid.uuid4().hex[:8]}"

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

            assert memory.source == "rule_inference"
            assert memory.status == "active"
            assert memory.churn_count == 0
            assert memory.suppress_until is None
            assert memory.last_observed_at is not None


class TestDbSchema:
    """迁移一致性：数据库列 / 默认值 / 索引与模型声明对齐。"""

    @pytest.mark.asyncio
    async def test_db_governance_columns_with_defaults(self) -> None:
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
                    {"names": list(GOVERNANCE_COLUMNS)},
                )
            ).mappings().all()

        by_name = {row["column_name"]: row for row in rows}
        assert set(by_name) == set(GOVERNANCE_COLUMNS)
        assert by_name["source"]["is_nullable"] == "NO"
        assert "rule_inference" in by_name["source"]["column_default"]
        assert by_name["status"]["is_nullable"] == "NO"
        assert "active" in by_name["status"]["column_default"]
        assert by_name["churn_count"]["is_nullable"] == "NO"
        assert by_name["churn_count"]["column_default"] is not None
        assert by_name["last_observed_at"]["is_nullable"] == "NO"
        assert "now()" in by_name["last_observed_at"]["column_default"]
        assert by_name["suppress_until"]["is_nullable"] == "YES"
        assert by_name["suppress_until"]["column_default"] is None

    @pytest.mark.asyncio
    async def test_db_user_status_index_exists(self) -> None:
        async with engine.connect() as conn:
            indexdef = (
                await conn.execute(
                    text(
                        """
                        SELECT indexdef
                        FROM pg_indexes
                        WHERE tablename = 'agent_memories'
                          AND indexname = 'ix_agent_memories_user_status'
                        """
                    )
                )
            ).scalar_one_or_none()

        assert indexdef is not None
        assert "agent_memories" in indexdef
        assert "USING btree (user_id, status)" in indexdef


class TestLegacyInsertBackfill:
    """存量兼容：旧式 INSERT 不写新列时由 server_default 回填。"""

    @pytest.mark.asyncio
    async def test_legacy_insert_gets_governance_defaults(
        self,
        register_and_login: RegisterAndLogin,
    ) -> None:
        _headers, user = await register_and_login(prefix="t5-w1-backfill")
        user_id = uuid.UUID(user["id"])
        key = f"legacy-{uuid.uuid4().hex[:8]}"

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
                        SELECT source, status, churn_count, suppress_until,
                               last_observed_at
                        FROM agent_memories
                        WHERE key = :key
                        """
                    ),
                    {"key": key},
                )
            ).mappings().one()

        assert row["source"] == "rule_inference"
        assert row["status"] == "active"
        assert row["churn_count"] == 0
        assert row["suppress_until"] is None
        assert row["last_observed_at"] is not None


class TestGovernancePureRules:
    """#1-6 纯函数。"""

    def test_language_rule(self) -> None:
        assert language_rule("hello world", cjk_ratio=0.6) == ("lang", "en")
        assert language_rule("年假有几天", cjk_ratio=0.6) == ("lang", "zh")
        assert language_rule("hello 世界", cjk_ratio=0.6) is None
        assert language_rule("   ", cjk_ratio=0.6) is None

    def test_depth_rule(self) -> None:
        assert depth_rule("thorough", 2, min_searches=2) == ("retrieval_depth", {"mode": "thorough"})
        assert depth_rule("thorough", 1, min_searches=2) is None
        assert depth_rule("default", 2, min_searches=2) is None

    def test_values_equivalent_lang_compat(self) -> None:
        assert values_equivalent("en", {"language": "en"})
        assert values_equivalent({"language": "en"}, {"language": "en"})
        assert not values_equivalent("en", {"language": "zh"})

    def test_source_priority_order(self) -> None:
        assert [source_priority(s) for s in MemorySource] == [4, 3, 2, 1]


def _obs(user_id: uuid.UUID, **kwargs: object) -> MemoryObservation:
    data = {"memory_type": "preference", "key": "lang", "value": {"language": "en"}, "source": MemorySource.rule_inference}
    data.update(kwargs)
    return MemoryObservation(user_id=user_id, **data)


async def _get(user_id: uuid.UUID, key: str) -> AgentMemory | None:
    async with SessionLocal() as db:
        return await db.scalar(select(AgentMemory).where(AgentMemory.user_id == user_id, AgentMemory.key == key))


async def _events(action: str, resource_id: uuid.UUID) -> list[AuditLog]:
    async with SessionLocal() as db:
        rows = await db.scalars(select(AuditLog).where(AuditLog.action == action, AuditLog.resource_id == resource_id).order_by(AuditLog.created_at))
        return list(rows)


async def _apply(user_id: uuid.UUID, **kwargs: object):
    return await apply_observation(None, observation=_obs(user_id, **kwargs))


class TestGovernanceWriteRules:
    """#7-13 / #15-16：优先级、强化、churn、抑制、跨 key 清理。

    #14 load 过滤归属 W3（memory.py 接线窗），本窗不修改 memory.py。
    """

    @pytest.mark.asyncio
    async def test_upsert_default_regression(self, register_and_login: RegisterAndLogin) -> None:
        _h, user = await register_and_login(prefix="t5-w2-upsert")
        uid = uuid.UUID(user["id"])
        async with SessionLocal() as db:
            await upsert_memory(db, uid, "preference", "lang", "en")
        row = await _get(uid, "lang")
        assert (row.confidence, row.status, row.source) == (1.0, "active", "rule_inference")

    @pytest.mark.asyncio
    async def test_low_priority_ignored(self, register_and_login: RegisterAndLogin) -> None:
        _h, user = await register_and_login(prefix="t5-w2-priority")
        uid = uuid.UUID(user["id"])
        await _apply(uid, source=MemorySource.user_explicit)
        result = await _apply(uid, value={"language": "zh"})
        row = await _get(uid, "lang")
        assert result.action == "ignored"
        assert (row.value, row.source, row.confidence, row.churn_count) == ({"language": "en"}, "user_explicit", 1.0, 0)

    @pytest.mark.asyncio
    async def test_same_value_reinforces(self, register_and_login: RegisterAndLogin) -> None:
        _h, user = await register_and_login(prefix="t5-w2-reinforce")
        uid = uuid.UUID(user["id"])
        first = await _apply(uid)
        result = await _apply(uid)
        row = await _get(uid, "lang")
        assert result.action == "reinforced"
        assert result.memory_id == first.memory_id
        assert (row.confidence, row.churn_count, row.value) == (pytest.approx(0.75), 0, {"language": "en"})

    @pytest.mark.asyncio
    async def test_overwrite_increments_churn(self, register_and_login: RegisterAndLogin) -> None:
        _h, user = await register_and_login(prefix="t5-w2-churn1")
        uid = uuid.UUID(user["id"])
        await _apply(uid)
        result = await _apply(uid, value={"language": "zh"})
        row = await _get(uid, "lang")
        assert result.action == "overwritten"
        assert (row.churn_count, row.value) == (1, {"language": "zh"})

    @pytest.mark.asyncio
    async def test_churn_threshold_audits_risk(self, register_and_login: RegisterAndLogin) -> None:
        _h, user = await register_and_login(prefix="t5-w2-churn3")
        uid = uuid.UUID(user["id"])
        await _apply(uid)
        for value in ({"language": "zh"}, {"language": "en"}, {"language": "zh"}):
            result = await _apply(uid, value=value)
        row = await _get(uid, "lang")
        events = await _events("agent.memory_risk_detected", row.id)
        assert result.action == "overwritten"
        assert (row.churn_count, row.confidence) == (3, 0.5)
        assert len(events) == 1 and events[0].details["churn_count"] == 3
        assert "value" not in events[0].details
        async with SessionLocal() as db:
            risky = await find_risky_memories(db, uid)
        assert row.id in {m.id for m in risky}

    @pytest.mark.asyncio
    async def test_suppressed_unexpired_ignored(self, register_and_login: RegisterAndLogin) -> None:
        _h, user = await register_and_login(prefix="t5-w2-suppressed")
        uid = uuid.UUID(user["id"])
        created = await _apply(uid)
        assert await suppress_memory(None, memory_id=created.memory_id, actor_user_id=uid, reason="wrong", suppress_seconds=3600)
        result = await _apply(uid, value={"language": "zh"})
        row = await _get(uid, "lang")
        assert result.action == "ignored"
        assert (row.status, row.value) == ("suppressed", {"language": "en"})

    @pytest.mark.asyncio
    async def test_suppressed_expired_rewrites(self, register_and_login: RegisterAndLogin) -> None:
        _h, user = await register_and_login(prefix="t5-w2-expired")
        uid = uuid.UUID(user["id"])
        created = await _apply(uid)
        assert await suppress_memory(None, memory_id=created.memory_id, actor_user_id=uid, reason="outdated", suppress_seconds=3600)
        async with SessionLocal() as db:
            row = await db.get(AgentMemory, created.memory_id)
            row.suppress_until = datetime.now(timezone.utc) - timedelta(seconds=1)
            await db.commit()
        result = await _apply(uid, value={"language": "zh"})
        row = await _get(uid, "lang")
        assert result.action == "overwritten"
        assert (row.status, row.value, row.suppress_until) == ("active", {"language": "zh"}, None)

    @pytest.mark.asyncio
    async def test_cross_key_lang_conflict(self, register_and_login: RegisterAndLogin) -> None:
        _h, user = await register_and_login(prefix="t5-w2-dimension")
        uid = uuid.UUID(user["id"])
        await _apply(uid, key="language", value={"language": "zh"})
        result = await _apply(uid, key="lang", value={"language": "en"})
        dirty = await _get(uid, "language")
        lang = await _get(uid, "lang")
        events = await _events("agent.memory_conflict_resolved", dirty.id)
        assert result.action == "created"
        assert dirty.status == "conflicted" and lang.status == "active"
        assert events[0].details["superseded_memory_id"] == str(lang.id)
        assert "value" not in events[0].details
        async with SessionLocal() as db:
            risky = await find_risky_memories(db, uid)
        assert dirty.id in {m.id for m in risky}

    @pytest.mark.asyncio
    async def test_suppress_memory_audits_without_value(self, register_and_login: RegisterAndLogin) -> None:
        _h, user = await register_and_login(prefix="t5-w2-suppress-audit")
        uid = uuid.UUID(user["id"])
        created = await _apply(uid)
        assert await suppress_memory(None, memory_id=created.memory_id, actor_user_id=uid, reason="irrelevant", suppress_seconds=604800)
        row = await _get(uid, "lang")
        events = await _events("agent.memory_suppressed", row.id)
        details = events[0].details
        assert row.status == "suppressed" and row.suppress_until is not None
        assert details["reason"] == "irrelevant"
        assert "value" not in details and "language" not in json.dumps(details)


class TestGovernanceA3:
    """#22 治理写路径独立 session 立即 commit。"""

    @pytest.mark.asyncio
    async def test_write_uses_independent_session(self, register_and_login: RegisterAndLogin) -> None:
        _h, user = await register_and_login(prefix="t5-w2-a3")
        uid = uuid.UUID(user["id"])
        async with SessionLocal() as db:
            db.add(AgentMemory(user_id=uid, memory_type="preference", key="pending", value={"language": "en"}))
            await db.flush()
            result = await apply_observation(db, observation=_obs(uid, key="governed"))
            await db.rollback()
        async with SessionLocal() as db:
            governed = await db.get(AgentMemory, result.memory_id)
            pending = await db.scalar(select(AgentMemory).where(AgentMemory.user_id == uid, AgentMemory.key == "pending"))
        assert result.action == "created"
        assert governed is not None and pending is None


class TestServiceWiring:
    """W3 服务接线：#14 load 过滤 + upsert 新参 + bump。"""

    @pytest.mark.asyncio
    async def test_load_active_memories_filters_inactive(
        self,
        register_and_login: RegisterAndLogin,
    ) -> None:
        _h, user = await register_and_login(prefix="t5-w3-load")
        uid = uuid.UUID(user["id"])
        now = datetime.now(timezone.utc)
        async with SessionLocal() as db:
            db.add_all([
                AgentMemory(
                    user_id=uid,
                    memory_type="preference",
                    key="active_k",
                    value={"language": "en"},
                    status="active",
                ),
                AgentMemory(
                    user_id=uid,
                    memory_type="preference",
                    key="conflicted_k",
                    value={"language": "zh"},
                    status="conflicted",
                ),
                AgentMemory(
                    user_id=uid,
                    memory_type="preference",
                    key="suppressed_k",
                    value={"language": "en"},
                    status="suppressed",
                    suppress_until=now + timedelta(hours=1),
                ),
            ])
            await db.commit()
            memories = await load_active_memories(db, uid)
        assert {m.key for m in memories} == {"active_k"}
        assert all(m.status == "active" for m in memories)

    @pytest.mark.asyncio
    async def test_upsert_custom_source_and_confidence(
        self,
        register_and_login: RegisterAndLogin,
    ) -> None:
        _h, user = await register_and_login(prefix="t5-w3-upsert-params")
        uid = uuid.UUID(user["id"])
        key = f"lang-{uuid.uuid4().hex[:8]}"
        async with SessionLocal() as db:
            await upsert_memory(
                db,
                uid,
                "preference",
                key,
                {"language": "en"},
                source=MemorySource.tool_observation,
                confidence=0.8,
            )
        row = await _get(uid, key)
        assert (row.source, row.confidence) == ("tool_observation", 0.8)

        async with SessionLocal() as db:
            await upsert_memory(
                db,
                uid,
                "preference",
                key,
                {"language": "en"},
                source=MemorySource.user_explicit,
                confidence=0.95,
            )
        row = await _get(uid, key)
        assert (row.source, row.confidence) == ("user_explicit", 0.95)

    @pytest.mark.asyncio
    async def test_bump_memory_confidence(
        self,
        register_and_login: RegisterAndLogin,
    ) -> None:
        _h, user = await register_and_login(prefix="t5-w3-bump")
        uid = uuid.UUID(user["id"])
        key = f"lang-{uuid.uuid4().hex[:8]}"
        async with SessionLocal() as db:
            memory_id = await upsert_memory(
                db,
                uid,
                "preference",
                key,
                {"language": "en"},
                confidence=0.6,
            )
            await bump_memory_confidence(db, memory_id, delta=0.2)
        row = await _get(uid, key)
        assert row.confidence == pytest.approx(0.8)

        async with SessionLocal() as db:
            await bump_memory_confidence(db, memory_id, delta=1.0)
        row = await _get(uid, key)
        assert row.confidence == 1.0


class TestExtractionWiring:
    """W5 提取扩展：R1 zh / R2 接线 / audit metadata 含 source。"""

    @pytest.mark.asyncio
    async def test_extract_zh_language_rule(
        self,
        register_and_login: RegisterAndLogin,
    ) -> None:
        _headers, user = await register_and_login(prefix="t5-w5-zh")
        uid = uuid.UUID(user["id"])
        async with SessionLocal() as db:
            await extract_and_store_memory(
                db, uid, "年假有几天", tool_name="semantic_search",
            )
            await db.commit()
        row = await _get(uid, "lang")
        events = await _events("agent.memory_write", row.id)
        assert row.value == {"language": "zh"}
        assert row.memory_type == "preference"
        assert row.source == "rule_inference"
        assert row.status == "active"
        assert row.confidence == pytest.approx(
            settings.agent_memory_rule_confidence
        )
        assert events[0].details["source"] == "rule_inference"
        assert "value" not in events[0].details

    @pytest.mark.asyncio
    async def test_extract_depth_rule_wired(
        self,
        register_and_login: RegisterAndLogin,
    ) -> None:
        _headers, user = await register_and_login(prefix="t5-w5-depth")
        uid = uuid.UUID(user["id"])
        async with SessionLocal() as db:
            await extract_and_store_memory(
                db, uid, "hello world",
                tool_name="search_documents",
                mode="thorough",
                search_successes=2,
            )
            await db.commit()
        row = await _get(uid, "retrieval_depth")
        events = await _events("agent.memory_write", row.id)
        assert row.value == {"mode": "thorough"}
        assert row.memory_type == "pattern"
        assert row.source == "rule_inference"
        assert events[0].details["source"] == "rule_inference"
        assert "value" not in events[0].details

    @pytest.mark.asyncio
    async def test_extract_depth_below_threshold_skipped(
        self,
        register_and_login: RegisterAndLogin,
    ) -> None:
        _headers, user = await register_and_login(prefix="t5-w5-depth-low")
        uid = uuid.UUID(user["id"])
        async with SessionLocal() as db:
            await extract_and_store_memory(
                db, uid, "hello world",
                tool_name="semantic_search",
                mode="thorough",
                search_successes=1,
            )
        assert await _get(uid, "retrieval_depth") is None


def _personal_workspace(user_id: uuid.UUID) -> WorkspaceScope:
    return WorkspaceScope(
        kind=WorkspaceKind.personal,
        user_id=user_id,
        org_id=None,
    )


class _SequencePlanner:
    def __init__(self, plans: list[ToolCallPlan | None]) -> None:
        self._plans = list(plans)

    async def next_tool_call(self, **kwargs) -> ToolCallPlan | None:
        return self._plans.pop(0) if self._plans else None


@pytest.mark.asyncio
async def test_runtime_passes_search_successes_and_mode(
    register_and_login: RegisterAndLogin,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """runtime 统计两类检索工具成功次数，并把 mode / search_successes 传给提取。"""
    _headers, user = await register_and_login(prefix="t5-w5-runtime")
    user_id = uuid.UUID(user["id"])
    async with SessionLocal() as db:
        thread = await create_workspace_thread(
            db,
            user_id=user_id,
            workspace_kind=WorkspaceKind.personal,
            workspace_org_id=None,
            department_id=None,
        )
        await db.commit()
        thread_id = thread.id

    planner = _SequencePlanner(
        [
            ToolCallPlan(tool_name="semantic_search", args={"query": "hello"}),
            ToolCallPlan(tool_name="search_documents", args={"query": "hello"}),
            None,
        ]
    )
    monkeypatch.setattr(
        "app.services.agent.runtime.run_semantic_search",
        AsyncMock(
            return_value=SemanticSearchToolResult(
                ok=True, data=None, summary="ok",
            )
        ),
    )
    monkeypatch.setattr(
        "app.services.agent.runtime.run_search_documents",
        AsyncMock(
            return_value=SearchDocumentsToolResult(
                ok=True, data=None, summary="ok",
            )
        ),
    )
    extract = AsyncMock()
    monkeypatch.setattr(
        "app.services.agent.runtime.extract_and_store_memory", extract
    )

    async with SessionLocal() as db:
        outcome = await run_react_loop(
            db,
            user_id=user_id,
            thread_id=thread_id,
            query="hello",
            workspace=_personal_workspace(user_id),
            tool_scope=AgentToolScope(),
            planner=planner,
            mode=AgentRunMode.thorough,
            max_steps=5,
        )
        await db.commit()

    assert outcome.steps_used == 2
    assert extract.call_count == 2
    calls = [call.kwargs for call in extract.call_args_list]
    assert [call["search_successes"] for call in calls] == [1, 2]
    assert all(call["mode"] == AgentRunMode.thorough for call in calls)


class TestMemoryGovernanceApi:
    """W4 API 接线：#17-21 report-error / DELETE 审计 / risky 列表。"""

    @pytest.mark.asyncio
    async def test_report_error_own_memory(
        self,
        client: AsyncClient,
        register_and_login: RegisterAndLogin,
    ) -> None:
        headers, user = await register_and_login(prefix="t5-w4-report-own")
        uid = uuid.UUID(user["id"])
        async with SessionLocal() as db:
            memory_id = await upsert_memory(
                db, uid, "preference", f"lang-{uuid.uuid4().hex[:8]}",
                {"language": "en"},
            )
        resp = await client.post(
            f"/api/v1/agent/memories/{memory_id}/report-error",
            headers=headers,
            json={"reason": "wrong"},
        )
        assert resp.status_code == 200
        assert resp.json() == {"ok": True}
        events = await _events("agent.memory_suppressed", memory_id)
        assert len(events) == 1
        details = events[0].details
        assert details["reason"] == "wrong"
        assert "value" not in details
        assert "language" not in json.dumps(details)
        async with SessionLocal() as db:
            row = await db.get(AgentMemory, memory_id)
        assert row is not None
        assert row.status == "suppressed" and row.suppress_until is not None

    @pytest.mark.asyncio
    async def test_report_error_other_or_missing_is_ok(
        self,
        client: AsyncClient,
        register_and_login: RegisterAndLogin,
    ) -> None:
        headers_a, user_a = await register_and_login(prefix="t5-w4-report-a")
        headers_b, _user_b = await register_and_login(prefix="t5-w4-report-b")
        uid_a = uuid.UUID(user_a["id"])
        async with SessionLocal() as db:
            memory_id = await upsert_memory(
                db, uid_a, "preference", f"lang-{uuid.uuid4().hex[:8]}",
                {"language": "en"},
            )
        other = await client.post(
            f"/api/v1/agent/memories/{memory_id}/report-error",
            headers=headers_b,
            json={"reason": "outdated"},
        )
        missing = await client.post(
            f"/api/v1/agent/memories/{uuid.uuid4()}/report-error",
            headers=headers_a,
            json={"reason": "irrelevant"},
        )
        assert other.status_code == 200 and other.json() == {"ok": True}
        assert missing.status_code == 200 and missing.json() == {"ok": True}
        async with SessionLocal() as db:
            row = await db.get(AgentMemory, memory_id)
        assert row is not None and row.status == "active"
        assert await _events("agent.memory_suppressed", memory_id) == []

    @pytest.mark.asyncio
    async def test_report_error_requires_auth_and_valid_reason(
        self,
        client: AsyncClient,
        register_and_login: RegisterAndLogin,
    ) -> None:
        memory_id = uuid.uuid4()
        unauth = await client.post(
            f"/api/v1/agent/memories/{memory_id}/report-error",
            json={"reason": "wrong"},
        )
        assert unauth.status_code == 401

        headers, _user = await register_and_login(prefix="t5-w4-report-params")
        invalid = await client.post(
            f"/api/v1/agent/memories/{memory_id}/report-error",
            headers=headers,
            json={"reason": "bad"},
        )
        assert invalid.status_code == 422

    @pytest.mark.asyncio
    async def test_delete_memory_audits_deleted_without_value(
        self,
        client: AsyncClient,
        register_and_login: RegisterAndLogin,
    ) -> None:
        headers, user = await register_and_login(prefix="t5-w4-delete-audit")
        uid = uuid.UUID(user["id"])
        secret_value = {"language": "en", "note": "secret-original-value-xyz"}
        async with SessionLocal() as db:
            memory_id = await upsert_memory(
                db, uid, "preference", f"lang-{uuid.uuid4().hex[:8]}",
                secret_value,
            )
        resp = await client.delete(
            f"/api/v1/agent/memories/{memory_id}", headers=headers
        )
        assert resp.status_code == 200 and resp.json() == {"ok": True}
        events = await _events("agent.memory_deleted", memory_id)
        assert len(events) == 1
        details = events[0].details
        assert details["memory_id"] == str(memory_id)
        assert "value" not in details
        assert "secret-original-value-xyz" not in json.dumps(details)
        async with SessionLocal() as db:
            row = await db.get(AgentMemory, memory_id)
        assert row is None

    @pytest.mark.asyncio
    async def test_risky_memories_list(
        self,
        client: AsyncClient,
        register_and_login: RegisterAndLogin,
    ) -> None:
        headers, user = await register_and_login(prefix="t5-w4-risky")
        uid = uuid.UUID(user["id"])
        now = datetime.now(timezone.utc)
        stale_at = now - timedelta(days=40)
        async with SessionLocal() as db:
            churn = AgentMemory(
                user_id=uid, memory_type="preference", key="churn_risk",
                value={"language": "en"}, churn_count=3, last_accessed_at=now,
            )
            conflicted = AgentMemory(
                user_id=uid, memory_type="preference", key="conflict_risk",
                value={"language": "zh"}, status="conflicted",
                last_accessed_at=now,
            )
            stale = AgentMemory(
                user_id=uid, memory_type="preference", key="stale_risk",
                value={"language": "en"}, confidence=0.2,
                last_accessed_at=stale_at,
            )
            normal = AgentMemory(
                user_id=uid, memory_type="preference", key="normal_ok",
                value={"language": "en"}, last_accessed_at=now,
            )
            db.add_all([churn, conflicted, stale, normal])
            await db.commit()

        resp = await client.get("/api/v1/agent/memories/risky", headers=headers)
        assert resp.status_code == 200
        returned = {m["id"] for m in resp.json()["memories"]}
        assert returned == {str(churn.id), str(conflicted.id), str(stale.id)}
        assert str(normal.id) not in returned
