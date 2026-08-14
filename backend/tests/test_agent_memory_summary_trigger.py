"""T6 长期记忆分层 · 记忆摘要触发接线测试（W5 §4.5 维护窗）。

覆盖：apply_observation / upsert_memory 写完 value 后自动刷新 summary，
reevaluate_importance 重算落库后自动刷新；重复触发不重复审计；刷新失败不
阻塞主写入。
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.agent_memory import AgentMemory
from app.models.audit_log import AuditLog
from app.services.agent.memory import upsert_memory
from app.services.agent.memory_governance import (
    MemoryObservation,
    MemorySource,
    apply_observation,
)
from app.services.agent.memory_tiering import reevaluate_importance


def _obs(
    user_id: uuid.UUID,
    *,
    key: str | None = None,
    value: dict | str = {"language": "en"},
) -> MemoryObservation:
    return MemoryObservation(
        user_id=user_id,
        memory_type="preference",
        key=key or f"trigger-{uuid.uuid4().hex[:8]}",
        value=value,
        source=MemorySource.rule_inference,
    )


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


class TestApplyObservationTrigger:
    """apply_observation 写完 value 后自动刷新 summary。"""

    @pytest.mark.asyncio
    async def test_created_fills_summary(self, register_and_login) -> None:
        _headers, user = await register_and_login(prefix="t6-trigger-apply-new")
        uid = uuid.UUID(user["id"])
        result = await apply_observation(None, observation=_obs(uid))
        row = await _get_memory(result.memory_id)
        assert result.action == "created"
        assert row is not None and row.summary == {"language": "en"}
        assert len(await _summary_events(result.memory_id)) == 1

    @pytest.mark.asyncio
    async def test_overwrite_updates_summary(self, register_and_login) -> None:
        _headers, user = await register_and_login(prefix="t6-trigger-apply-over")
        uid = uuid.UUID(user["id"])
        key = f"trigger-{uuid.uuid4().hex[:8]}"
        created = await apply_observation(None, observation=_obs(uid, key=key))
        overwritten = await apply_observation(
            None, observation=_obs(uid, key=key, value={"language": "zh"})
        )
        row = await _get_memory(created.memory_id)
        assert overwritten.action == "overwritten"
        assert row is not None and row.summary == {"language": "zh"}
        assert len(await _summary_events(created.memory_id)) == 2

    @pytest.mark.asyncio
    async def test_repeated_trigger_no_duplicate_audit(
        self, register_and_login
    ) -> None:
        _headers, user = await register_and_login(prefix="t6-trigger-apply-repeat")
        uid = uuid.UUID(user["id"])
        key = f"trigger-{uuid.uuid4().hex[:8]}"
        first = await apply_observation(None, observation=_obs(uid, key=key))
        reinforced = await apply_observation(None, observation=_obs(uid, key=key))
        row = await _get_memory(first.memory_id)
        assert reinforced.action == "reinforced"
        assert row is not None and row.summary == {"language": "en"}
        assert len(await _summary_events(first.memory_id)) == 1

    @pytest.mark.asyncio
    async def test_trigger_failure_does_not_block_write(
        self,
        register_and_login,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _headers, user = await register_and_login(prefix="t6-trigger-apply-fail")
        uid = uuid.UUID(user["id"])

        async def _boom(*_args, **_kwargs) -> None:
            raise RuntimeError("summary db unavailable")

        monkeypatch.setattr(
            "app.services.agent.memory_governance.update_memory_summary", _boom
        )
        result = await apply_observation(None, observation=_obs(uid))
        row = await _get_memory(result.memory_id)
        assert result.action == "created"
        assert row is not None and row.summary is None


class TestUpsertMemoryTrigger:
    """upsert_memory 写完 value 后自动刷新 summary。"""

    @pytest.mark.asyncio
    async def test_upsert_fills_and_updates_summary(
        self, register_and_login
    ) -> None:
        _headers, user = await register_and_login(prefix="t6-trigger-upsert")
        uid = uuid.UUID(user["id"])
        key = f"trigger-{uuid.uuid4().hex[:8]}"
        async with SessionLocal() as db:
            memory_id = await upsert_memory(
                db, uid, "preference", key, {"language": "en"}
            )
        row = await _get_memory(memory_id)
        assert row is not None and row.summary == {"language": "en"}
        assert len(await _summary_events(memory_id)) == 1

        async with SessionLocal() as db:
            await upsert_memory(db, uid, "preference", key, {"language": "zh"})
        row = await _get_memory(memory_id)
        assert row is not None and row.summary == {"language": "zh"}
        assert len(await _summary_events(memory_id)) == 2

        async with SessionLocal() as db:
            await upsert_memory(db, uid, "preference", key, {"language": "zh"})
        assert len(await _summary_events(memory_id)) == 2


class TestReevaluateImportanceTrigger:
    """reevaluate_importance 重算落库后自动刷新 summary。"""

    @pytest.mark.asyncio
    async def test_reevaluate_fills_summary_once(
        self, register_and_login
    ) -> None:
        _headers, user = await register_and_login(prefix="t6-trigger-tier")
        uid = uuid.UUID(user["id"])
        async with SessionLocal() as db:
            memory = AgentMemory(
                user_id=uid,
                memory_type="preference",
                key=f"trigger-{uuid.uuid4().hex[:8]}",
                value={"language": "en", "note": "x" * 130},
                tier="long_term",
                source=MemorySource.rule_inference.value,
                confidence=0.7,
                last_accessed_at=datetime.now(timezone.utc),
                status="active",
                churn_count=0,
            )
            db.add(memory)
            await db.commit()
            await db.refresh(memory)
            memory_id = memory.id
        result = await reevaluate_importance(
            None, memory_id=memory_id, actor_user_id=uid
        )
        row = await _get_memory(memory_id)
        assert result is not None
        assert row is not None
        assert row.summary == {"language": "en", "note": "x" * 120 + "..."}
        assert len(await _summary_events(memory_id)) == 1

        await reevaluate_importance(None, memory_id=memory_id, actor_user_id=uid)
        assert len(await _summary_events(memory_id)) == 1
