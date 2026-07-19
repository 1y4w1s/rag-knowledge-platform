"""G4-2.1 · 编辑模式 Planner：只读步 + 末步 generate_faq_draft（≤3 步）· 无 adopt tool。

纯逻辑单测（不接 runtime / 不落库 / 不发射 SSE）：直接驱动
EditFaqDraftPlanner.next_tool_call，校验步骤序列形态与 generate_faq_draft 入参推导。

验收锚点：
- planner 产出合理步骤序列（只读步 + generate_faq_draft）
- 绝不把 adopt_draft_to_kb 暴露给模型
- 步骤数 ≤ 3
- 不破坏 pytest 基线（本文件不依赖 DB fixture）
"""

from __future__ import annotations

import uuid

import pytest

from app.services.agent.dispatch import create_edit_tool_planner
from app.services.agent.tools.registry import AgentToolName, ReadOnlyToolName
from app.services.agent.tools.semantic_search import (
    SemanticSearchHit,
    SemanticSearchOutput,
)
from app.services.agent.types import AgentStepRecord, ToolCallPlan

ADOPT_TOOL = "adopt_draft_to_kb"  # G4-2.1 红线：绝不允许出现


def _hit(kb_id: uuid.UUID, *, score: float = 0.9) -> SemanticSearchHit:
    return SemanticSearchHit(
        chunk_id=uuid.uuid4(),
        kb_id=kb_id,
        kb_name="制度库",
        doc_name="员工手册.md",
        page=1,
        section_title="1.1 年假",
        excerpt="员工年假规定为 10 天",
        score=score,
    )


async def _collect(
    planner,
    *,
    max_steps: int = 5,
    hits: tuple[SemanticSearchHit, ...] = (),
) -> list[ToolCallPlan]:
    """重放 next_tool_call，用模拟 prior_steps 驱动 draft 入参推导。"""
    plans: list[ToolCallPlan] = []
    prior: list[AgentStepRecord] = []
    steps_used = 0
    # 多跑一两次以确认 planner 在终态后返回 None
    for step_index in range(1, max_steps + 3):
        plan = await planner.next_tool_call(
            query="",
            step_index=step_index,
            steps_used=steps_used,
            max_steps=max_steps,
            prior_steps=tuple(prior),
        )
        if plan is None:
            break
        plans.append(plan)
        data = (
            SemanticSearchOutput(hits=hits, retrieval_ms=1)
            if plan.tool_name == ReadOnlyToolName.semantic_search.value
            else None
        )
        prior.append(
            AgentStepRecord(
                step_index=step_index,
                tool_name=plan.tool_name,
                args=plan.args,
                ok=True,
                summary="ok",
                latency_ms=1,
                step_id=uuid.uuid4(),
                data=data,
            )
        )
        steps_used = step_index
    return plans


def _tool_names(plans: list[ToolCallPlan]) -> list[str]:
    return [p.tool_name for p in plans]


@pytest.mark.asyncio
async def test_edit_planner_kb_internal_sequence_and_args() -> None:
    """库内 edit：semantic_search(kb_ids) + (excerpt) + generate_faq_draft；入参正确。"""
    default_kb = uuid.uuid4()
    hits = (_hit(default_kb, score=0.95), _hit(default_kb, score=0.80))
    planner = create_edit_tool_planner("年假制度 FAQ", default_kb_id=default_kb)

    plans = await _collect(planner, hits=hits)

    names = _tool_names(plans)
    assert names[0] == ReadOnlyToolName.semantic_search.value
    assert names[-1] == AgentToolName.generate_faq_draft.value
    assert ADOPT_TOOL not in names
    assert len(plans) <= 3

    # 末步 generate_faq_draft 入参推导
    draft = plans[-1].args
    assert draft["kb_id"] == str(default_kb)  # 库内 edit 强制路径 kb（G4-E19）
    assert draft["filename"].endswith(".md")
    assert set(draft["source_chunk_ids"]) == {str(h.chunk_id) for h in hits}
    assert draft["title"]

    # 首步 semantic_search 带 kb_ids
    assert plans[0].args.get("kb_ids") == [str(default_kb)]
    assert plans[0].args.get("query") == "年假制度 FAQ"


@pytest.mark.asyncio
async def test_edit_planner_ask_mode_derives_kb_from_hits() -> None:
    """/ask 跨库 edit（无 default）：目标库取首个命中库（搜索已 enforce visible）。"""
    target_kb = uuid.uuid4()
    hits = (_hit(target_kb, score=0.9),)
    planner = create_edit_tool_planner("年假怎么请", default_kb_id=None)

    plans = await _collect(planner, hits=hits)

    names = _tool_names(plans)
    assert names[0] == ReadOnlyToolName.semantic_search.value
    assert names[-1] == AgentToolName.generate_faq_draft.value
    assert ADOPT_TOOL not in names
    assert plans[-1].args["kb_id"] == str(target_kb)


@pytest.mark.asyncio
async def test_edit_planner_no_hits_still_emits_draft() -> None:
    """全无命中（G4-E11）：仍产 search + draft；draft source_chunk_ids 空 → tool 拒答。"""
    planner = create_edit_tool_planner("不存在的主题", default_kb_id=None)

    plans = await _collect(planner, hits=())

    names = _tool_names(plans)
    assert names[0] == ReadOnlyToolName.semantic_search.value
    assert names[-1] == AgentToolName.generate_faq_draft.value
    assert ADOPT_TOOL not in names
    assert len(plans) <= 3
    assert plans[-1].args["source_chunk_ids"] == []
    # 无命中且无 default → kb_id 为 None，tool 走 deny/拒答路径
    assert plans[-1].args["kb_id"] is None


@pytest.mark.asyncio
async def test_edit_planner_excerpt_step_when_budget_allows() -> None:
    """预算充足且命中存在 → 3 步：semantic_search + get_chunk_excerpt + generate_faq_draft。"""
    default_kb = uuid.uuid4()
    hits = (_hit(default_kb, score=0.9),)
    planner = create_edit_tool_planner("年假 FAQ", default_kb_id=default_kb)

    plans = await _collect(planner, max_steps=5, hits=hits)

    names = _tool_names(plans)
    assert names == [
        ReadOnlyToolName.semantic_search.value,
        ReadOnlyToolName.get_chunk_excerpt.value,
        AgentToolName.generate_faq_draft.value,
    ]
    assert ADOPT_TOOL not in names
    assert len(plans) == 3
    # excerpt 取最相关片段
    assert plans[1].args["chunk_id"] == str(hits[0].chunk_id)


@pytest.mark.asyncio
async def test_edit_planner_respects_max_steps_two() -> None:
    """max_steps=2 → 跳过 enrichment，仅 2 步：semantic_search + generate_faq_draft。"""
    default_kb = uuid.uuid4()
    hits = (_hit(default_kb, score=0.9),)
    planner = create_edit_tool_planner("年假 FAQ", default_kb_id=default_kb)

    plans = await _collect(planner, max_steps=2, hits=hits)

    names = _tool_names(plans)
    assert names == [
        ReadOnlyToolName.semantic_search.value,
        AgentToolName.generate_faq_draft.value,
    ]
    assert ADOPT_TOOL not in names
    assert len(plans) == 2


@pytest.mark.asyncio
async def test_edit_planner_never_exposes_adopt_tool() -> None:
    """跨场景断言：任何步骤都不出现 adopt_draft_to_kb（服务端写 · 非模型调用）。"""
    scenarios = [
        ("kb-internal+hits", uuid.uuid4(), (_hit(uuid.uuid4()),), 5),
        ("ask+hits", None, (_hit(uuid.uuid4()),), 5),
        ("ask+no-hits", None, (), 5),
        ("kb-internal+max2", uuid.uuid4(), (_hit(uuid.uuid4()),), 2),
    ]
    for _label, default_kb, hits, max_steps in scenarios:
        planner = create_edit_tool_planner("主题", default_kb_id=default_kb)
        plans = await _collect(planner, max_steps=max_steps, hits=hits)
        assert ADOPT_TOOL not in _tool_names(plans)
        # 有且仅有末步为写·待审 tool
        write_tools = [
            p.tool_name
            for p in plans
            if p.tool_name == AgentToolName.generate_faq_draft.value
        ]
        assert write_tools == [AgentToolName.generate_faq_draft.value]


@pytest.mark.asyncio
async def test_edit_planner_factory_returns_planner() -> None:
    """工厂返回可驱动实例，首步即 semantic_search。"""
    planner = create_edit_tool_planner("年假", default_kb_id=uuid.uuid4())
    plans = await _collect(planner, hits=(_hit(uuid.uuid4()),))
    assert plans[0].tool_name == ReadOnlyToolName.semantic_search.value
    assert plans[-1].tool_name == AgentToolName.generate_faq_draft.value
