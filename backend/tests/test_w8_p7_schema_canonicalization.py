"""W8 P7 P1 Product Schema Canonicalization — Gate H A2 safety matrix (product parser)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import pytest

from app.eval.schema_ablation.candidates import (
    classify_hard_negative_accept,
    evaluate_strict,
)
from app.eval.schema_ablation.dataset import (
    build_hard_negatives,
    load_target_failures,
    load_valid_passthrough,
)
from app.eval.schema_ablation.models import CandidateOutcome
from app.eval.schema_ablation.tool_inventory import frozen_tool_inventory
from app.services.agent.planners import (
    INDEPENDENT_TOOL_SPECS,
    NextActionPlanner,
    SafetyFrame,
    parse_agent_decision,
)
from app.services.agent.types import AgentActionKind, AgentDecision, ObservationSummary


def _decision_to_dict(decision: AgentDecision | None) -> dict[str, Any] | None:
    if decision is None:
        return None
    return {
        "action": decision.action.value,
        "tool_name": decision.tool_name,
        "args": dict(decision.args or {}),
        "reason_code": decision.reason_code,
        "user_message": decision.user_message,
    }


def _decisions_preserved(
    strict: CandidateOutcome,
    product: CandidateOutcome,
) -> bool:
    if not strict.parse_ok or not product.parse_ok:
        return False
    return strict.decision == product.decision and not product.repair_applied


def _product_outcome(
    raw: str,
    *,
    exposed_tool_names: frozenset[str],
) -> CandidateOutcome:
    parsed = parse_agent_decision(raw, exposed_tool_names=exposed_tool_names)
    decision = _decision_to_dict(parsed.decision)
    return CandidateOutcome(
        parse_ok=parsed.ok,
        error=parsed.error,
        decision=decision,
        repair_applied=parsed.canonicalization_applied,
        semantic_mutation=False,
        false_repair=False,
    )


@dataclass
class ProductCanonicalizationMetrics:
    frozen_target_recovered: int = 0
    frozen_target_total: int = 9
    valid_passthrough: int = 0
    valid_passthrough_total: int = 30
    false_accepts: int = 0
    conflict_accepted: int = 0
    unknown_accepted: int = 0
    out_of_scope_accepted: int = 0
    invalid_args_accepted: int = 0
    non_tool_mutated: int = 0
    malformed_json_repaired: int = 0
    hard_negative_count: int = 0
    rows: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "frozen_target_recovered": f"{self.frozen_target_recovered}/{self.frozen_target_total}",
            "valid_passthrough": f"{self.valid_passthrough}/{self.valid_passthrough_total}",
            "false_accepts": self.false_accepts,
            "conflict_accepted": self.conflict_accepted,
            "unknown_accepted": self.unknown_accepted,
            "out_of_scope_accepted": self.out_of_scope_accepted,
            "invalid_args_accepted": self.invalid_args_accepted,
            "non_tool_mutated": self.non_tool_mutated,
            "malformed_json_repaired": self.malformed_json_repaired,
            "hard_negative_count": self.hard_negative_count,
        }


def run_product_canonicalization_metrics() -> ProductCanonicalizationMetrics:
    inventory = frozen_tool_inventory(external_tools_enabled=False)
    exposed = inventory.allowed_tool_names
    metrics = ProductCanonicalizationMetrics(
        frozen_target_total=len(load_target_failures()),
        valid_passthrough_total=len(load_valid_passthrough()),
    )

    for sample in load_target_failures():
        strict = evaluate_strict(sample.raw_output)
        assert strict.parse_ok is False
        out = _product_outcome(sample.raw_output, exposed_tool_names=exposed)
        recovered = (
            out.parse_ok
            and out.repair_applied
            and out.decision is not None
            and out.decision.get("action") == "tool"
            and isinstance(out.decision.get("tool_name"), str)
        )
        if recovered:
            metrics.frozen_target_recovered += 1
        metrics.rows.append(
            {
                "sample_id": sample.sample_id,
                "kind": "target",
                "recovered": recovered,
                "canonicalization_applied": out.repair_applied,
            }
        )

    for sample in load_valid_passthrough():
        strict = evaluate_strict(sample.raw_output)
        out = _product_outcome(sample.raw_output, exposed_tool_names=exposed)
        preserved = _decisions_preserved(strict, out)
        if preserved:
            metrics.valid_passthrough += 1
        elif strict.parse_ok and (
            out.repair_applied
            or (out.parse_ok and out.decision != strict.decision)
        ):
            action = strict.decision.get("action") if strict.decision else None
            if action in ("finish", "clarify", "refuse"):
                metrics.non_tool_mutated += 1

    hard = build_hard_negatives()
    metrics.hard_negative_count = len(hard)
    for sample in hard:
        strict = evaluate_strict(sample.raw_output)
        out = _product_outcome(sample.raw_output, exposed_tool_names=exposed)
        dim = sample.failure_dimension or "unknown"
        counts = classify_hard_negative_accept(
            out,
            dimension=dim,
            inventory=inventory,
            strict_outcome=strict,
        )
        metrics.false_accepts += counts["false_repair"]
        metrics.conflict_accepted += counts["conflict_accept"]
        metrics.unknown_accepted += counts["unknown_tool_accept"]
        metrics.out_of_scope_accepted += counts["out_of_scope_tool_accept"]
        metrics.invalid_args_accepted += counts["invalid_arguments_accept"]
        if dim in {
            "finish_action",
            "clarify_action",
            "refuse_action",
            "duplicate_finish",
            "duplicate_clarify",
            "duplicate_refuse",
        }:
            if out.repair_applied or (
                strict.parse_ok
                and out.parse_ok
                and out.decision != strict.decision
            ):
                metrics.non_tool_mutated += 1
        if dim == "malformed_json" and out.repair_applied:
            metrics.malformed_json_repaired += 1
        if dim == "json_with_fence_valid_under_strict":
            if strict.parse_ok and out.parse_ok and (
                out.repair_applied or out.decision != strict.decision
            ):
                metrics.false_accepts += 1

    return metrics


def test_product_gate_h_a2_safety_matrix_metrics() -> None:
    metrics = run_product_canonicalization_metrics()
    payload = metrics.to_dict()
    assert metrics.frozen_target_recovered == metrics.frozen_target_total == 9
    assert metrics.valid_passthrough == metrics.valid_passthrough_total == 30
    assert metrics.false_accepts == 0
    assert metrics.conflict_accepted == 0
    assert metrics.unknown_accepted == 0
    assert metrics.out_of_scope_accepted == 0
    assert metrics.invalid_args_accepted == 0
    assert metrics.non_tool_mutated == 0
    assert metrics.malformed_json_repaired == 0
    assert payload["frozen_target_recovered"] == "9/9"
    assert payload["valid_passthrough"] == "30/30"
    assert payload["false_accepts"] == 0


@pytest.mark.parametrize("sample", load_target_failures(), ids=lambda s: s.sample_id)
def test_frozen_target_recovery(sample) -> None:  # noqa: ANN001
    inventory = frozen_tool_inventory(external_tools_enabled=False)
    strict = evaluate_strict(sample.raw_output)
    assert strict.parse_ok is False
    out = _product_outcome(
        sample.raw_output,
        exposed_tool_names=inventory.allowed_tool_names,
    )
    assert out.parse_ok is True
    assert out.repair_applied is True
    assert out.decision is not None
    assert out.decision["action"] == "tool"
    assert out.decision["tool_name"]


@pytest.mark.parametrize("sample", load_valid_passthrough(), ids=lambda s: s.sample_id)
def test_valid_passthrough_semantic_preservation(sample) -> None:  # noqa: ANN001
    inventory = frozen_tool_inventory(external_tools_enabled=False)
    strict = evaluate_strict(sample.raw_output)
    out = _product_outcome(
        sample.raw_output,
        exposed_tool_names=inventory.allowed_tool_names,
    )
    assert _decisions_preserved(strict, out)


def test_hard_negatives_zero_false_accepts() -> None:
    inventory = frozen_tool_inventory(external_tools_enabled=False)
    false_accepts = 0
    for sample in build_hard_negatives():
        strict = evaluate_strict(sample.raw_output)
        out = _product_outcome(
            sample.raw_output,
            exposed_tool_names=inventory.allowed_tool_names,
        )
        counts = classify_hard_negative_accept(
            out,
            dimension=sample.failure_dimension or "unknown",
            inventory=inventory,
            strict_outcome=strict,
        )
        false_accepts += counts["false_repair"]
    assert false_accepts == 0


def test_out_of_scope_global_tool_not_accepted_when_not_exposed() -> None:
    """grep_in_document exists globally but is not in step-0 exposed set."""
    inventory = frozen_tool_inventory(external_tools_enabled=False)
    exposed = inventory.allowed_tool_names
    assert "grep_in_document" not in exposed
    assert "grep_in_document" in inventory.all_agent_tool_names

    raw = json.dumps(
        {
            "action": "grep_in_document",
            "tool_name": "grep_in_document",
            "args": {"document_id": "d", "pattern": "p"},
        }
    )
    strict = parse_agent_decision(raw)
    assert strict.ok is False
    assert strict.error == "invalid_action"

    scoped = parse_agent_decision(raw, exposed_tool_names=exposed)
    assert scoped.ok is False
    assert scoped.canonicalization_applied is False
    assert scoped.error == "invalid_action"


def test_without_exposed_tool_names_legacy_behavior_unchanged() -> None:
    dup_raw = (
        '```json\n{"action":"search_documents","tool_name":"search_documents",'
        '"args":{"query":"x"},"reason_code":"initial_retrieval"}\n```'
    )
    assert parse_agent_decision(dup_raw).error == "invalid_action"

    missing_raw = json.dumps(
        {"action": "list_knowledge_bases", "reason_code": "initial_retrieval"}
    )
    assert parse_agent_decision(missing_raw).error == "invalid_action"


def test_canonicalize_then_reject_invalid_args() -> None:
    inventory = frozen_tool_inventory(external_tools_enabled=False)
    raw = json.dumps(
        {
            "action": "search_documents",
            "tool_name": "search_documents",
            "args": {},
        }
    )
    out = parse_agent_decision(raw, exposed_tool_names=inventory.allowed_tool_names)
    assert out.canonicalization_applied is True
    assert out.ok is False
    assert out.error == "invalid_args"


@pytest.mark.asyncio
async def test_next_action_planner_call_llm_applies_exposed_canonicalization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Real _call_llm path: LLM mock → parse with step tool_specs exposed set."""
    dup_raw = (
        '```json\n{"action":"search_documents","tool_name":"search_documents",'
        '"args":{"query":"schema recovery"},"reason_code":"initial_retrieval"}\n```'
    )
    tool_specs = [s for s in INDEPENDENT_TOOL_SPECS if s.name != "web_search"]
    exposed = frozenset(s.name for s in tool_specs)

    async def _fake_complete(_messages):  # noqa: ANN001
        return dup_raw, {}

    monkeypatch.setattr(
        "app.services.rag.chat_llm.has_available_chat_provider_key",
        lambda: True,
    )
    monkeypatch.setattr(
        "app.services.rag.chat_llm.complete_chat_with_usage",
        _fake_complete,
    )

    planner = NextActionPlanner(
        "schema recovery query",
        safety_frame=SafetyFrame("schema recovery query"),
        tool_specs=tool_specs,
    )
    summary = ObservationSummary(
        original_query="schema recovery query",
        active_query="schema recovery query",
        steps_used=0,
        max_steps=5,
    )
    result = await planner._call_llm(summary, tool_specs)

    assert result.ok is True
    assert result.canonicalization_applied is True
    assert result.decision is not None
    assert result.decision.action == AgentActionKind.tool
    assert result.decision.tool_name == "search_documents"
    assert result.decision.args == {"query": "schema recovery"}
    assert "search_documents" in exposed
