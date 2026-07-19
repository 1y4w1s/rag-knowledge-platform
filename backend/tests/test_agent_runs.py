"""G3-0.4：services/agent/runs.py CRUD · user_id 隔离（G3-E10）。"""

from __future__ import annotations

import uuid

import pytest

from app.core.database import SessionLocal
from app.models.enums import AgentRunMode, AgentRunStatus, AgentStepStatus
from app.services.agent.runs import (
    create_agent_run,
    create_agent_step,
    finish_agent_run,
    finish_agent_step,
    get_agent_run_for_user,
    list_agent_steps_for_run,
    update_agent_run_steps_used,
)
from app.services.rag.persistence import save_workspace_chat_turn
from app.services.rag.thread_persistence import create_workspace_thread
from app.services.workspace.scope import WorkspaceKind


async def _create_personal_thread(user_id: uuid.UUID) -> uuid.UUID:
    async with SessionLocal() as db:
        thread = await create_workspace_thread(
            db,
            user_id=user_id,
            workspace_kind=WorkspaceKind.personal,
            workspace_org_id=None,
            department_id=None,
        )
        return thread.id


@pytest.mark.asyncio
async def test_create_run_and_step(register_and_login) -> None:
    """创建 run/step 落库字段正确。"""
    _, user = await register_and_login(prefix="g3-run-owner")
    user_id = uuid.UUID(user["id"])
    thread_id = await _create_personal_thread(user_id)

    async with SessionLocal() as db:
        run = await create_agent_run(
            db,
            thread_id=thread_id,
            user_id=user_id,
            max_steps=5,
        )
        assert run.mode == AgentRunMode.thorough
        assert run.status == AgentRunStatus.running
        assert run.steps_used == 0
        assert run.max_steps == 5
        assert run.finished_at is None

        step = await create_agent_step(
            db,
            run_id=run.id,
            user_id=user_id,
            step_index=1,
            tool_name="semantic_search",
            args_json={"query": "年假", "kb_ids": []},
        )
        assert step is not None
        assert step.status == AgentStepStatus.running
        assert step.tool_name == "semantic_search"

        finished = await finish_agent_step(
            db,
            step_id=step.id,
            user_id=user_id,
            ok=True,
            result_summary="命中 3 条",
            latency_ms=42,
        )
        assert finished is not None
        assert finished.status == AgentStepStatus.done
        assert finished.ok is True
        assert finished.latency_ms == 42

        updated = await update_agent_run_steps_used(
            db,
            run_id=run.id,
            user_id=user_id,
            steps_used=1,
        )
        assert updated is not None
        assert updated.steps_used == 1

        assistant_id = await save_workspace_chat_turn(
            db,
            user_id=user_id,
            workspace_kind=WorkspaceKind.personal,
            workspace_org_id=None,
            department_id=None,
            user_content="精准问题",
            assistant_content="精准回答",
            citations=[],
            thread_id=thread_id,
        )
        done = await finish_agent_run(
            db,
            run_id=run.id,
            user_id=user_id,
            status=AgentRunStatus.completed,
            assistant_message_id=assistant_id,
        )
        assert done is not None
        assert done.status == AgentRunStatus.completed
        assert done.assistant_message_id == assistant_id
        assert done.finished_at is not None

        steps = await list_agent_steps_for_run(
            db,
            run_id=run.id,
            user_id=user_id,
        )
        assert steps is not None
        assert len(steps) == 1
        assert steps[0].step_index == 1

        await db.commit()


@pytest.mark.asyncio
async def test_run_isolated_by_user_id(register_and_login) -> None:
    """G3-E10：非 owner 无法读/写 run 与 step。"""
    _, owner = await register_and_login(prefix="g3-run-owner-a")
    _, other = await register_and_login(prefix="g3-run-other-b")
    owner_id = uuid.UUID(owner["id"])
    other_id = uuid.UUID(other["id"])
    thread_id = await _create_personal_thread(owner_id)

    async with SessionLocal() as db:
        run = await create_agent_run(
            db,
            thread_id=thread_id,
            user_id=owner_id,
        )
        step = await create_agent_step(
            db,
            run_id=run.id,
            user_id=owner_id,
            step_index=1,
            tool_name="list_knowledge_bases",
        )
        assert step is not None
        await db.commit()

    async with SessionLocal() as db:
        assert (
            await get_agent_run_for_user(db, run_id=run.id, user_id=other_id) is None
        )
        assert (
            await create_agent_step(
                db,
                run_id=run.id,
                user_id=other_id,
                step_index=2,
                tool_name="semantic_search",
            )
            is None
        )
        assert (
            await finish_agent_step(
                db,
                step_id=step.id,
                user_id=other_id,
                ok=True,
                result_summary="blocked",
                latency_ms=1,
            )
            is None
        )
        assert (
            await update_agent_run_steps_used(
                db,
                run_id=run.id,
                user_id=other_id,
                steps_used=99,
            )
            is None
        )
        assert (
            await finish_agent_run(
                db,
                run_id=run.id,
                user_id=other_id,
                status=AgentRunStatus.failed,
            )
            is None
        )
        assert (
            await list_agent_steps_for_run(
                db,
                run_id=run.id,
                user_id=other_id,
            )
            is None
        )

    async with SessionLocal() as db:
        still_running = await get_agent_run_for_user(
            db,
            run_id=run.id,
            user_id=owner_id,
        )
        assert still_running is not None
        assert still_running.status == AgentRunStatus.running
        assert still_running.steps_used == 0


@pytest.mark.asyncio
async def test_finish_step_error_status(register_and_login) -> None:
    """tool 失败时 step status=error。"""
    _, user = await register_and_login(prefix="g3-run-err")
    user_id = uuid.UUID(user["id"])
    thread_id = await _create_personal_thread(user_id)

    async with SessionLocal() as db:
        run = await create_agent_run(
            db,
            thread_id=thread_id,
            user_id=user_id,
        )
        step = await create_agent_step(
            db,
            run_id=run.id,
            user_id=user_id,
            step_index=1,
            tool_name="semantic_search",
        )
        assert step is not None

        failed = await finish_agent_step(
            db,
            step_id=step.id,
            user_id=user_id,
            ok=False,
            result_summary="无权限",
            latency_ms=7,
        )
        assert failed is not None
        assert failed.status == AgentStepStatus.error
        assert failed.ok is False

        capped = await finish_agent_run(
            db,
            run_id=run.id,
            user_id=user_id,
            status=AgentRunStatus.capped,
        )
        assert capped is not None
        assert capped.status == AgentRunStatus.capped

        await db.commit()
