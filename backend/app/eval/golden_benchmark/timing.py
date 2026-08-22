"""Phase timing schema and aggregation for W8 P4 benchmark hygiene."""

from __future__ import annotations

import statistics
from dataclasses import asdict, dataclass, field
from typing import Any

TIMING_TOLERANCE_MS = 500.0  # harness overhead allowance


@dataclass(slots=True)
class CaseTiming:
    case_id: str
    category: str
    case_total_wall_ms: float
    setup_total_ms: float
    kb_create_ms: float
    fixture_select_ms: float
    ingest_total_ms: float
    memory_seed_ms: float
    thread_create_ms: float
    agent_execution_ms: float
    model_call_total_ms: float
    model_call_count: int
    retrieval_tool_overhead_ms: float | None = None
    entity_extraction: str = "SKIPPED_BY_BENCHMARK_PROTOCOL"
    entity_extraction_ms: float | None = None
    model_call_latencies_ms: list[float] = field(default_factory=list)
    task_success: bool | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["agent_non_model_overhead_ms"] = self.agent_non_model_overhead_ms
        return payload

    @property
    def agent_non_model_overhead_ms(self) -> float | None:
        if self.model_call_count == 0 and self.agent_execution_ms <= 0:
            return None
        overhead = self.agent_execution_ms - self.model_call_total_ms
        return round(max(0.0, overhead), 1)


def validate_timing_invariants(timing: CaseTiming) -> list[str]:
    """Return violation messages; empty list means invariants hold."""
    violations: list[str] = []
    if timing.case_total_wall_ms < 0 or timing.setup_total_ms < 0 or timing.agent_execution_ms < 0:
        violations.append("negative timing field")
    if timing.case_total_wall_ms + 0.01 < timing.setup_total_ms:
        violations.append("case_total_wall_ms < setup_total_ms")
    if timing.case_total_wall_ms + 0.01 < timing.agent_execution_ms:
        violations.append("case_total_wall_ms < agent_execution_ms")
    expected_sum = timing.setup_total_ms + timing.agent_execution_ms
    if timing.case_total_wall_ms + TIMING_TOLERANCE_MS < expected_sum:
        violations.append(
            f"case_total_wall_ms ({timing.case_total_wall_ms}) "
            f"< setup + agent_execution ({expected_sum}) - tolerance"
        )
    setup_parts = (
        timing.kb_create_ms
        + timing.fixture_select_ms
        + timing.ingest_total_ms
        + timing.memory_seed_ms
        + timing.thread_create_ms
    )
    if timing.setup_total_ms + TIMING_TOLERANCE_MS < setup_parts:
        violations.append("setup_total_ms < sum(setup phase parts)")
    return violations


def _percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return round(ordered[0], 1)
    k = (len(ordered) - 1) * p
    lo = int(k)
    hi = min(lo + 1, len(ordered) - 1)
    frac = k - lo
    return round(ordered[lo] * (1 - frac) + ordered[hi] * frac, 1)


def aggregate_timing_stats(timings: list[CaseTiming]) -> dict[str, Any]:
    wall = [t.case_total_wall_ms for t in timings]
    setup = [t.setup_total_ms for t in timings]
    kb = [t.kb_create_ms for t in timings]
    ingest = [t.ingest_total_ms for t in timings]
    agent = [t.agent_execution_ms for t in timings]
    call_per_case = [t.model_call_total_ms for t in timings]
    all_calls = [x for t in timings for x in t.model_call_latencies_ms]
    overhead = [t.agent_non_model_overhead_ms for t in timings if t.agent_non_model_overhead_ms is not None]

    return {
        "case_count": len(timings),
        "case_total_wall_ms": {
            "p50": _percentile(wall, 0.5),
            "p95": _percentile(wall, 0.95),
            "max": round(max(wall), 1) if wall else None,
            "mean": round(statistics.mean(wall), 1) if wall else None,
        },
        "setup_total_ms": {
            "p50": _percentile(setup, 0.5),
            "p95": _percentile(setup, 0.95),
            "max": round(max(setup), 1) if setup else None,
        },
        "kb_create_ms": {
            "p50": _percentile(kb, 0.5),
            "p95": _percentile(kb, 0.95),
            "max": round(max(kb), 1) if kb else None,
        },
        "ingest_total_ms": {
            "p50": _percentile(ingest, 0.5),
            "p95": _percentile(ingest, 0.95),
            "max": round(max(ingest), 1) if ingest else None,
        },
        "agent_execution_ms": {
            "p50": _percentile(agent, 0.5),
            "p95": _percentile(agent, 0.95),
            "max": round(max(agent), 1) if agent else None,
        },
        "model_call_total_ms_per_case": {
            "p50": _percentile(call_per_case, 0.5),
            "p95": _percentile(call_per_case, 0.95),
            "max": round(max(call_per_case), 1) if call_per_case else None,
        },
        "model_call_per_invocation_ms": {
            "p50": _percentile(all_calls, 0.5),
            "p95": _percentile(all_calls, 0.95),
            "max": round(max(all_calls), 1) if all_calls else None,
        },
        "agent_non_model_overhead_ms": {
            "p50": _percentile(overhead, 0.5) if overhead else None,
            "p95": _percentile(overhead, 0.95) if overhead else None,
            "max": round(max(overhead), 1) if overhead else None,
            "note": "agent_execution_ms - model_call_total_ms per case; sequential wall-clock, not nested.",
        },
        "entity_extraction": "SKIPPED_BY_BENCHMARK_PROTOCOL",
        "entity_extraction_ms": None,
    }
