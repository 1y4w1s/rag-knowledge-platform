"""D2 · ThoroughEntryPolicy：简单题不浪费步数；复杂仍多步。"""

from __future__ import annotations

import uuid

import pytest

from app.core.config import settings
from app.services.agent.planners import (
    QueryDepth,
    ThoroughReadPlanner,
    create_tool_planner,
    is_complex_query,
    query_depth,
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
    """存量测试依赖 create_tool_planner 返回 ThoroughReadPlanner。"""
    settings.agent_llm_planner_enabled = False

# 简单：有命中 → 仅 1 步 search
_SIMPLE_CASES = [
    "年假几天",
    "员工年假有几天？",
    "请问年假有几天？",
    "餐补多少？",
    "加班费怎么算？",
]

# 标准：长于简单阈值、无复杂特征 → search + excerpt
_STANDARD_QUERY = (
    "根据公司员工手册第二章关于考勤与休假的规定，"
    "入职满一年的正式员工年假额度是多少天？"
)

# 复杂：对比 / 多问点 → 可到第 3 步
_COMPLEX_QUERY = (
    "员工小王入职满一年后申请年假10天，但他在申请年假前一周刚请了3天事假。"
    "请问根据手册，他申请年假需要提前多久？事假是否会影响年假申请？"
)


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
    planner: ThoroughReadPlanner,
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
                ok=True,
                summary="ok",
                latency_ms=1,
                step_id=uuid.uuid4(),
                data=data,
            )
        )
        steps_used = step_index
    return plans


@pytest.mark.parametrize("q", _SIMPLE_CASES)
def test_query_depth_simple(q: str) -> None:
    assert query_depth(q) == QueryDepth.simple
    assert not is_complex_query(q)


def test_query_depth_standard_long_single_question() -> None:
    assert query_depth(_STANDARD_QUERY) == QueryDepth.standard
    assert not is_complex_query(_STANDARD_QUERY)


def test_query_depth_complex_multi_question() -> None:
    assert query_depth(_COMPLEX_QUERY) == QueryDepth.complex
    assert is_complex_query(_COMPLEX_QUERY)


def test_please_alone_does_not_force_complex() -> None:
    """「请问」单独不够升复杂（D2 收紧）。"""
    q = "请问年假有几天？"
    assert query_depth(q) == QueryDepth.simple
    assert not is_complex_query(q)


@pytest.mark.asyncio
@pytest.mark.parametrize("q", _SIMPLE_CASES)
async def test_simple_with_hits_one_search_only(q: str) -> None:
    kb = uuid.uuid4()
    planner = create_tool_planner(q)
    assert planner.depth == QueryDepth.simple
    plans = await _collect(planner, hits=(_hit(kb),))
    assert len(plans) == 1
    assert plans[0].tool_name == ReadOnlyToolName.semantic_search.value


@pytest.mark.asyncio
async def test_standard_with_hits_search_then_excerpt() -> None:
    kb = uuid.uuid4()
    hits = (_hit(kb, score=0.95),)
    planner = create_tool_planner(_STANDARD_QUERY)
    assert planner.depth == QueryDepth.standard
    plans = await _collect(planner, hits=hits)
    assert [p.tool_name for p in plans] == [
        ReadOnlyToolName.semantic_search.value,
        ReadOnlyToolName.get_chunk_excerpt.value,
    ]
    assert plans[1].args["chunk_id"] == str(hits[0].chunk_id)


@pytest.mark.asyncio
async def test_complex_with_hits_three_steps() -> None:
    kb = uuid.uuid4()
    planner = create_tool_planner(_COMPLEX_QUERY, default_kb_id=kb)
    assert planner.depth == QueryDepth.complex
    plans = await _collect(
        planner,
        hits=(_hit(kb, score=0.9),),
        second_hits=(_hit(kb, score=0.85),),
    )
    assert [p.tool_name for p in plans] == [
        ReadOnlyToolName.semantic_search.value,
        ReadOnlyToolName.get_chunk_excerpt.value,
        ReadOnlyToolName.semantic_search.value,
    ]


@pytest.mark.asyncio
async def test_simple_no_hits_still_one_search() -> None:
    planner = create_tool_planner("火星殖民计划")
    plans = await _collect(planner, hits=())
    assert len(plans) == 1
