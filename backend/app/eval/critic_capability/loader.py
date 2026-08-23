"""W9 critic fixture loader with physical oracle isolation and hash binding."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

_BACKEND_ROOT = Path(__file__).resolve().parents[3]
_FIXTURE_ROOT = _BACKEND_ROOT / "tests" / "fixtures" / "l4_critic"
_INPUT_PATH = _FIXTURE_ROOT / "w9-critic-cases.json"
_CONTRACT_PATH = _FIXTURE_ROOT / "w9-critic-capability-contract.json"


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"fixture root must be an object: {path}")
    return payload


def _fingerprint(value: Mapping[str, Any]) -> str:
    canonical = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def load_model_inputs(path: Path = _INPUT_PATH) -> tuple[dict[str, Any], ...]:
    """Load only model-visible inputs; oracle/status/action fields are forbidden."""
    payload = _load_json(path)
    cases = payload.get("cases")
    if not isinstance(cases, list):
        raise ValueError("model input fixture must contain cases[]")
    forbidden = {
        "expected_status",
        "expected_action",
        "oracle",
        "decision_owner",
        "reason_code",
        "in_capability_denominator",
    }

    def leaked_keys(value: Any) -> set[str]:
        if isinstance(value, dict):
            direct = forbidden.intersection(value)
            return direct.union(*(leaked_keys(item) for item in value.values()))
        if isinstance(value, list):
            return set().union(*(leaked_keys(item) for item in value))
        return set()

    loaded: list[dict[str, Any]] = []
    for case in cases:
        if not isinstance(case, dict):
            raise ValueError("each model input case must be an object")
        leaked = leaked_keys(case)
        if leaked:
            raise ValueError(f"oracle leakage in {case.get('case_id')}: {sorted(leaked)}")
        loaded.append(case)
    return tuple(loaded)


def load_contract(path: Path = _CONTRACT_PATH) -> dict[str, Any]:
    return _load_json(path)


def load_bound_suite() -> tuple[dict[str, Any], tuple[dict[str, Any], ...]]:
    contract = load_contract()
    inputs = load_model_inputs()
    by_id = {case["case_id"]: case for case in inputs}
    oracle = contract.get("oracle_cases")
    if not isinstance(oracle, list) or len(oracle) != len(by_id):
        raise ValueError("oracle/input case count mismatch")
    for expected in oracle:
        case_id = expected.get("case_id")
        if case_id not in by_id:
            raise ValueError(f"oracle case missing input: {case_id}")
        if expected.get("input_sha256") != _fingerprint(by_id[case_id]):
            raise ValueError(f"input fingerprint mismatch: {case_id}")
    return contract, inputs


def capability_valid_denominator() -> int:
    contract, _ = load_bound_suite()
    return sum(
        1 for case in contract["oracle_cases"] if case["in_capability_denominator"]
    )
