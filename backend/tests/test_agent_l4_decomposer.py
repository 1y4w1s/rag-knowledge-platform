"""L4-W2：Fact Decomposer 契约（deterministic + schema + mock LLM · 默认关）。"""

from __future__ import annotations

import json

import pytest

from app.core.config import settings
from app.services.agent.decomposer import (
    MAX_FACT_GOALS,
    MIN_FACT_GOALS,
    FactDecomposer,
    deterministic_decompose,
    normalize_fact_goals,
    parse_fact_goals_payload,
)
from app.services.agent.state import init_agent_state
from app.services.agent.types import FactGoal, FactKind, FactStatus


def test_l3_l4_and_critic_flags_remain_false() -> None:
    assert settings.rag_critic_enabled is False
    assert settings.agent_l3_next_action_enabled is False
    assert settings.agent_l3_dynamic_tools_enabled is False
    assert settings.agent_l3_evidence_state_enabled is False
    assert settings.agent_l3_trajectory_trace_enabled is False
    assert settings.agent_l3_critic_retrieval_enabled is False
    assert settings.agent_l4_fact_decomposition_enabled is False
    assert settings.agent_l4_evidence_matcher_enabled is False
    assert settings.agent_l4_contradiction_enabled is False
    assert settings.agent_l4_stop_policy_enabled is False
    assert settings.agent_l4_reflection_recovery_enabled is False
    assert settings.agent_l4_local_model_profile_enabled is False
    assert settings.agent_l4_multimodal_evidence_enabled is False


def test_deterministic_simple_yields_one_lookup() -> None:
    result = deterministic_decompose("Docker Compose 用途？", difficulty="simple")
    assert result.ok is True
    assert result.source == "deterministic"
    assert len(result.fact_goals) == 1
    assert result.fact_goals[0].kind == FactKind.lookup
    assert result.fact_goals[0].status == FactStatus.missing
    assert result.fact_goals[0].id == "F1"


def test_deterministic_complex_compare_and_kinds() -> None:
    query = (
        "根据 2025 与 2026 差旅制度，住宿标准发生了什么变化？"
        "台湾办公室员工去上海适用哪档？是否存在高管例外？"
    )
    result = deterministic_decompose(query, difficulty="complex")
    assert result.ok is True
    assert MIN_FACT_GOALS <= len(result.fact_goals) <= MAX_FACT_GOALS
    kinds = {g.kind for g in result.fact_goals}
    assert FactKind.compare in kinds
    assert FactKind.condition in kinds or FactKind.exception in kinds
    assert all(g.status == FactStatus.missing for g in result.fact_goals)


def test_deterministic_hard_cap_at_six() -> None:
    parts = [f"核验点{i}是什么？" for i in range(1, 10)]
    result = deterministic_decompose("；".join(parts), difficulty="complex")
    assert result.ok is True
    assert len(result.fact_goals) <= MAX_FACT_GOALS
    assert len(result.fact_goals) >= 1


def test_parse_schema_valid_json_string() -> None:
    raw = json.dumps(
        {
            "fact_goals": [
                {
                    "id": "F1",
                    "text": "找到 2025 住宿标准",
                    "kind": "compare",
                    "required": True,
                },
                {
                    "id": "F2",
                    "text": "找到 2026 住宿标准",
                    "kind": "compare",
                    "required": True,
                },
            ]
        },
        ensure_ascii=False,
    )
    result = parse_fact_goals_payload(raw)
    assert result.ok is True
    assert result.source == "schema"
    assert len(result.fact_goals) == 2
    assert result.fact_goals[0].kind == FactKind.compare


def test_parse_rejects_invalid_kind() -> None:
    result = parse_fact_goals_payload(
        [{"text": "x", "kind": "multi_hop"}],
    )
    assert result.ok is False
    assert result.error == "invalid_kind"


def test_parse_truncates_over_six() -> None:
    items = [{"text": f"事实{i}", "kind": "lookup"} for i in range(1, 9)]
    result = parse_fact_goals_payload({"fact_goals": items})
    assert result.ok is True
    assert len(result.fact_goals) == MAX_FACT_GOALS
    assert result.fact_goals[-1].id == "F6"


def test_normalize_simple_forces_one() -> None:
    goals = (
        FactGoal(id="A", text="一", kind=FactKind.lookup),
        FactGoal(id="B", text="二", kind=FactKind.verify),
    )
    result = normalize_fact_goals(goals, difficulty="simple")
    assert result.ok is True
    assert len(result.fact_goals) == 1
    assert result.fact_goals[0].id == "F1"


def test_output_feeds_init_agent_state_scheme_a() -> None:
    result = deterministic_decompose(
        "确认适用条件；检查高管例外",
        difficulty="complex",
    )
    assert result.ok is True
    state = init_agent_state(
        original_query="q",
        max_steps=5,
        fact_goals=result.fact_goals,
    )
    assert len(state.evidence.facts) == len(result.fact_goals)
    assert state.evidence.required_facts == tuple(
        g.text for g in result.fact_goals if g.required
    )
    assert state.evidence.missing_facts == state.evidence.required_facts
    assert state.evidence.covered_facts == ()


@pytest.mark.asyncio
async def test_fact_decomposer_disabled_by_default() -> None:
    assert settings.agent_l4_fact_decomposition_enabled is False
    decomposer = FactDecomposer()
    result = await decomposer.decompose("任意问题")
    assert result.ok is False
    assert result.error == "disabled"
    assert result.source == "disabled"
    assert result.fact_goals == ()


@pytest.mark.asyncio
async def test_fact_decomposer_mock_llm_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "agent_l4_fact_decomposition_enabled", True)

    async def fake_llm(_query: str) -> str:
        return json.dumps(
            {
                "fact_goals": [
                    {
                        "text": "核实引用是否一致",
                        "kind": "verify",
                        "required": True,
                    }
                ]
            },
            ensure_ascii=False,
        )

    decomposer = FactDecomposer(llm_complete=fake_llm)
    result = await decomposer.decompose("请核实")
    assert result.ok is True
    assert result.source == "llm"
    assert len(result.fact_goals) == 1
    assert result.fact_goals[0].kind == FactKind.verify
    # 测完后默认仍应为 False（monkeypatch 结束还原；此处再确认生产默认字段）
    monkeypatch.setattr(settings, "agent_l4_fact_decomposition_enabled", False)
    assert settings.agent_l4_fact_decomposition_enabled is False


@pytest.mark.asyncio
async def test_fact_decomposer_llm_parse_fail_falls_back_deterministic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "agent_l4_fact_decomposition_enabled", True)

    async def bad_llm(_query: str) -> str:
        return "not-json{{{ "

    decomposer = FactDecomposer(llm_complete=bad_llm)
    result = await decomposer.decompose("住宿标准是什么？", difficulty="simple")
    assert result.ok is True
    assert result.source == "deterministic"
    assert result.error == "parse_error"
    assert len(result.fact_goals) == 1
