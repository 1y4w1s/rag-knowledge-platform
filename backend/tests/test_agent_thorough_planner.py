"""D1 · ThoroughReadPlanner：有命中 ≥2 有用 tool；无命中 1 步结束。"""

from __future__ import annotations

import uuid

import pytest

from app.core.config import settings
from app.services.agent.dispatch import create_tool_planner
from app.services.agent.planners import (
    SemanticSearchPlanner,
    ThoroughReadPlanner,
    is_complex_query,
    refine_query,
)
from app.services.agent.tools.get_chunk_excerpt import GetChunkExcerptOutput
from app.services.agent.tools.registry import ReadOnlyToolName
from app.services.agent.tools.semantic_search import (
    SemanticSearchHit,
    SemanticSearchOutput,
)
from app.services.agent.types import AgentStepRecord, ToolCallPlan


@pytest.fixture(autouse=True)
def _disable_llm_planner() -> None:
    """存量测试依赖 create_tool_planner 返回 ThoroughReadPlanner；
    LLMPlanner 启用后会走 LLM 调用导致不确定行为。关闭开关以保持向后兼容。"""
    settings.agent_llm_planner_enabled = False

USEFUL = {
    ReadOnlyToolName.semantic_search.value,
    ReadOnlyToolName.get_chunk_excerpt.value,
}


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
    planner: ThoroughReadPlanner | SemanticSearchPlanner,
    *,
    max_steps: int = 5,
    hits: tuple[SemanticSearchHit, ...] = (),
    second_hits: tuple[SemanticSearchHit, ...] | None = None,
) -> list[ToolCallPlan]:
    plans: list[ToolCallPlan] = []
    prior: list[AgentStepRecord] = []
    steps_used = 0
    search_count = 0
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
        data = None
        ok = True
        if plan.tool_name == ReadOnlyToolName.semantic_search.value:
            search_count += 1
            use_hits = (
                hits
                if search_count == 1
                else (second_hits if second_hits is not None else hits)
            )
            data = SemanticSearchOutput(hits=use_hits, retrieval_ms=1)
        elif plan.tool_name == ReadOnlyToolName.get_chunk_excerpt.value:
            cid = uuid.UUID(str(plan.args["chunk_id"]))
            data = GetChunkExcerptOutput(
                chunk_id=cid,
                document_id=uuid.uuid4(),
                doc_name="员工手册.md",
                page=1,
                section_title="1.1 年假",
                excerpt="员工年假规定为 10 天",
                kb_id=uuid.uuid4(),
                kb_name="制度库",
            )
        prior.append(
            AgentStepRecord(
                step_index=step_index,
                tool_name=plan.tool_name,
                args=plan.args,
                ok=ok,
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
async def test_thorough_standard_with_hits_at_least_two_useful_tools() -> None:
    """非简单有命中：≥2 有用 tool（D2 · 简单档允许 1 步）。"""
    kb = uuid.uuid4()
    hits = (_hit(kb, score=0.95),)
    q = (
        "根据公司员工手册第二章关于考勤与休假的规定，"
        "入职满一年的正式员工年假额度是多少天？"
    )
    planner = create_tool_planner(q)
    plans = await _collect(planner, hits=hits)
    names = _tool_names(plans)
    assert names[0] == ReadOnlyToolName.semantic_search.value
    assert names[1] == ReadOnlyToolName.get_chunk_excerpt.value
    assert len(plans) >= 2
    assert all(n in USEFUL for n in names)
    assert plans[1].args["chunk_id"] == str(hits[0].chunk_id)


@pytest.mark.asyncio
async def test_thorough_simple_with_hits_one_step() -> None:
    kb = uuid.uuid4()
    planner = create_tool_planner("员工年假有几天？")
    plans = await _collect(planner, hits=(_hit(kb),))
    assert _tool_names(plans) == [ReadOnlyToolName.semantic_search.value]


@pytest.mark.asyncio
async def test_thorough_no_hits_stops_after_one_search() -> None:
    planner = create_tool_planner("火星殖民计划")
    plans = await _collect(planner, hits=())
    assert _tool_names(plans) == [ReadOnlyToolName.semantic_search.value]


@pytest.mark.asyncio
async def test_thorough_kb_passes_default_kb_ids() -> None:
    kb = uuid.uuid4()
    planner = create_tool_planner("年假几天", default_kb_id=kb)
    plans = await _collect(planner, hits=(_hit(kb),))
    assert plans[0].args.get("kb_ids") == [str(kb)]


@pytest.mark.asyncio
async def test_thorough_complex_adds_refined_second_search() -> None:
    kb = uuid.uuid4()
    q = (
        "员工小王入职满一年后申请年假10天，但他在申请年假前一周刚请了3天事假。"
        "请问根据手册，他申请年假需要提前多久？事假是否会影响年假申请？"
    )
    assert is_complex_query(q)
    focus = refine_query(q)
    assert focus is not None

    planner = create_tool_planner(q, default_kb_id=kb)
    plans = await _collect(
        planner,
        hits=(_hit(kb, score=0.9), _hit(kb, score=0.7)),
        second_hits=(_hit(kb, score=0.85),),
    )
    names = _tool_names(plans)
    assert names == [
        ReadOnlyToolName.semantic_search.value,
        ReadOnlyToolName.get_chunk_excerpt.value,
        ReadOnlyToolName.semantic_search.value,
    ]
    assert plans[2].args["query"] == focus
    assert all(n in USEFUL for n in names)


@pytest.mark.asyncio
async def test_legacy_one_step_planner_contrast() -> None:
    """对照：旧 SemanticSearchPlanner 仍一步停（生产已不用）。"""
    planner = SemanticSearchPlanner("年假几天")
    plans = await _collect(planner, hits=(_hit(uuid.uuid4()),))
    assert len(plans) == 1
    assert plans[0].tool_name == ReadOnlyToolName.semantic_search.value


def test_refine_query_strips_persona() -> None:
    q = "员工小李离职后竞业限制期为12个月。请问根据手册，他是否有权要求补偿？"
    focus = refine_query(q)
    assert focus is not None
    assert "小李" not in focus
    assert "补偿" in focus or "竞业" in focus or "有权" in focus


def test_factory_returns_thorough_planner() -> None:
    assert isinstance(create_tool_planner("q"), ThoroughReadPlanner)
