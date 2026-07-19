"""G4-2.3 · dispatch 路由 + 库内编辑流 + can_adopt 权限信号。

验收锚点：
- `stream_agent_kb_edit_events` 是 `stream_agent_edit_events` 的库内薄封装：
  事件序 tool → citation → token → approval_required → done 不回退；
  `approval_required.kb_id` 来自「默认目标库 = 路径 kb」（G4-E19 / H4-2-B）。
- 三模式 dispatch：fast/thorough 行为零改动（由路由分支保证，本文件以
  `can_adopt` 权限信号 + kb 封装覆盖「edit 新路径」核心）。
- `can_user_adopt_kb` / `can_user_adopt_in_workspace` 精确/启发式判定
  Member 永不可采纳（HA-2-A · H4-1-B）。

不依赖真实生成延迟：mock run_react_loop / prepare_agent_generation / db.get。
"""

from __future__ import annotations

import json
import uuid
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_approval import AgentApproval
from app.models.enums import OrgRole
from app.services.agent.dispatch import create_edit_tool_planner
from app.services.agent.stream import stream_agent_kb_edit_events
from app.services.agent.tools.generate_faq_draft import (
    GenerateFaqDraftFailure,
    GenerateFaqDraftOutput,
    GenerateFaqDraftToolResult,
)
from app.services.agent.tools.registry import AgentToolName
from app.services.agent.tools.scope import AgentToolScope
from app.services.agent.types import AgentRunOutcome, AgentStepRecord
from app.services.org.scope import (
    can_user_adopt_in_workspace,
    can_user_adopt_kb,
)
from app.services.workspace.scope import WorkspaceKind, WorkspaceScope


# --------------------------------------------------------------------------- #
# SSE 帧解析 + 最小编排工具（与 test_agent_g4_edit_sse.py 同构）
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
# outcome / 编排构造
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


def _patch_runtime(monkeypatch, outcome, citations, *, tool_events):
    async def _fake_run(*args, hooks=None, **kwargs):
        if hooks is not None:
            hooks.events.extend(tool_events)
        return outcome

    monkeypatch.setattr(
        "app.services.agent.stream.run_react_loop",
        _fake_run,
    )
    from app.services.agent.finalize import AgentGenerationPlan

    gen = AgentGenerationPlan(
        gated_chunks=(),
        citations=tuple(citations),
        refusal=not citations,
    )
    monkeypatch.setattr(
        "app.services.agent.stream.prepare_agent_generation",
        AsyncMock(return_value=gen),
    )


async def _run_kb_edit_sse(
    monkeypatch,
    outcome,
    citations,
    *,
    can_adopt: bool = False,
    path_kb_id: UUID,
    draft_kb_id: UUID,
) -> list[tuple[str, dict]]:
    """驱动 `stream_agent_kb_edit_events`（库内封装）并收集事件。"""
    # stream_agent_kb_edit_events 内部硬编码 save_turn=save_chat_turn（真实落库，
    # 会经 resolve_thread_for_message 查库）；测试以 mock 替换，保持无真实 DB 依赖。
    monkeypatch.setattr("app.services.agent.stream.save_chat_turn", AsyncMock())
    tool_events = _tool_event_tuples()
    _patch_runtime(monkeypatch, outcome, citations, tool_events=tool_events)

    fake_approval = MagicMock(spec=AgentApproval)
    fake_approval.kb_id = draft_kb_id  # 库内 edit：默认目标库 = 路径 kb（G4-E19）
    fake_approval.filename = "FAQ_年假.md"
    fake_approval.payload_json = {
        "markdown": "# FAQ：年假\n\n> 本草稿由 Agent 依据资料库检索片段生成。"
    }
    db = AsyncMock(spec=AsyncSession)
    db.get = AsyncMock(return_value=fake_approval)
    save_turn = AsyncMock(return_value=uuid.uuid4())

    planner = create_edit_tool_planner("年假 FAQ", default_kb_id=path_kb_id)
    frames = stream_agent_kb_edit_events(
        db,
        kb_id=path_kb_id,
        user_id=uuid.uuid4(),
        message="年假 FAQ",
        thread_id=uuid.uuid4(),
        workspace=_workspace(uuid.uuid4()),
        tool_scope=AgentToolScope(),
        planner=planner,
        can_adopt=can_adopt,
    )
    return await _collect(frames)


# --------------------------------------------------------------------------- #
# G4-2.3 · 库内编辑流封装 + G4-E19 默认目标库
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_kb_edit_stream_delegates_event_order_and_default_kb(
    monkeypatch,
) -> None:
    """stream_agent_kb_edit_events 复用编辑渲染：序 tool→citation→token→
    approval_required→done；approval_required.kb_id = 路径 kb（G4-E19）。"""
    run_id = uuid.uuid4()
    approval_id = uuid.uuid4()
    path_kb_id = uuid.uuid4()  # 库内路径 kb
    draft_kb_id = path_kb_id  # generate_faq_draft 落库到路径 kb
    outcome = _draft_ok_outcome(run_id, approval_id, "FAQ_年假.md", "制度库")
    citations = [{"doc_name": "员工手册.md", "chunk_id": str(uuid.uuid4())}]

    events = await _run_kb_edit_sse(
        monkeypatch,
        outcome,
        citations,
        can_adopt=True,
        path_kb_id=path_kb_id,
        draft_kb_id=draft_kb_id,
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

    # 顺序硬约束不回退
    assert _index_of(events, "approval_required") < _index_of(events, "done")
    assert _index_of(events, "citation") < _index_of(events, "token")

    approval = _first(events, "approval_required")
    assert approval["approval_id"] == str(approval_id)
    assert approval["kb_id"] == str(path_kb_id)  # G4-E19：默认目标库 = 路径 kb
    assert approval["can_adopt"] is True

    done = _first(events, "done")
    assert done["approval_id"] == str(approval_id)
    assert done["approval_status"] == "pending"


@pytest.mark.asyncio
async def test_kb_edit_stream_refusal_on_no_source(monkeypatch) -> None:
    """库内 edit：全无命中（G4-E11）→ refusal，无 approval_required。"""
    run_id = uuid.uuid4()
    path_kb_id = uuid.uuid4()
    draft_data = GenerateFaqDraftToolResult(
        ok=False, data=None, summary="库内无足够依据", reason=GenerateFaqDraftFailure.no_source
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
    outcome = AgentRunOutcome(
        run_id=run_id, steps_used=2, max_steps=5, capped=False,
        timed_out=False, steps=(step,),
    )
    events = await _run_kb_edit_sse(
        monkeypatch, outcome, citations=[], can_adopt=False,
        path_kb_id=path_kb_id, draft_kb_id=path_kb_id,
    )
    names = _names(events)
    assert "approval_required" not in names
    assert "refusal" in names
    assert names[-1] == "done"
    refusal = _first(events, "refusal")
    assert refusal["reason"] == "no_source"


# --------------------------------------------------------------------------- #
# can_adopt 权限信号（H4-1-B · HA-2-A）
# --------------------------------------------------------------------------- #


class _User:
    def __init__(self, *, user_id: UUID, is_owner: bool = False,
                 org_role: OrgRole = OrgRole.member) -> None:
        self.id = user_id
        self.is_owner = is_owner
        self.org_role = org_role


class _KB:
    def __init__(self, *, owner_user_id: UUID | None = None,
                 owner_org_id: UUID | None = None,
                 kb_id: UUID | None = None) -> None:
        self.id = kb_id if kb_id is not None else uuid.uuid4()
        self.owner_user_id = owner_user_id
        self.owner_org_id = owner_org_id


class _OrgScope:
    def __init__(self, writable: bool) -> None:
        self._writable = writable

    def is_kb_writable(self, kb_id: UUID) -> bool:  # noqa: ARG002 - 测试桩
        return self._writable


def _admin(user_id: UUID) -> _User:
    return _User(user_id=user_id, is_owner=True)


def _member(user_id: UUID) -> _User:
    return _User(user_id=user_id, org_role=OrgRole.member)


def test_can_user_adopt_kb_personal_owner() -> None:
    uid = uuid.uuid4()
    kb = _KB(owner_user_id=uid)
    assert can_user_adopt_kb(_admin(uid), kb, None) is True
    # 个人库 owner 即便角色是普通成员也可采纳（库归属优先）
    assert can_user_adopt_kb(_member(uid), kb, None) is True


def test_can_user_adopt_kb_personal_not_owner() -> None:
    uid = uuid.uuid4()
    other = uuid.uuid4()
    kb = _KB(owner_user_id=other)
    assert can_user_adopt_kb(_admin(uid), kb, None) is False


def test_can_user_adopt_kb_org_admin_writable() -> None:
    uid = uuid.uuid4()
    kb_id = uuid.uuid4()
    kb = _KB(owner_org_id=uuid.uuid4())
    assert can_user_adopt_kb(_admin(uid), kb, _OrgScope(writable=True)) is True


def test_can_user_adopt_kb_org_admin_not_writable() -> None:
    uid = uuid.uuid4()
    kb = _KB(owner_org_id=uuid.uuid4())
    # 组织库 Admin 但对该 kb 无 write → 不可采纳（G4-4.1 须 kb write）
    assert can_user_adopt_kb(_admin(uid), kb, _OrgScope(writable=False)) is False


def test_can_user_adopt_kb_org_member_never() -> None:
    uid = uuid.uuid4()
    kb = _KB(owner_org_id=uuid.uuid4())
    # Member 即使有 write grant 也永不可采纳（HA-2-A）
    assert can_user_adopt_kb(_member(uid), kb, _OrgScope(writable=True)) is False
    assert can_user_adopt_kb(_member(uid), kb, _OrgScope(writable=False)) is False


def test_can_user_adopt_in_workspace_personal() -> None:
    uid = uuid.uuid4()
    ws = WorkspaceScope(kind=WorkspaceKind.personal, user_id=uid, org_id=None)
    assert can_user_adopt_in_workspace(_member(uid), ws) is True


def test_can_user_adopt_in_workspace_org_admin() -> None:
    uid = uuid.uuid4()
    ws = WorkspaceScope(kind=WorkspaceKind.organization, user_id=uid, org_id=uuid.uuid4())
    assert can_user_adopt_in_workspace(_admin(uid), ws) is True


def test_can_user_adopt_in_workspace_org_member() -> None:
    uid = uuid.uuid4()
    ws = WorkspaceScope(kind=WorkspaceKind.organization, user_id=uid, org_id=uuid.uuid4())
    # 组织工作区 Member → 不可采纳（HA-2-A）
    assert can_user_adopt_in_workspace(_member(uid), ws) is False
