"""L3-W7：Critic → 定向再检索（限预算 · 默认关）。"""

from __future__ import annotations

import uuid
from app.core.config import settings
from app.services.agent.planners import (
    CRITIC_RETRIEVAL_MAX,
    plan_critic_directed_retrieval,
)
from app.services.agent.types import AgentActionKind
from app.services.rag.critic import (
    METHOD_RULES_V1,
    METHOD_SKIPPED,
    ClaimCheck,
    CriticResult,
    CriticRetrievalGap,
    build_critic_retrieval_gap,
    critique_answer_rules,
)
from app.services.rag.feedback_attribution import LABEL_GENERATION_BAD, LABEL_UNKNOWN
from app.services.rag.types import RetrievedChunk


def test_critic_retrieval_flags_default_false() -> None:
    assert settings.rag_critic_enabled is False
    assert settings.agent_l3_critic_retrieval_enabled is False
    assert settings.agent_l3_next_action_enabled is False
    assert CRITIC_RETRIEVAL_MAX == 1


def _chunk(content: str) -> RetrievedChunk:
    return RetrievedChunk(
        kb_id=uuid.uuid4(),
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        doc_name="制度.md",
        content=content,
        page_number=1,
        section_title="住宿",
        heading_path="住宿",
        similarity=0.9,
    )


def test_build_gap_from_failed_claims_is_executable() -> None:
    chunks = [_chunk("员工住宿标准上限为 800 元/晚。")]
    result = critique_answer_rules(
        "总经理也必须遵守 800 元上限[片段1]。",
        chunks,
    )
    # 浅层证据可能 ok；强制构造失败 claim
    if result.ok:
        result = CriticResult(
            ok=False,
            claims=(
                ClaimCheck(
                    text="总经理也必须遵守 800 元上限[片段1]。",
                    citation_nums=(1,),
                    ok=False,
                    issue="shallow evidence overlap insufficient",
                ),
            ),
            label=LABEL_GENERATION_BAD,
            rationale="shallow",
            method=METHOD_RULES_V1,
        )
    gap = build_critic_retrieval_gap(
        result, original_query="总经理住宿标准有例外吗？"
    )
    assert gap is not None
    payload = gap.to_dict()
    assert payload["supported"] is False
    assert payload["unsupported_claims"]
    assert payload["suggested_query"]
    assert "总经理" in payload["suggested_query"] or "800" in payload["suggested_query"]


def test_build_gap_skipped_or_ok_returns_none() -> None:
    skipped = CriticResult(
        ok=True,
        claims=(),
        label=LABEL_UNKNOWN,
        rationale="off",
        method=METHOD_SKIPPED,
    )
    assert build_critic_retrieval_gap(skipped) is None
    ok = CriticResult(
        ok=True,
        claims=(),
        label=LABEL_UNKNOWN,
        rationale="ok",
        method=METHOD_RULES_V1,
    )
    assert build_critic_retrieval_gap(ok) is None


def test_plan_flag_off_returns_none() -> None:
    gap = CriticRetrievalGap(
        unsupported_claims=("总经理也必须遵守 800 元上限",),
        missing_facts=("高管住宿例外",),
        suggested_query="住宿标准 高管 总经理 例外",
    )
    assert settings.agent_l3_critic_retrieval_enabled is False
    assert (
        plan_critic_directed_retrieval(gap, steps_used=1, max_steps=5) is None
    )


def test_plan_enabled_returns_semantic_search() -> None:
    gap = CriticRetrievalGap(
        unsupported_claims=("总经理也必须遵守 800 元上限",),
        missing_facts=("高管住宿例外",),
        suggested_query="住宿标准 高管 总经理 例外",
    )
    kb = uuid.uuid4()
    decision = plan_critic_directed_retrieval(
        gap,
        steps_used=2,
        max_steps=5,
        default_kb_id=kb,
        enabled=True,
    )
    assert decision is not None
    assert decision.action == AgentActionKind.tool
    assert decision.tool_name == "semantic_search"
    assert decision.reason_code == "critic_directed_retrieve"
    assert decision.args["query"] == "住宿标准 高管 总经理 例外"
    assert decision.args["kb_ids"] == [str(kb)]


def test_plan_budget_exhausted_returns_none() -> None:
    gap = CriticRetrievalGap(
        unsupported_claims=("x",),
        missing_facts=("x",),
        suggested_query="住宿 例外",
    )
    assert (
        plan_critic_directed_retrieval(
            gap, steps_used=5, max_steps=5, enabled=True
        )
        is None
    )
    assert (
        plan_critic_directed_retrieval(
            gap, steps_used=1, max_steps=5, already_used=1, enabled=True
        )
        is None
    )
