"""Run one MEMORY P3 Golden case through product run_react_loop."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID, uuid4

from app.core.database import SessionLocal
from app.eval.local_agent_trajectory.injection import (
    RecordingAdapter,
    RoundCapture,
    TracingPlanner,
    patch_planner_llm,
    restore_planner_llm,
    wrap_stop_policy,
)
from app.eval.local_agent_trajectory.schema import utc_now_iso
from app.eval.memory_capability.c1_flags import apply_memory_c1_flags, restore_memory_c1_flags
from app.eval.memory_capability.proposition import analyze_utilization, seeds_equivalent
from app.eval.memory_capability.schema import MemorySeed, MemoryTrajectoryInput
from app.models.enums import AccountType
from app.models.knowledge_base import KnowledgeBase
from app.models.user import User
from app.services.agent.fact_contracts import fact_coverage_ratio
from app.services.agent.memory import format_memory_context, load_active_memories, upsert_memory
from app.services.agent.memory_exposure import (
    build_memory_exposure_records,
    clear_memory_exposure_events,
    get_memory_exposure_events,
)
from app.services.agent.runtime import run_react_loop
from app.services.agent.tools.scope import AgentToolScope
from app.services.agent.types import AgentActionKind, AgentRunOutcome, FactStatus
from app.services.auth.password import hash_password
from app.services.rag.thread_persistence import create_kb_thread
from app.services.workspace.scope import WorkspaceKind, WorkspaceScope
from tests.golden_agent_qa_loader import AgentGoldenCase


@dataclass(slots=True)
class MemoryP3TrialRecord:
    case_id: str
    trial_index: int
    condition: str  # WITH_MEMORY | WITHOUT_MEMORY | EMPTY_CONTROL
    query: str
    model_id: str
    thinking_mode: str
    started_at: str
    duration_ms: float
    run_id: str | None
    seed_succeeded: bool
    seeded_memories: list[dict[str, Any]]
    loaded_memories: list[dict[str, Any]]
    expected_memory_hashes: list[str]
    exposed_context: str
    exposure_events: list[dict[str, Any]]
    output_text: str
    tool_query: str | None
    outcome: dict[str, Any]
    captures: list[dict[str, Any]]
    trajectory_input: MemoryTrajectoryInput
    proposition_records: list[dict[str, Any]] = field(default_factory=list)
    privacy_hits: list[str] = field(default_factory=list)


def _seed_to_dict(seed: MemorySeed) -> dict[str, Any]:
    return seed.to_dict()


def _memory_row_to_seed(mem: Any) -> MemorySeed:
    value = mem.value
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            value = {"raw": value}
    if not isinstance(value, dict):
        value = {"value": value}
    return MemorySeed(key=str(mem.key), memory_type=str(mem.memory_type), value=value)


def _capture_dict(cap: RoundCapture) -> dict[str, Any]:
    d = cap.planner_decision
    return {
        "step_index": cap.step_index,
        "raw_excerpt": (cap.raw or "")[:2000],
        "parse_ok": cap.parse_ok,
        "parse_error": cap.parse_error,
        "parsed_action": cap.parsed_action,
        "parsed_tool": cap.parsed_tool,
        "parsed_args": dict(cap.parsed_args or {}),
        "planner_decision": {
            "action": d.action.value,
            "tool_name": d.tool_name,
            "args": dict(d.args or {}),
            "reason_code": d.reason_code,
        },
        "stop_effect": cap.stop_effect,
        "tool_name": cap.tool_name,
        "tool_args": dict(cap.tool_args or {}),
        "tool_success": cap.tool_success,
        "observation_summary": cap.observation_summary,
        "timed_out": cap.timed_out,
        "provider_error": cap.provider_error,
        "latency_ms": round(cap.latency_ms, 1),
    }


def _outcome_dict(outcome: AgentRunOutcome) -> dict[str, Any]:
    terminal = outcome.terminal_decision
    return {
        "run_id": str(outcome.run_id),
        "steps_used": outcome.steps_used,
        "max_steps": outcome.max_steps,
        "capped": outcome.capped,
        "timed_out": outcome.timed_out,
        "low_confidence": outcome.low_confidence,
        "terminal_action": terminal.action.value if terminal else None,
        "terminal_reason": terminal.reason_code if terminal else None,
        "steps": [
            {
                "step_index": s.step_index,
                "tool_name": s.tool_name,
                "args": dict(s.args or {}),
                "ok": s.ok,
                "summary": s.summary,
                "latency_ms": s.latency_ms,
            }
            for s in outcome.steps
        ],
    }


def _collect_output_text(outcome: AgentRunOutcome, captures: list[RoundCapture]) -> str:
    parts: list[str] = []
    for cap in captures:
        if cap.raw:
            parts.append(cap.raw)
        if cap.observation_summary:
            parts.append(cap.observation_summary)
        dec = cap.stop_after or cap.planner_decision
        if dec.user_message:
            parts.append(dec.user_message)
        if dec.args:
            parts.append(json.dumps(dec.args, ensure_ascii=False))
    for step in outcome.steps:
        if step.summary:
            parts.append(step.summary)
    terminal = outcome.terminal_decision
    if terminal is not None:
        if terminal.user_message:
            parts.append(terminal.user_message)
        if terminal.args:
            parts.append(json.dumps(terminal.args, ensure_ascii=False))
    return "\n".join(parts)


def _first_tool_query(outcome: AgentRunOutcome, captures: list[RoundCapture]) -> str | None:
    for cap in captures:
        dec = cap.stop_after or cap.planner_decision
        if dec.action == AgentActionKind.tool:
            q = (dec.args or {}).get("query")
            if isinstance(q, str) and q.strip():
                return q
    for step in outcome.steps:
        if step.tool_name:
            q = (step.args or {}).get("query")
            if isinstance(q, str) and q.strip():
                return q
    return None


def _privacy_scan(
    events: list[dict[str, Any]],
    *,
    seed_plaintext: list[str],
) -> list[str]:
    hits: list[str] = []
    banned_keys = ("value", "content", "summary", "plaintext", "memory_text", "prompt")
    for ev in events:
        for key in banned_keys:
            if key in ev:
                hits.append(f"banned_key:{key}")
        blob = json.dumps(ev, ensure_ascii=False)
        for plain in seed_plaintext:
            if plain and plain in blob:
                hits.append(f"plaintext_leak:{plain[:40]}")
    return sorted(set(hits))


def _no_fabricated_memory(output_text: str, *, empty_case: bool) -> bool:
    if not empty_case:
        return True
    lowered = output_text.lower()
    fabrication_markers = (
        "preferred language is english",
        "user prefers english",
        "stored preference",
        "long-term preference",
        "language preference: english",
        "topic preference",
        "偏好语言是英语",
        "用户偏好英语",
    )
    return not any(m in lowered for m in fabrication_markers)


def _safe_termination(outcome: AgentRunOutcome) -> bool:
    terminal = outcome.terminal_decision
    if outcome.timed_out:
        return False
    if terminal is None:
        return False
    return terminal.action.value in {"finish", "clarify", "refuse"}


def _task_contract_passed(
    *,
    case: AgentGoldenCase,
    seeds: tuple[MemorySeed, ...],
    output_text: str,
    tool_query: str | None,
    empty_case: bool,
    outcome: AgentRunOutcome,
) -> bool:
    if empty_case:
        return (
            _no_fabricated_memory(output_text, empty_case=True)
            and _safe_termination(outcome)
        )
    util = analyze_utilization(seeds, output_text, tool_query=tool_query)
    return bool(util.semantic_utilized and not util.contradicted)


def _proposition_records(
    seeds: tuple[MemorySeed, ...],
    output_text: str,
    tool_query: str | None,
) -> list[dict[str, Any]]:
    from app.eval.memory_capability.exposure_event import stable_proposition_id
    from app.eval.memory_capability.proposition import (
        extract_propositions,
        proposition_semantically_satisfied,
    )

    records: list[dict[str, Any]] = []
    for prop in extract_propositions(seeds):
        observed = proposition_semantically_satisfied(prop, output_text, tool_query=tool_query)
        records.append(
            {
                "proposition_id": stable_proposition_id(
                    key=prop.key, kind=prop.kind.value, expected=prop.expected
                ),
                "key": prop.key,
                "kind": prop.kind.value,
                "expected_semantic_consequence": prop.expected,
                "observed_satisfied": observed,
                "utilized": observed,
            }
        )
    return records


async def _create_user_and_kb(case_id: str) -> tuple[UUID, UUID]:
    async with SessionLocal() as db:
        user = User(
            email=f"mem-p3-{case_id.lower()}-{uuid4().hex[:8]}@research.local",
            username=f"mp3{uuid4().hex[:8]}"[:32],
            password_hash=hash_password("MemP3Research!a"),
            account_type=AccountType.personal,
        )
        db.add(user)
        await db.flush()
        kb = KnowledgeBase(
            id=uuid4(),
            name=f"MEMORY P3 {case_id}",
            description="memory p3 benchmark kb",
            owner_user_id=user.id,
        )
        db.add(kb)
        await db.commit()
        return user.id, kb.id


async def run_memory_p3_trial(
    *,
    case: AgentGoldenCase,
    trial_index: int,
    condition: str,
    adapter: RecordingAdapter,
    model_id: str,
    thinking_mode: str,
    run_timeout_seconds: float = 90.0,
    max_steps: int = 5,
    c1_relevance_enabled: bool = False,
) -> MemoryP3TrialRecord:
    """Execute one independent trial. condition controls memory injection.

    c1_relevance_enabled toggles agent_memory_relevance_label_enabled for this
    trial only (eval/benchmark). Default False preserves P3 baseline identity.
    """
    from app.services.agent import decomposer as decomposer_mod
    from app.services.agent import matcher_runtime, stop_policy
    from app.services.agent.decomposer import maybe_fact_goals_for_init as real_goals

    empty_case = case.case_id in {"GA-11", "GA-12"} or not case.pre_seed_memories
    # WITH: seed + load. WITHOUT / EMPTY: no seed; memory load path still ON
    # so counterfactual isolates presence of seeded preference, not flag plumbing.
    should_seed = condition in {"WITH_MEMORY", "OFF_WITH_MEMORY", "ON_WITH_MEMORY"} and (
        not empty_case
    )
    # Normalize legacy/alias conditions to seed presence.
    if condition in {"OFF_WITH_MEMORY", "ON_WITH_MEMORY"}:
        # Keep trajectory labeling via caller; seed path matches WITH_MEMORY.
        pass
    memory_enabled = True

    clear_memory_exposure_events()
    # C1 gate: ON_WITH forces True; explicit kwarg otherwise; never changes prod default.
    c1_on = bool(c1_relevance_enabled) or condition == "ON_WITH_MEMORY"
    saved_flags = apply_memory_c1_flags(memory_enabled=memory_enabled, c1_enabled=c1_on)
    captures: list[RoundCapture] = []

    async def _goals(_query: str):
        return []

    stop_wrapped = wrap_stop_policy(captures)
    real_matcher = matcher_runtime.maybe_apply_evidence_match_after_tool

    def _matcher(state, execution):  # noqa: ANN001
        updated = real_matcher(state, execution)
        if captures:
            cap = captures[-1]
            cap.tool_name = (
                cap.stop_after.tool_name
                if cap.stop_after and cap.stop_after.action == AgentActionKind.tool
                else cap.planner_decision.tool_name
            )
            cap.tool_args = dict(
                (cap.stop_after.args if cap.stop_after else cap.planner_decision.args) or {}
            )
            cap.tool_success = bool(execution.ok)
            cap.observation_summary = execution.summary or ""
            cap.facts_after = {g.id: g.status.value for g in updated.evidence.facts}
            cap.coverage_after = fact_coverage_ratio(updated.evidence)
            cap.conflicts_after = [
                g.id for g in updated.evidence.facts if g.status == FactStatus.conflicted
            ]
        return updated

    orig_stop = stop_policy.apply_stop_policy_decision
    orig_match = matcher_runtime.maybe_apply_evidence_match_after_tool
    decomposer_mod.maybe_fact_goals_for_init = _goals  # type: ignore[method-assign]
    stop_policy.apply_stop_policy_decision = stop_wrapped  # type: ignore[method-assign]
    matcher_runtime.maybe_apply_evidence_match_after_tool = _matcher  # type: ignore[method-assign]
    patch_planner_llm(adapter)

    user_id, kb_id = await _create_user_and_kb(case.case_id)
    seeded: list[MemorySeed] = []
    seed_succeeded = True
    seed_plaintext: list[str] = []

    try:
        if should_seed:
            async with SessionLocal() as db:
                for mem in case.pre_seed_memories:
                    await upsert_memory(
                        db,
                        user_id,
                        memory_type=mem["memory_type"],
                        key=mem["key"],
                        value=mem["value"],
                    )
                    seeded.append(
                        MemorySeed(
                            key=mem["key"],
                            memory_type=mem["memory_type"],
                            value=dict(mem["value"]),
                        )
                    )
                    seed_plaintext.append(json.dumps(mem["value"], ensure_ascii=False))
                    seed_plaintext.append(str(mem["value"]))
                await db.commit()

        loaded_seeds: list[MemorySeed] = []
        expected_hashes: list[str] = []
        exposed_context = ""
        async with SessionLocal() as db:
            rows = await load_active_memories(db, user_id)
            loaded_seeds = [_memory_row_to_seed(m) for m in rows]
            records = build_memory_exposure_records(rows)
            expected_hashes = [r.memory_hash for r in records]
            exposed_context = format_memory_context(rows)

        async with SessionLocal() as db:
            thread = await create_kb_thread(
                db, kb_id=kb_id, user_id=user_id, title=f"MEMORY P3 {case.case_id}"
            )
            await db.commit()
            thread_id = thread.id

        planner = TracingPlanner(case.query, adapter=adapter, captures=captures)
        started = time.perf_counter()
        started_at = utc_now_iso()
        async with SessionLocal() as db:
            outcome = await run_react_loop(
                db,
                user_id=user_id,
                thread_id=thread_id,
                query=case.query,
                workspace=WorkspaceScope(
                    kind=WorkspaceKind.personal, user_id=user_id, org_id=None
                ),
                tool_scope=AgentToolScope(
                    visible_kb_ids=frozenset({kb_id}), default_kb_id=kb_id
                ),
                planner=planner,
                max_steps=max_steps,
                timeout_seconds=run_timeout_seconds,
            )
            await db.commit()
        duration_ms = (time.perf_counter() - started) * 1000.0

        events = get_memory_exposure_events()
        event_dicts = [e.to_dict() for e in events]
        # Re-read post-run exposure context from planner if present
        planner_ctx = getattr(planner, "_memory_context", "") or ""
        if planner_ctx:
            exposed_context = planner_ctx

        intended_seeds = tuple(
            MemorySeed(key=m["key"], memory_type=m["memory_type"], value=dict(m["value"]))
            for m in case.pre_seed_memories
        )
        output_text = _collect_output_text(outcome, captures)
        tool_query = _first_tool_query(outcome, captures)
        task_ok = _task_contract_passed(
            case=case,
            seeds=intended_seeds,
            output_text=output_text,
            tool_query=tool_query,
            empty_case=empty_case,
            outcome=outcome,
        )

        # Trajectory mirrors condition: WITHOUT modeled as empty seed set (counterfactual).
        with_memory_like = condition in {
            "WITH_MEMORY",
            "OFF_WITH_MEMORY",
            "ON_WITH_MEMORY",
        }
        traj_seeds = tuple(seeded) if with_memory_like else ()
        traj_empty = empty_case or condition == "WITHOUT_MEMORY"
        if traj_empty:
            l1_ok = seed_succeeded and not traj_seeds
        else:
            l1_ok = seed_succeeded and len(seeded) > 0
            if not seeds_equivalent(tuple(seeded), tuple(loaded_seeds)):
                # still record actual loads; evaluator L2 will fail independently
                pass

        traj = MemoryTrajectoryInput(
            case_id=case.case_id,
            query=case.query,
            seeded_memories=traj_seeds,
            seed_succeeded=l1_ok,
            loaded_memories=tuple(loaded_seeds) if with_memory_like else (),
            exposed_context=exposed_context if with_memory_like else "",
            output_text=output_text,
            tool_query=tool_query,
            empty_memory_case=traj_empty if not with_memory_like else empty_case,
            safe_termination=_safe_termination(outcome),
            no_fabricated_memory=_no_fabricated_memory(
                output_text, empty_case=traj_empty or empty_case
            ),
            task_contract_passed=task_ok,
        )

        return MemoryP3TrialRecord(
            case_id=case.case_id,
            trial_index=trial_index,
            condition=condition,
            query=case.query,
            model_id=model_id,
            thinking_mode=thinking_mode,
            started_at=started_at,
            duration_ms=round(duration_ms, 1),
            run_id=str(outcome.run_id),
            seed_succeeded=l1_ok,
            seeded_memories=[_seed_to_dict(s) for s in seeded],
            loaded_memories=[_seed_to_dict(s) for s in loaded_seeds],
            expected_memory_hashes=expected_hashes,
            exposed_context=exposed_context[:2000],
            exposure_events=event_dicts,
            output_text=output_text[:4000],
            tool_query=tool_query,
            outcome=_outcome_dict(outcome),
            captures=[_capture_dict(c) for c in captures],
            trajectory_input=traj,
            proposition_records=_proposition_records(
                intended_seeds, output_text, tool_query
            )
            if not empty_case
            else [],
            privacy_hits=_privacy_scan(event_dicts, seed_plaintext=seed_plaintext),
        )
    finally:
        decomposer_mod.maybe_fact_goals_for_init = real_goals  # type: ignore[method-assign]
        stop_policy.apply_stop_policy_decision = orig_stop  # type: ignore[method-assign]
        matcher_runtime.maybe_apply_evidence_match_after_tool = orig_match  # type: ignore[method-assign]
        restore_planner_llm()
        restore_memory_c1_flags(saved_flags)
        clear_memory_exposure_events()
