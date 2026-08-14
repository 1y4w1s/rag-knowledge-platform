"""T6 长期记忆分层 · W4 结构化摘要服务测试。

覆盖：压缩规则 / 总字符预算 / 落库 / 审计契约 / 零 LLM / 所有权隔离 / 副作用边界 / 配置接线。
"""

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
from app.services.agent.memory_summary import (
    MemorySummaryResult,
    SummaryConfig,
    compress_memory_value,
    summary_config_from_settings,
    update_memory_summary,
)


def _canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


async def _create_memory(user_id: uuid.UUID, **kwargs: object) -> AgentMemory:
    data: dict[str, object] = {
        "memory_type": "preference",
        "key": f"summary-{uuid.uuid4().hex[:8]}",
        "value": {"language": "en"},
    }
    data.update(kwargs)
    async with SessionLocal() as db:
        memory = AgentMemory(user_id=user_id, **data)
        db.add(memory)
        await db.commit()
        await db.refresh(memory)
        return memory


async def _get_memory(memory_id: uuid.UUID) -> AgentMemory | None:
    async with SessionLocal() as db:
        return await db.get(AgentMemory, memory_id)


async def _summary_events(memory_id: uuid.UUID) -> list[AuditLog]:
    async with SessionLocal() as db:
        rows = await db.scalars(
            select(AuditLog)
            .where(
                AuditLog.action == "agent.memory_summary_updated",
                AuditLog.resource_id == memory_id,
            )
            .order_by(AuditLog.created_at)
        )
        return list(rows)


class TestCompressionRules:
    """#1-8 压缩规则纯函数用例。"""

    def test_short_dict_value_passthrough(self) -> None:
        result = compress_memory_value({"language": "en"})
        assert result.summary == {"language": "en"}
        assert result.truncated is False
        assert result.field_count == 1
        assert result.total_chars == len(_canonical(result.summary))
        assert result.total_chars == 18

    def test_string_field_truncated_with_marker(self) -> None:
        config = SummaryConfig(max_field_chars=10)
        result = compress_memory_value({"note": "a" * 11}, config=config)
        assert result.summary == {"note": "a" * 10 + "..."}
        assert result.truncated is True

    def test_list_items_capped_with_marker(self) -> None:
        config = SummaryConfig(max_items=3)
        result = compress_memory_value({"items": [1, 2, 3, 4, 5]}, config=config)
        assert result.summary == {"items": [1, 2, 3, "..."]}
        assert result.truncated is True

    def test_nested_depth_limit_replaces_subtree(self) -> None:
        result = compress_memory_value({"a": {"b": {"c": {"d": {"e": 1}}}}})
        assert result.summary == {"a": {"b": {"c": {"d": "..."}}}}
        assert result.truncated is True

    def test_non_dict_root_wrapped_as_v(self) -> None:
        scalar = compress_memory_value("en")
        assert isinstance(scalar.summary, dict)
        assert scalar.summary == {"v": "en"}
        assert scalar.truncated is True
        root_list = compress_memory_value([1, 2, 3])
        assert isinstance(root_list.summary, dict)
        assert root_list.summary == {"v": [1, 2, 3]}
        assert root_list.truncated is True

    def test_total_chars_budget_halves_or_removes_strings(self) -> None:
        budget_only = SummaryConfig(max_field_chars=1000)
        halved = compress_memory_value({"note": "a" * 1000}, config=budget_only)
        assert halved.summary == {"note": "a" * 500}
        assert halved.truncated is True
        assert halved.total_chars <= SummaryConfig().max_total_chars

        removed = compress_memory_value(
            {"note": "a" * 1000},
            config=SummaryConfig(max_field_chars=1000, max_total_chars=10),
        )
        assert removed.summary == {}
        assert removed.truncated is True
        assert removed.total_chars == 2

    def test_total_chars_budget_drops_tail_and_falls_back(self) -> None:
        tail = compress_memory_value(
            {"items": list(range(30))},
            config=SummaryConfig(max_items=100, max_total_chars=30),
        )
        assert tail.summary == {"items": [0, 1, 2, 3, 4, 5]}
        assert tail.truncated is True
        assert tail.total_chars <= 30

        fallback = compress_memory_value(
            {"a": 1}, config=SummaryConfig(max_total_chars=1)
        )
        assert fallback.summary == {"v": "..."}
        assert fallback.truncated is True

    def test_primitives_preserved(self) -> None:
        value = {"a": True, "b": 1, "c": 1.5, "d": None, "e": {}}
        result = compress_memory_value(value)
        assert result.summary == value
        assert result.truncated is False
        assert result.field_count == 5

    def test_deterministic_pure_function(self) -> None:
        value = {
            "language": "en",
            "note": "x" * 130,
            "items": list(range(30)),
            "nested": {"deep": {"deeper": {"deepest": "y" * 20}}},
        }
        first = compress_memory_value(value)
        second = compress_memory_value(value)
        assert isinstance(first, MemorySummaryResult)
        assert first == second
        assert _canonical(first.summary) == _canonical(second.summary)
        assert value["note"] == "x" * 130


class TestNoLlmPath:
    """#9 零 LLM / 无 key 兼容。"""

    @pytest.mark.asyncio
    async def test_no_llm_key_and_no_exception(
        self,
        register_and_login,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(settings, "deepseek_api_key", "")
        monkeypatch.setattr(settings, "tongyi_api_key", "")
        compressed = compress_memory_value({"language": "en", "note": "x" * 130})
        assert compressed.truncated is True

        _headers, user = await register_and_login(prefix="t6-w4-nollm")
        uid = uuid.UUID(user["id"])
        memory = await _create_memory(uid, value={"language": "en"})
        updated = await update_memory_summary(
            None, memory_id=memory.id, actor_user_id=uid
        )
        assert updated is not None
        row = await _get_memory(memory.id)
        assert row is not None and row.summary == {"language": "en"}


class TestUpdateMemorySummary:
    """#10-14 落库 / 审计契约 / 隔离 / 副作用边界。"""

    @pytest.mark.asyncio
    async def test_update_persists_summary(self, register_and_login) -> None:
        _headers, user = await register_and_login(prefix="t6-w4-persist")
        uid = uuid.UUID(user["id"])
        memory = await _create_memory(
            uid, value={"language": "en", "note": "x" * 130}
        )
        result = await update_memory_summary(
            None, memory_id=memory.id, actor_user_id=uid
        )
        row = await _get_memory(memory.id)
        assert result is not None
        assert row is not None and row.summary == result.summary
        assert isinstance(result.summary, dict)
        assert result.total_chars == len(_canonical(result.summary))
        assert result.field_count == len(result.summary)

    @pytest.mark.asyncio
    async def test_audit_contract_without_value(self, register_and_login) -> None:
        _headers, user = await register_and_login(prefix="t6-w4-audit")
        uid = uuid.UUID(user["id"])
        secret_value = {
            "language": "en",
            "note": "secret-memory-value-w4",
            "question": "secret-user-question-full-text",
        }
        memory = await _create_memory(uid, value=secret_value)
        result = await update_memory_summary(
            None, memory_id=memory.id, actor_user_id=uid
        )
        events = await _summary_events(memory.id)
        assert result is not None
        assert len(events) == 1
        details = events[0].details
        assert set(details) == {
            "memory_id",
            "key",
            "memory_type",
            "truncated",
            "field_count",
            "total_chars",
        }
        assert details["memory_id"] == str(memory.id)
        assert details["key"] == memory.key
        assert details["memory_type"] == "preference"
        assert details["truncated"] is False
        serialized = json.dumps(details, ensure_ascii=False)
        assert "secret-memory-value-w4" not in serialized
        assert "secret-user-question-full-text" not in serialized

    @pytest.mark.asyncio
    async def test_unchanged_summary_writes_no_audit(
        self, register_and_login
    ) -> None:
        _headers, user = await register_and_login(prefix="t6-w4-noaudit")
        uid = uuid.UUID(user["id"])
        memory = await _create_memory(
            uid, value={"language": "en"}, summary={"language": "en"}
        )
        first = await update_memory_summary(
            None, memory_id=memory.id, actor_user_id=uid
        )
        second = await update_memory_summary(
            None, memory_id=memory.id, actor_user_id=uid
        )
        assert first is not None and second is not None
        assert await _summary_events(memory.id) == []

        async with SessionLocal() as db:
            row = await db.get(AgentMemory, memory.id)
            row.value = {"language": "zh"}
            await db.commit()
        changed = await update_memory_summary(
            None, memory_id=memory.id, actor_user_id=uid
        )
        assert changed is not None and changed.summary == {"language": "zh"}
        assert len(await _summary_events(memory.id)) == 1
        await update_memory_summary(None, memory_id=memory.id, actor_user_id=uid)
        assert len(await _summary_events(memory.id)) == 1

    @pytest.mark.asyncio
    async def test_ownership_isolation(self, register_and_login) -> None:
        _headers_a, user_a = await register_and_login(prefix="t6-w4-owner-a")
        _headers_b, user_b = await register_and_login(prefix="t6-w4-owner-b")
        uid_a = uuid.UUID(user_a["id"])
        uid_b = uuid.UUID(user_b["id"])
        memory = await _create_memory(uid_a, value={"language": "en"})
        cross = await update_memory_summary(
            None, memory_id=memory.id, actor_user_id=uid_b
        )
        missing = await update_memory_summary(
            None, memory_id=uuid.uuid4(), actor_user_id=uid_a
        )
        assert cross is None and missing is None
        assert await _summary_events(memory.id) == []
        row = await _get_memory(memory.id)
        assert row is not None and row.summary is None

    @pytest.mark.asyncio
    async def test_side_effect_boundary(self, register_and_login) -> None:
        _headers, user = await register_and_login(prefix="t6-w4-sideeffect")
        uid = uuid.UUID(user["id"])
        suppress_until = datetime.now(timezone.utc) + timedelta(hours=1)
        last_accessed_at = datetime(2026, 8, 1, tzinfo=timezone.utc)
        memory = await _create_memory(
            uid,
            memory_type="pattern",
            value={"mode": "thorough"},
            tier="working",
            importance_score=0.8,
            status="suppressed",
            suppress_until=suppress_until,
            churn_count=2,
            source=MemorySource.conversation.value,
            confidence=0.6,
            last_accessed_at=last_accessed_at,
        )
        result = await update_memory_summary(
            None, memory_id=memory.id, actor_user_id=uid
        )
        row = await _get_memory(memory.id)
        assert result is not None and row is not None
        assert row.summary == {"mode": "thorough"}
        assert row.value == {"mode": "thorough"}
        assert row.tier == "working"
        assert row.importance_score == pytest.approx(0.8)
        assert row.status == "suppressed"
        assert row.suppress_until == suppress_until
        assert row.churn_count == 2
        assert row.confidence == pytest.approx(0.6)
        assert row.last_accessed_at == last_accessed_at


class TestConfigWiring:
    """#15 配置接线。"""

    def test_settings_defaults_and_mapping_match_doc(self) -> None:
        assert settings.agent_memory_summary_max_field_chars == 120
        assert settings.agent_memory_summary_max_items == 20
        assert settings.agent_memory_summary_max_depth == 3
        assert settings.agent_memory_summary_max_total_chars == 800
        assert settings.agent_memory_summary_truncation_marker == "..."
        assert SummaryConfig().max_field_chars == 120
        assert SummaryConfig().max_items == 20
        assert SummaryConfig().max_depth == 3
        assert SummaryConfig().max_total_chars == 800
        assert SummaryConfig().truncation_marker == "..."

        config = summary_config_from_settings()
        assert config.max_field_chars == settings.agent_memory_summary_max_field_chars
        assert config.max_items == settings.agent_memory_summary_max_items
        assert config.max_depth == settings.agent_memory_summary_max_depth
        assert config.max_total_chars == settings.agent_memory_summary_max_total_chars
        assert config.truncation_marker == settings.agent_memory_summary_truncation_marker
