"""W8 P7 Schema Remediation P0/P0b offline ablation — deterministic Gate H tests."""

from __future__ import annotations

import json
from pathlib import Path

from app.eval.schema_ablation.dataset import (
    TARGET_FIXTURE,
    build_hard_negatives,
    load_target_failures,
)
from app.eval.contract_validity.schema_baseline import schema_characterization_baseline
from app.eval.schema_ablation.candidates import (
    CandidateKind,
    apply_duplicate_consistent_canonicalization,
    apply_narrow_canonicalization,
    decode_llm_json,
    evaluate_candidate,
    evaluate_strict,
)
from app.eval.schema_ablation.models import (
    BASE_MASTER_SHA,
    PRE_REPAIR_PARSE_FAILURES,
    PRE_REPAIR_PLANNER_DECISIONS,
    PRE_REPAIR_TOOL_NAME_AS_ACTION,
    PARSER_CONTRACT_CHAIN,
    TOOL_NAME_AS_ACTION_FAILURE_LAYER,
)
from app.eval.schema_ablation.runner import build_schema_ablation_report, run_schema_ablation
from app.eval.schema_ablation.tool_inventory import frozen_tool_inventory
from app.services.agent.planners import parse_agent_decision


def test_frozen_gate_g_baseline_unchanged() -> None:
    baseline = schema_characterization_baseline()
    assert PRE_REPAIR_PLANNER_DECISIONS == 226
    assert PRE_REPAIR_PARSE_FAILURES == 9
    assert PRE_REPAIR_TOOL_NAME_AS_ACTION == 9
    assert baseline.failure_count == PRE_REPAIR_PARSE_FAILURES


def test_target_fixture_lineage_nine_cases() -> None:
    targets = load_target_failures()
    assert len(targets) == 9
    assert TARGET_FIXTURE.is_file()
    for sample in targets:
        assert sample.raw_output
        assert len(sample.raw_output_hash) == 64
        assert sample.source == "TARGET_FAILURE"
        strict = evaluate_strict(sample.raw_output)
        assert strict.parse_ok is False
        assert strict.error == "invalid_action"


def test_failure_shape_one_missing_eight_duplicate() -> None:
    report = run_schema_ablation()
    shape = report.dataset["failure_shape"]
    assert shape["missing_tool_name"] == 1
    assert shape["duplicate_consistent_tool_name"] == 8
    assert shape["conflicting_tool_name"] == 0


def test_strict_baseline_does_not_recover_targets() -> None:
    report = run_schema_ablation()
    assert report.strict.target_recovered_count == 0
    assert report.strict.target_failure_count == 9


def test_candidate_a1_only_exact_allowed_tool_without_tool_name() -> None:
    inventory = frozen_tool_inventory(external_tools_enabled=False)
    obj = {"action": "semantic_search", "args": {"query": "x"}, "reason_code": "t"}
    patched, applied = apply_narrow_canonicalization(obj, inventory)
    assert applied is True
    assert patched["action"] == "tool"
    assert patched["tool_name"] == "semantic_search"

    conflict = {
        "action": "semantic_search",
        "tool_name": "grep_in_document",
        "args": {"query": "x"},
    }
    _, applied_conflict = apply_narrow_canonicalization(conflict, inventory)
    assert applied_conflict is False

    duplicate = {
        "action": "search_documents",
        "tool_name": "search_documents",
        "args": {"query": "x"},
    }
    _, applied_dup = apply_narrow_canonicalization(duplicate, inventory)
    assert applied_dup is False


def test_a1_recovers_only_gq132_from_real_targets() -> None:
    report = run_schema_ablation()
    assert report.narrow.target_recovered_count == 1
    inventory = frozen_tool_inventory()
    targets = load_target_failures()
    gq132 = next(t for t in targets if t.case_id == "GQ-132")
    out132 = evaluate_candidate(
        gq132.raw_output, kind=CandidateKind.narrow, inventory=inventory
    )
    assert out132.parse_ok is True
    gq98 = next(t for t in targets if t.case_id == "GQ-98")
    out98 = evaluate_candidate(gq98.raw_output, kind=CandidateKind.narrow, inventory=inventory)
    assert out98.parse_ok is False


def test_a2_recovers_missing_tool_name_target() -> None:
    inventory = frozen_tool_inventory()
    targets = load_target_failures()
    gq132 = next(t for t in targets if t.case_id == "GQ-132")
    out = evaluate_candidate(
        gq132.raw_output,
        kind=CandidateKind.duplicate_consistent,
        inventory=inventory,
    )
    assert out.repair_applied is True
    assert out.parse_ok is True
    assert out.decision is not None
    assert out.decision["action"] == "tool"
    assert out.decision["tool_name"] == "list_knowledge_bases"


def test_a2_recovers_duplicate_consistent_target() -> None:
    inventory = frozen_tool_inventory()
    dup_raw = (
        '```json\n{"action":"search_documents","tool_name":"search_documents",'
        '"args":{"query":"x"},"reason_code":"initial_retrieval"}\n```'
    )
    out = evaluate_candidate(
        dup_raw,
        kind=CandidateKind.duplicate_consistent,
        inventory=inventory,
    )
    assert out.repair_applied is True
    assert out.parse_ok is True
    assert out.decision is not None
    assert out.decision["action"] == "tool"
    assert out.decision["tool_name"] == "search_documents"


def test_a2_recovers_all_nine_real_targets() -> None:
    report = run_schema_ablation()
    a2 = report.duplicate_consistent
    assert a2.target_recovered_count == 9
    assert a2.missing_tool_recovered_count == 1
    assert a2.duplicate_recovered_count == 8
    assert all(r.result == "RECOVERED" for r in report.target_failure_reports)


def test_a2_valid_passthrough_semantic_preservation() -> None:
    report = run_schema_ablation()
    a2 = report.duplicate_consistent
    assert a2.valid_passthrough_count >= 30
    assert a2.valid_passthrough_preserved == a2.valid_passthrough_count
    assert a2.valid_passthrough_rate == 1.0


def test_unknown_action_and_typo_not_repaired_by_a2() -> None:
    inventory = frozen_tool_inventory()
    for raw in (
        '{"action":"unknown_tool","args":{"query":"x"}}',
        '{"action":"semantic_seach","args":{"query":"x"}}',
        json.dumps(
            {"action": "unknown_tool", "tool_name": "unknown_tool", "args": {"query": "x"}},
        ),
        json.dumps(
            {"action": "semantic_seach", "tool_name": "semantic_seach", "args": {"query": "x"}},
        ),
    ):
        out = evaluate_candidate(
            raw,
            kind=CandidateKind.duplicate_consistent,
            inventory=inventory,
        )
        assert out.parse_ok is False
        assert out.repair_applied is False


def test_conflicting_tool_name_not_repaired_by_a2() -> None:
    inventory = frozen_tool_inventory()
    raw = json.dumps(
        {
            "action": "semantic_search",
            "tool_name": "grep_in_document",
            "args": {"query": "x"},
        }
    )
    out = evaluate_candidate(raw, kind=CandidateKind.duplicate_consistent, inventory=inventory)
    assert out.parse_ok is False
    assert out.repair_applied is False


def test_duplicate_invalid_args_canonicalized_but_rejected() -> None:
    inventory = frozen_tool_inventory()
    raw = json.dumps(
        {
            "action": "search_documents",
            "tool_name": "search_documents",
            "args": {},
        }
    )
    obj, _ = decode_llm_json(raw)
    assert obj is not None
    patched, applied = apply_duplicate_consistent_canonicalization(obj, inventory)
    assert applied is True
    assert patched["action"] == "tool"
    out = evaluate_candidate(
        raw,
        kind=CandidateKind.duplicate_consistent,
        inventory=inventory,
    )
    assert out.repair_applied is True
    assert out.parse_ok is False


def test_duplicate_wrong_arg_types_rejected_by_a2() -> None:
    inventory = frozen_tool_inventory()
    raw = json.dumps(
        {
            "action": "search_documents",
            "tool_name": "search_documents",
            "args": {"query": 0},
        }
    )
    out = evaluate_candidate(raw, kind=CandidateKind.duplicate_consistent, inventory=inventory)
    assert out.repair_applied is True
    assert out.parse_ok is False


def test_out_of_scope_duplicate_not_repaired_by_a2() -> None:
    inventory = frozen_tool_inventory()
    raw = json.dumps(
        {
            "action": "grep_in_document",
            "tool_name": "grep_in_document",
            "args": {"document_id": "d", "pattern": "p"},
        }
    )
    out = evaluate_candidate(raw, kind=CandidateKind.duplicate_consistent, inventory=inventory)
    assert out.parse_ok is False
    assert out.repair_applied is False


def test_malformed_json_still_fails_a2() -> None:
    inventory = frozen_tool_inventory()
    out = evaluate_candidate(
        "{not json",
        kind=CandidateKind.duplicate_consistent,
        inventory=inventory,
    )
    assert out.parse_ok is False
    assert out.repair_applied is False


def test_finish_clarify_refuse_unaffected_by_a2() -> None:
    inventory = frozen_tool_inventory()
    for raw in (
        '{"action":"finish","reason_code":"done"}',
        '{"action":"clarify","reason_code":"ambiguous","user_message":"?"}',
        '{"action":"refuse","reason_code":"unsupported"}',
        json.dumps({"action": "finish", "tool_name": "finish", "reason_code": "done"}),
        json.dumps(
            {
                "action": "clarify",
                "tool_name": "clarify",
                "reason_code": "ambiguous",
                "user_message": "?",
            },
        ),
        json.dumps({"action": "refuse", "tool_name": "refuse", "reason_code": "unsupported"}),
    ):
        strict = evaluate_strict(raw)
        a2 = evaluate_candidate(
            raw,
            kind=CandidateKind.duplicate_consistent,
            inventory=inventory,
            strict_baseline=strict,
        )
        assert strict.parse_ok is True
        assert a2.parse_ok is True
        assert a2.repair_applied is False
        assert a2.decision == strict.decision


def test_a2_only_mutates_action_and_tool_name_fields() -> None:
    inventory = frozen_tool_inventory()
    raw = json.dumps(
        {
            "action": "list_knowledge_bases",
            "reason_code": "initial_retrieval",
        }
    )
    obj, _ = decode_llm_json(raw)
    assert obj is not None
    patched, applied = apply_duplicate_consistent_canonicalization(obj, inventory)
    assert applied is True
    for key in ("reason_code", "args", "user_message"):
        assert patched.get(key) == obj.get(key)


def test_a2_zero_false_repair_on_hard_negatives() -> None:
    report = run_schema_ablation()
    a2 = report.duplicate_consistent
    assert a2.false_repair_count == 0
    assert a2.unknown_tool_accept_count == 0
    assert a2.conflict_accept_count == 0
    assert a2.out_of_scope_tool_accept_count == 0
    assert a2.invalid_arguments_accept_count == 0
    assert a2.non_tool_action_mutation_count == 0


def test_a1_zero_false_repair_on_hard_negatives() -> None:
    report = run_schema_ablation()
    assert report.narrow.false_repair_count == 0


def test_broad_control_high_recovery_but_unsafe() -> None:
    report = run_schema_ablation()
    assert report.broad.target_recovered_count == 9
    assert report.broad.false_repair_count >= 1


def test_parser_failure_layer_documented() -> None:
    assert "AgentActionKind" in TOOL_NAME_AS_ACTION_FAILURE_LAYER
    assert len(PARSER_CONTRACT_CHAIN) >= 8


def test_ablation_report_gate_h_pass_with_a2() -> None:
    payload = build_schema_ablation_report(
        repo_root=Path(__file__).resolve().parents[1]
    )
    assert payload["base_master_sha"] == BASE_MASTER_SHA
    assert payload["product_diff"] == 0
    assert payload["golden_diff"] == 0
    assert payload["raw_target_lineage"] == "VALID"
    assert payload["failure_shape"]["missing_tool_name"] == 1
    assert payload["failure_shape"]["duplicate_consistent_tool_name"] == 8
    assert payload["recommendation"]["recommended_fix"] == "DUPLICATE_CONSISTENT_CANONICALIZATION"
    assert payload["recommendation"]["status"] == "RECOMMENDED_FOR_PRODUCT_IMPLEMENTATION"
    assert payload["recommendation"]["safety"] == "PASS"
    assert payload["gate_h"]["gate_h"] == "PASS"
    assert payload["gate_h"]["w8_p7_p0b"] == "PASS"
    assert payload["gate_h"]["ready_for_schema_product_implementation"] is True
    assert payload["gate_h"]["ready_for_prompt_ablation"] is False
    a2 = payload["OFFLINE_A2_RESULT"]
    assert a2["target_recovered_count"] == 9
    assert a2["valid_passthrough_rate"] == 1.0
    assert a2["false_repair_count"] == 0


def test_hard_negative_count_at_least_thirty() -> None:
    assert len(build_hard_negatives()) >= 30


def test_p5_duplicate_tool_name_targets_fail_a1_but_recover_a2() -> None:
    inventory = frozen_tool_inventory()
    dup_raw = (
        '```json\n{"action":"search_documents","tool_name":"search_documents",'
        '"args":{"query":"x"},"reason_code":"initial_retrieval"}\n```'
    )
    a1 = evaluate_candidate(dup_raw, kind=CandidateKind.narrow, inventory=inventory)
    assert a1.repair_applied is False
    assert a1.parse_ok is False
    assert parse_agent_decision(dup_raw).error == "invalid_action"
    a2 = evaluate_candidate(
        dup_raw,
        kind=CandidateKind.duplicate_consistent,
        inventory=inventory,
    )
    assert a2.repair_applied is True
    assert a2.parse_ok is True
