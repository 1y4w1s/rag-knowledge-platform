"""G4-2.2 · 编辑模式 SSE 事件流（stream_agent_edit_events）。

验收锚点：
- 事件顺序硬约束（R4-4 / G4 §3.3）：tool_* → citation → token →
  approval_required → done。
- 草稿成功 → 发 approval_required（含 approval_id / 草稿预览 / 来源引用 /
  can_adopt），且位于 done 之前。
- G4-E11（全无命中 / 越权 / 文件名非法）→ 不发 approval_required，
  改发 refusal（带 G4-1.3 reason 码文案），位于 done 之前。
- 不依赖真实生成延迟：用同步生成器 + AsyncMock 编排 event collector，
  直接驱动真实渲染顺序逻辑（run_react_loop / prepare_agent_generation /
  db.get / save_turn 均 mock）。

另含一条 runtime 执行测试：确认 run_react_loop 经编辑 planner 真实执行
generate_faq_draft 末步（G4-2.2「让 runtime 按 planner 序列执行」）。
"""

from __future__ import annotations

import json
import uuid
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import SessionLocal
from app.models.agent_approval import AgentApproval
from app.models.enums import AgentRunMode
from app.services.agent.dispatch import create_edit_tool_planner
from app.services.agent.finalize import AgentGenerationPlan
from app.services.agent.runtime import run_react_loop
from app.services.agent.stream import stream_agent_edit_events
from app.services.agent.tools.generate_faq_draft import (
    GenerateFaqDraftFailure,
    GenerateFaqDraftOutput,
    GenerateFaqDraftToolResult,
)
from app.services.agent.tools.registry import AgentToolName
from app.services.agent.tools.scope import AgentToolScope
from app.services.agent.tools.semantic_search import (
    SemanticSearchHit,
    SemanticSearchOutput,
)
from app.services.agent.types import AgentRunOutcome, AgentStepRecord
from app.services.rag.thread_persistence import create_workspace_thread
from app.services.workspace.scope import WorkspaceKind, WorkspaceScope


# --------------------------------------------------------------------------- #
# 事件帧解析 + 最小编排工具
# --------------------------------------------------------------------------- #

def _parse_frame(frame: str) -> tuple[str, dict]:
    assert frame.startswith("event: "), frame
    rest = frame[len("event: "):]
    ev, _sep, data_str = rest.partition("\ndata: ")
    return ev, json.loads(data_str.strip())


async def _collect(frames) -> list[tuple[str, dict]]:
    out: list[tuple[str, dict]] = []
    async for frame in frames:
        out.append(_parse_frame(frame))
    return out


def _names(events: list[tuple[str, dict]]) -> list[str]:
    return [ev for ev, _ in events]


def _first(events: list[tuple[str, dict]], name: str) -> dict:
    for ev, data in events:
        if ev == name:
            return data
    raise AssertionError(f"event not found: {name}")


def _index_of(events: list[tuple[str, dict]], name: str) -> int:
    for i, (ev, _d) in enumerate(events):
        if ev == name:
            return i
    raise AssertionError(f"event not found: {name}")


# --------------------------------------------------------------------------- #
# outcome 构造（合成 AgentRunOutcome，驱动真实渲染逻辑）
# --------------------------------------------------------------------------- #

def _draft_ok_outcome(
    run_id: UUID, approval_id: UUID, filename: str, kb_name: str
) -> AgentRunOutcome:
    draft_data = GenerateFaqDraftToolResult(
        ok=True,
        data=GenerateFaqDraftOutput(
            approval_id=approval_id,
            filename=filename,
            kb_name=kb_name,
            draft_chars=120,
            citation_count=1,
        ),
        summary="已生成 FAQ 草稿",
        reason=None,
    )
    step = AgentStepRecord(
        step_index=2,
        tool_name=AgentToolName.generate_faq_draft.value,
        args={"kb_id": str(uuid.uuid4()), "filename": filename, "source_chunk_ids": []},
        ok=True,
        summary="已生成 FAQ 草稿",
        latency_ms=10,
        step_id=uuid.uuid4(),
        data=draft_data,
    )
    return AgentRunOutcome(
        run_id=run_id,
        steps_used=2,
        max_steps=5,
        capped=False,
        timed_out=False,
        steps=(step,),
    )


def _draft_fail_outcome(run_id: UUID, reason: GenerateFaqDraftFailure) -> AgentRunOutcome:
    draft_data = GenerateFaqDraftToolResult(
        ok=False, data=None, summary="库内无足够依据", reason=reason
    )
    step = AgentStepRecord(
        step_index=2,
        tool_name=AgentToolName.generate_faq_draft.value,
        args={"kb_id": None, "filename": "FAQ_x.md", "source_chunk_ids": []},
        ok=False,
        summary="库内无足够依据",
        latency_ms=10,
        step_id=uuid.uuid4(),
        data=draft_data,
    )
    return AgentRunOutcome(
        run_id=run_id,
        steps_used=2,
        max_steps=5,
        capped=False,
        timed_out=False,
        steps=(step,),
    )


def _tool_event_tuples() -> list[tuple[str, dict]]:
    return [
        ("tool_start", {"step": 1, "tool": "semantic_search", "args_summary": "年假"}),
        (
            "tool_result",
            {"step": 1, "tool": "semantic_search", "ok": True, "summary": "命中 2", "latency_ms": 5},
        ),
        ("agent_budget", {"steps_used": 1, "max_steps": 5, "capped": False}),
    ]


def _workspace(user_id: UUID) -> WorkspaceScope:
    return WorkspaceScope(kind=WorkspaceKind.personal, user_id=user_id, org_id=None)


def _patch_edit_runtime(monkeypatch, outcome, citations, *, tool_events):
    async def _fake_run(*args, hooks=None, **kwargs):
        # 把合成 tool 事件灌入 stream_agent_edit_events 内部创建的 hooks，
        # 模拟 run_react_loop 真实执行后产出的 tool_start/result/budget 序列。
        # 必须 async：stream_agent_edit_events 以 `await run_react_loop(...)` 调用。
        if hooks is not None:
            hooks.events.extend(tool_events)
        return outcome

    monkeypatch.setattr(
        "app.services.agent.stream.run_react_loop",
        _fake_run,
    )
    gen = AgentGenerationPlan(
        gated_chunks=(),
        citations=tuple(citations),
        refusal=not citations,
    )
    monkeypatch.setattr(
        "app.services.agent.stream.prepare_agent_generation",
        AsyncMock(return_value=gen),
    )


async def _run_edit_sse(monkeypatch, outcome, citations, *, can_adopt=False, kb_id=None):
    run_id = outcome.run_id
    approval_id = uuid.uuid4()
    tool_events = _tool_event_tuples()

    _patch_edit_runtime(monkeypatch, outcome, citations, tool_events=tool_events)

    fake_approval = MagicMock(spec=AgentApproval)
    fake_approval.kb_id = kb_id or uuid.uuid4()
    fake_approval.filename = "FAQ_年假.md"
    fake_approval.payload_json = {
        "markdown": "# FAQ：年假\n\n> 本草稿由 Agent 依据资料库检索片段生成。\n\n## 问：关于「年假」\n答：员工年假规定为 10 天，需提前申请。"
    }
    db = AsyncMock(spec=AsyncSession)
    db.get = AsyncMock(return_value=fake_approval)
    save_turn = AsyncMock(return_value=uuid.uuid4())

    # 用真实 planner 占位（run_react_loop 已 mock，不会被真正调用）
    planner = create_edit_tool_planner("年假 FAQ", default_kb_id=None)

    frames = stream_agent_edit_events(
        db,
        user_id=uuid.uuid4(),
        message="年假 FAQ",
        thread_id=uuid.uuid4(),
        workspace=_workspace(uuid.uuid4()),
        tool_scope=AgentToolScope(),
        planner=planner,
        workspace_mode=False,
        can_adopt=can_adopt,
        save_turn=save_turn,
        save_kwargs={"kb_id": kb_id or uuid.uuid4(), "thread_id": uuid.uuid4()},
    )
    return await _collect(frames)


# --------------------------------------------------------------------------- #
# 成功路径：approval_required 顺序 + 载荷
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_edit_sse_success_order_and_approval_required(monkeypatch) -> None:
    """tool → citation → token → approval_required → done（严格顺序）。"""
    run_id = uuid.uuid4()
    approval_id = uuid.uuid4()
    kb_id = uuid.uuid4()
    outcome = _draft_ok_outcome(run_id, approval_id, "FAQ_年假.md", "制度库")
    citations = [{"doc_name": "员工手册.md", "chunk_id": str(uuid.uuid4())}]

    events = await _run_edit_sse(
        monkeypatch, outcome, citations, can_adopt=True, kb_id=kb_id
    )
    names = _names(events)
    assert names == [
        "tool_start",
        "tool_result",
        "agent_budget",
        "citation",
        "token",
        "approval_required",
        "done",
    ], names

    # approval_required 前于 done
    assert _index_of(events, "approval_required") < _index_of(events, "done")
    # citation 前于 token
    assert _index_of(events, "citation") < _index_of(events, "token")

    approval = _first(events, "approval_required")
    assert approval["approval_id"] == str(approval_id)
    assert approval["draft_type"] == "faq"
    assert approval["filename"] == "FAQ_年假.md"
    assert approval["kb_id"] == str(kb_id)
    assert approval["kb_name"] == "制度库"
    assert approval["can_adopt"] is True
    assert "markdown" not in approval  # 不背全文
    assert approval["draft_preview"]  # 有预览片段

    done = _first(events, "done")
    assert done["approval_id"] == str(approval_id)
    assert done["approval_status"] == "pending"


@pytest.mark.asyncio
async def test_edit_sse_success_multi_citation_before_token(monkeypatch) -> None:
    """多 citation 全部位于 token 之前。"""
    run_id = uuid.uuid4()
    approval_id = uuid.uuid4()
    outcome = _draft_ok_outcome(run_id, approval_id, "FAQ_x.md", "k")
    citations = [
        {"doc_name": "a.md", "chunk_id": str(uuid.uuid4())},
        {"doc_name": "b.md", "chunk_id": str(uuid.uuid4())},
    ]
    events = await _run_edit_sse(monkeypatch, outcome, citations)
    names = _names(events)
    assert names.count("citation") == 2
    assert names.index("citation") < names.index("token")
    assert names.index("token") < names.index("approval_required")
    # 两条 citation 都先于 token
    for i, n in enumerate(names):
        if n == "token":
            assert "citation" in names[:i]
            break


# --------------------------------------------------------------------------- #
# 拒答路径：G4-E11 / 越权 / 文件名非法 → refusal（无 approval_required）
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_edit_sse_no_source_refusal_no_approval_g4_e11(monkeypatch) -> None:
    """全无命中（G4-E11）：不发 approval_required，改发 refusal（reason=no_source）。"""
    run_id = uuid.uuid4()
    outcome = _draft_fail_outcome(run_id, GenerateFaqDraftFailure.no_source)
    events = await _run_edit_sse(monkeypatch, outcome, citations=[])

    names = _names(events)
    assert "approval_required" not in names
    assert "refusal" in names
    assert names[-1] == "done"
    assert _index_of(events, "refusal") < _index_of(events, "done")

    refusal = _first(events, "refusal")
    assert refusal["reason"] == "no_source"
    assert "未检索到" in refusal["message"]

    done = _first(events, "done")
    assert done["approval_id"] is None
    assert done["approval_status"] is None


@pytest.mark.asyncio
async def test_edit_sse_kb_not_visible_refusal(monkeypatch) -> None:
    """目标库不可见 → refusal（reason=kb_not_visible）。"""
    run_id = uuid.uuid4()
    outcome = _draft_fail_outcome(run_id, GenerateFaqDraftFailure.kb_not_visible)
    events = await _run_edit_sse(monkeypatch, outcome, citations=[])
    refusal = _first(events, "refusal")
    assert refusal["reason"] == "kb_not_visible"
    assert "不可见" in refusal["message"]


@pytest.mark.asyncio
async def test_edit_sse_invalid_filename_refusal(monkeypatch) -> None:
    """文件名非 .md → refusal（reason=invalid_filename）。"""
    run_id = uuid.uuid4()
    outcome = _draft_fail_outcome(run_id, GenerateFaqDraftFailure.invalid_filename)
    events = await _run_edit_sse(monkeypatch, outcome, citations=[])
    refusal = _first(events, "refusal")
    assert refusal["reason"] == "invalid_filename"
    assert ".md" in refusal["message"]


# --------------------------------------------------------------------------- #
# runtime 执行：run_react_loop 经编辑 planner 真实跑通 generate_faq_draft
# --------------------------------------------------------------------------- #

def _personal_workspace(user_id: UUID) -> WorkspaceScope:
    return WorkspaceScope(kind=WorkspaceKind.personal, user_id=user_id, org_id=None)


async def _create_personal_thread(user_id: UUID) -> UUID:
    async with SessionLocal() as db:
        thread = await create_workspace_thread(
            db,
            user_id=user_id,
            workspace_kind=WorkspaceKind.personal,
            workspace_org_id=None,
            department_id=None,
        )
        await db.commit()
        return thread.id


@pytest.mark.asyncio
async def test_edit_runtime_runs_generate_faq_draft(
    register_and_login, monkeypatch
) -> None:
    """G4-2.2：runtime 按编辑 planner 序列真实执行末步 generate_faq_draft。"""
    _user, user = await register_and_login(prefix="g4-edit-rt")
    user_id = UUID(user["id"])
    thread_id = await _create_personal_thread(user_id)

    hit = SemanticSearchHit(
        chunk_id=uuid.uuid4(),
        kb_id=uuid.uuid4(),
        kb_name="制度库",
        doc_name="员工手册.md",
        page=1,
        section_title="1.1 年假",
        excerpt="员工年假规定为 10 天",
        score=0.9,
    )
    semantic_mock = AsyncMock(
        return_value=type(
            "R",
            (),
            {
                "ok": True,
                "summary": "命中 1",
                "data": SemanticSearchOutput(hits=(hit,), retrieval_ms=1),
            },
        )()
    )
    gen_mock = AsyncMock(
        return_value=GenerateFaqDraftToolResult(
            ok=True,
            data=GenerateFaqDraftOutput(
                approval_id=uuid.uuid4(),
                filename="FAQ_年假.md",
                kb_name="制度库",
                draft_chars=80,
                citation_count=1,
            ),
            summary="已生成 FAQ 草稿",
            reason=None,
        )
    )
    monkeypatch.setattr(
        "app.services.agent.runtime.run_semantic_search", semantic_mock
    )
    monkeypatch.setattr(
        "app.services.agent.runtime.run_generate_faq_draft", gen_mock
    )

    planner = create_edit_tool_planner("年假 FAQ", default_kb_id=None)
    async with SessionLocal() as db:
        outcome = await run_react_loop(
            db,
            user_id=user_id,
            thread_id=thread_id,
            query="年假 FAQ",
            workspace=_personal_workspace(user_id),
            tool_scope=AgentToolScope(),
            planner=planner,
            mode=AgentRunMode.edit,
            max_steps=5,
        )
        await db.commit()

    draft_steps = [
        s for s in outcome.steps if s.tool_name == AgentToolName.generate_faq_draft.value
    ]
    assert draft_steps, "编辑 planner 末步应执行 generate_faq_draft"
    assert draft_steps[-1].ok is True
    gen_mock.assert_awaited()
