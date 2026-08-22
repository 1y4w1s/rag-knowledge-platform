"""P1 migrated TOOL case contracts — sidecar manifest with lineage hashes."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from app.eval.tool_capability.args_validation import validate_tool_args
from app.eval.tool_capability.fixtures import ADAPT_FIXTURE_TRAJECTORIES
from app.eval.tool_capability.observation import observation_satisfies_contract
from app.eval.contract_validity.tool_contract import TOOL_CASE_BY_ID
from app.services.agent.tools.registry import READ_ONLY_TOOL_NAMES

MIGRATION_STATUS_MIGRATED = "MIGRATED_CURRENT_L3"
MIGRATION_STATUS_BLOCKED = "MIGRATION_BLOCKED"

_LEGACY_GOLDEN_PATH = (
    Path(__file__).resolve().parents[3] / "tests" / "golden_agent_qa.json"
)


@dataclass(frozen=True, slots=True)
class StageContractSpec:
    stage: str
    expected: str
    required_fields: tuple[str, ...] = ()
    acceptable_actions: tuple[str, ...] = ()
    tool_native_matcher: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        if not self.required_fields:
            payload.pop("required_fields")
        if not self.acceptable_actions:
            payload.pop("acceptable_actions")
        if not self.tool_native_matcher:
            payload.pop("tool_native_matcher")
        return payload


@dataclass(frozen=True, slots=True)
class SatisfiabilityProof:
    tool_in_l3_inventory: bool
    args_expressible: bool
    resolver_can_accept: bool
    observation_producible: bool
    safe_terminal_reachable: bool

    @property
    def proven(self) -> bool:
        return all(
            (
                self.tool_in_l3_inventory,
                self.args_expressible,
                self.resolver_can_accept,
                self.observation_producible,
                self.safe_terminal_reachable,
            )
        )

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["proven"] = self.proven
        return payload


@dataclass(frozen=True, slots=True)
class MigratedCaseContract:
    case_id: str
    legacy_classification: str
    migration_status: str
    current_runtime_intent: str
    expected_tool: str
    required_args_semantics: dict[str, str]
    resolver_expectation: str
    execution_expectation: str
    observation_contract: str
    post_observation_behavior: str
    safe_terminal_contract: str
    budget_expectation: str
    stages: tuple[StageContractSpec, ...]
    satisfiability: SatisfiabilityProof
    legacy_case_hash: str
    migration_contract_hash: str = field(repr=False, compare=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "legacy_classification": self.legacy_classification,
            "migration_status": self.migration_status,
            "current_runtime_intent": self.current_runtime_intent,
            "expected_tool": self.expected_tool,
            "required_args_semantics": self.required_args_semantics,
            "resolver_expectation": self.resolver_expectation,
            "execution_expectation": self.execution_expectation,
            "observation_contract": self.observation_contract,
            "post_observation_behavior": self.post_observation_behavior,
            "safe_terminal_contract": self.safe_terminal_contract,
            "budget_expectation": self.budget_expectation,
            "stages": [s.to_dict() for s in self.stages],
            "satisfiability": self.satisfiability.to_dict(),
            "legacy_case_hash": self.legacy_case_hash,
            "migration_contract_hash": self.migration_contract_hash,
        }


def _canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _hash_payload(payload: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _load_legacy_golden_case(case_id: str) -> dict[str, Any]:
    data = json.loads(_LEGACY_GOLDEN_PATH.read_text(encoding="utf-8"))
    for case in data["cases"]:
        if case["case_id"] == case_id:
            return {
                "case_id": case["case_id"],
                "category": case["category"],
                "query": case["query"],
                "expected_doc": case.get("expected_doc", "none"),
                "expected_chunk": case["expected_chunk"],
                "scope": case.get("scope", "kb"),
            }
    raise KeyError(f"golden case not found: {case_id}")


def legacy_case_hash(case_id: str) -> str:
    return _hash_payload(_load_legacy_golden_case(case_id))


def _stage_specs_for(case_id: str, expected_tool: str, *, optional_mode: str | None = None) -> tuple[StageContractSpec, ...]:
    if expected_tool == "search_documents":
        args_fields = ("query",) if optional_mode is None else ("query", "mode")
        obs_matcher = "total:int + items[].document_id + items[].filename + summary"
    else:
        args_fields = ()
        obs_matcher = "total:int + items[].kb_id + items[].name"

    return (
        StageContractSpec(
            stage="planner_tool_selected",
            expected=f"planner selects {expected_tool}",
        ),
        StageContractSpec(
            stage="tool_args_valid",
            expected="args satisfy current L3 tool schema",
            required_fields=args_fields,
        ),
        StageContractSpec(
            stage="tool_resolver_accepted",
            expected="ToolResolver accepts call in kb scope with injected workspace",
        ),
        StageContractSpec(
            stage="tool_execution_succeeded",
            expected="tool returns ok result without execution error",
        ),
        StageContractSpec(
            stage="expected_observation_present",
            expected="tool-native payload present (not legacy expected_chunk)",
            tool_native_matcher=obs_matcher,
        ),
        StageContractSpec(
            stage="post_observation_decision_valid",
            expected="finish/refuse/clarify after observation",
            acceptable_actions=("finish", "refuse", "clarify"),
        ),
        StageContractSpec(
            stage="safe_terminal",
            expected="finish/refuse/clarify with safe=True and budget not exhausted",
            acceptable_actions=("finish", "refuse", "clarify"),
        ),
    )


def _runtime_intent(case_id: str) -> str:
    golden = _load_legacy_golden_case(case_id)
    mapping = {
        "GQ-131": "Answer how to search documents across knowledge bases using search_documents",
        "GQ-132": "Answer how to list knowledge bases using list_knowledge_bases",
        "GQ-149": "Answer content-mode document search using search_documents with mode=content",
    }
    base = mapping[case_id]
    return f"{base} (query={golden['query']!r})"


def _prove_satisfiability(case_id: str, expected_tool: str) -> SatisfiabilityProof:
    trajectory = ADAPT_FIXTURE_TRAJECTORIES[case_id]
    tool_step = trajectory.steps[0]
    args_ok, _ = validate_tool_args(expected_tool, tool_step.tool_args)
    obs_ok, _ = observation_satisfies_contract(expected_tool, tool_step.observation)
    return SatisfiabilityProof(
        tool_in_l3_inventory=expected_tool in READ_ONLY_TOOL_NAMES,
        args_expressible=args_ok,
        resolver_can_accept=tool_step.resolver_accepted is True,
        observation_producible=obs_ok,
        safe_terminal_reachable=trajectory.safe and trajectory.terminal_action == "finish",
    )


def _build_contract(case_id: str) -> MigratedCaseContract:
    gate_record = TOOL_CASE_BY_ID[case_id]
    golden = _load_legacy_golden_case(case_id)
    trajectory = ADAPT_FIXTURE_TRAJECTORIES[case_id]
    expected_tool = trajectory.case.expected_tool
    optional_mode = trajectory.case.optional_mode

    if case_id == "GQ-149":
        required_args = {"query": "non-empty string", "mode": "content"}
    elif expected_tool == "search_documents":
        required_args = {"query": "non-empty string"}
    else:
        required_args = {"q": "optional filter string or null"}

    satisfiability = _prove_satisfiability(case_id, expected_tool)
    status = MIGRATION_STATUS_MIGRATED if satisfiability.proven else MIGRATION_STATUS_BLOCKED

    body_without_hash = {
        "case_id": case_id,
        "legacy_classification": gate_record.primary_contract_class.value,
        "legacy_expected_chunk": golden["expected_chunk"],
        "migration_status": status,
        "current_runtime_intent": _runtime_intent(case_id),
        "expected_tool": expected_tool,
        "required_args_semantics": required_args,
        "resolver_expectation": "ToolResolver accepts independent read-only tool in kb scope",
        "execution_expectation": "run_* returns ok=True with structured data payload",
        "observation_contract": (
            "search_documents: total + document_id + filename (+ summary); "
            "list_knowledge_bases: total + kb_id + name"
        ),
        "post_observation_behavior": "finish after usable observation (no premature re-tool loop)",
        "safe_terminal_contract": "terminal_action in finish|refuse|clarify, safe=True, budget_exhausted=False",
        "budget_expectation": "default agent step budget not exhausted",
        "stages": [s.to_dict() for s in _stage_specs_for(case_id, expected_tool, optional_mode=optional_mode)],
        "satisfiability": satisfiability.to_dict(),
        "legacy_case_hash": legacy_case_hash(case_id),
    }
    contract_hash = _hash_payload(body_without_hash)

    return MigratedCaseContract(
        case_id=case_id,
        legacy_classification=gate_record.primary_contract_class.value,
        migration_status=status,
        current_runtime_intent=_runtime_intent(case_id),
        expected_tool=expected_tool,
        required_args_semantics=required_args,
        resolver_expectation=body_without_hash["resolver_expectation"],
        execution_expectation=body_without_hash["execution_expectation"],
        observation_contract=body_without_hash["observation_contract"],
        post_observation_behavior=body_without_hash["post_observation_behavior"],
        safe_terminal_contract=body_without_hash["safe_terminal_contract"],
        budget_expectation=body_without_hash["budget_expectation"],
        stages=_stage_specs_for(case_id, expected_tool, optional_mode=optional_mode),
        satisfiability=satisfiability,
        legacy_case_hash=legacy_case_hash(case_id),
        migration_contract_hash=contract_hash,
    )


def build_migrated_contracts() -> tuple[MigratedCaseContract, ...]:
    return tuple(_build_contract(case_id) for case_id in ("GQ-131", "GQ-132", "GQ-149"))


MIGRATED_CASE_CONTRACTS: tuple[MigratedCaseContract, ...] = build_migrated_contracts()
MIGRATED_CASE_BY_ID: dict[str, MigratedCaseContract] = {c.case_id: c for c in MIGRATED_CASE_CONTRACTS}
MIGRATED_CASE_IDS: frozenset[str] = frozenset(MIGRATED_CASE_BY_ID)


def all_migrations_proven() -> bool:
    return all(c.satisfiability.proven for c in MIGRATED_CASE_CONTRACTS)
