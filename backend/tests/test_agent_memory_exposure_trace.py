"""MEMORY P2 instrumentation — MemoryExposureEvent at planner prompt boundary.

Behavior change: NONE. Flag default OFF. Privacy: no plaintext in events.
"""

from __future__ import annotations

import copy
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.core.config import settings
from app.eval.memory_capability.exposure_event import (
    MemoryExposureChannel,
    stable_memory_hash,
)
from app.eval.memory_capability.l3_exposure_evaluator import l3_exposed_from_events
from app.services.agent.memory_exposure import (
    MemoryExposureRecord,
    build_memory_exposure_records,
    clear_memory_exposure_events,
    emit_memory_exposure_at_prompt_boundary,
    get_memory_exposure_events,
    memory_exposure_trace_enabled,
)
from app.services.agent.planners import LLMPlanner, NextActionPlanner, SafetyFrame
from app.services.agent.state import init_agent_state, summarize_state_for_planner

LANG_VALUE = {"language": "en"}
LANG_HASH = stable_memory_hash(
    key="lang", memory_type="preference", value=LANG_VALUE
)
SECRET_PLAINTEXT = "user-private-memory-SECRET-42"


@pytest.fixture(autouse=True)
def _reset_exposure_sink_and_flag(monkeypatch: pytest.MonkeyPatch):
    clear_memory_exposure_events()
    monkeypatch.setattr(
        settings, "agent_memory_exposure_trace_enabled", False, raising=False
    )
    yield
    clear_memory_exposure_events()
    monkeypatch.setattr(
        settings, "agent_memory_exposure_trace_enabled", False, raising=False
    )


def _records(*items: tuple[str, str, dict]) -> tuple[MemoryExposureRecord, ...]:
    out: list[MemoryExposureRecord] = []
    for key, memory_type, value in items:
        out.append(
            MemoryExposureRecord(
                memory_hash=stable_memory_hash(
                    key=key, memory_type=memory_type, value=value
                ),
                memory_key=key,
                memory_id=f"id-{key}",
            )
        )
    return tuple(out)


def _attach_exposure(
    planner: LLMPlanner | NextActionPlanner,
    *,
    records: tuple[MemoryExposureRecord, ...],
    run_id: str = "run-a",
    step_id: str = "1",
) -> None:
    planner._memory_exposure_records = records
    planner._exposure_run_id = run_id
    planner._exposure_step_id = step_id


def test_flag_defaults_off() -> None:
    assert settings.agent_memory_exposure_trace_enabled is False
    assert memory_exposure_trace_enabled() is False


def test_flag_off_no_event() -> None:
    recs = _records(("lang", "preference", LANG_VALUE))
    emitted = emit_memory_exposure_at_prompt_boundary(
        memory_block="non-empty",
        channel=MemoryExposureChannel.llm_planner,
        run_id="run-a",
        step_id="1",
        records=recs,
    )
    assert emitted == ()
    assert get_memory_exposure_events() == ()


def test_flag_on_emits_correct_event(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "agent_memory_exposure_trace_enabled", True)
    recs = _records(("lang", "preference", LANG_VALUE))
    emitted = emit_memory_exposure_at_prompt_boundary(
        memory_block="non-empty",
        channel=MemoryExposureChannel.llm_planner,
        run_id="run-a",
        step_id="1",
        records=recs,
    )
    assert len(emitted) == 1
    ev = emitted[0]
    assert ev.run_id == "run-a"
    assert ev.step_id == "1"
    assert ev.memory_hash == LANG_HASH
    assert ev.injected_to_context is True
    assert ev.channel == MemoryExposureChannel.llm_planner
    assert ev.memory_key == "lang"


def test_empty_memory_no_event(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "agent_memory_exposure_trace_enabled", True)
    recs = _records(("lang", "preference", LANG_VALUE))
    emitted = emit_memory_exposure_at_prompt_boundary(
        memory_block="",
        channel=MemoryExposureChannel.llm_planner,
        run_id="run-a",
        step_id="1",
        records=recs,
    )
    assert emitted == ()
    assert get_memory_exposure_events() == ()


def test_wrong_scope_missing_run_or_step_no_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "agent_memory_exposure_trace_enabled", True)
    recs = _records(("lang", "preference", LANG_VALUE))
    assert (
        emit_memory_exposure_at_prompt_boundary(
            memory_block="x",
            channel=MemoryExposureChannel.llm_planner,
            run_id=None,
            step_id="1",
            records=recs,
        )
        == ()
    )
    assert (
        emit_memory_exposure_at_prompt_boundary(
            memory_block="x",
            channel=MemoryExposureChannel.llm_planner,
            run_id="run-a",
            step_id=None,
            records=recs,
        )
        == ()
    )
    assert get_memory_exposure_events() == ()


def test_dedup_within_emit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "agent_memory_exposure_trace_enabled", True)
    rec = MemoryExposureRecord(memory_hash=LANG_HASH, memory_key="lang")
    emitted = emit_memory_exposure_at_prompt_boundary(
        memory_block="x",
        channel=MemoryExposureChannel.next_action_planner,
        run_id="run-a",
        step_id="1",
        records=(rec, rec, rec),
    )
    assert len(emitted) == 1
    assert len(get_memory_exposure_events()) == 1


def test_no_plaintext_leakage(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "agent_memory_exposure_trace_enabled", True)
    secret_hash = stable_memory_hash(
        key="secret",
        memory_type="preference",
        value={"note": SECRET_PLAINTEXT},
    )
    recs = (
        MemoryExposureRecord(
            memory_hash=secret_hash,
            memory_key="secret",
            memory_id="id-secret",
        ),
    )
    emitted = emit_memory_exposure_at_prompt_boundary(
        memory_block=f"contains {SECRET_PLAINTEXT}",
        channel=MemoryExposureChannel.llm_planner,
        run_id="run-a",
        step_id="1",
        records=recs,
    )
    assert len(emitted) == 1
    payload = emitted[0].to_dict()
    blob = str(payload)
    assert SECRET_PLAINTEXT not in blob
    assert "value" not in payload
    assert "content" not in payload
    assert "summary" not in payload
    assert "prompt" not in payload


def test_build_records_preserves_order_and_hashes() -> None:
    m1 = SimpleNamespace(
        id="a",
        key="lang",
        memory_type="preference",
        value=LANG_VALUE,
        summary=None,
    )
    m2 = SimpleNamespace(
        id="b",
        key="tone",
        memory_type="preference",
        value={"tone": "formal"},
        summary=None,
    )
    records = build_memory_exposure_records([m1, m2])
    assert [r.memory_key for r in records] == ["lang", "tone"]
    assert records[0].memory_hash == LANG_HASH
    assert records[1].memory_hash == stable_memory_hash(
        key="tone", memory_type="preference", value={"tone": "formal"}
    )


def test_l3_evaluator_loaded_only_false() -> None:
    result = l3_exposed_from_events(
        run_id="run-a",
        expected_memory_hashes=(LANG_HASH,),
        events=(),
    )
    assert result.passed is False


def test_l3_evaluator_actual_event_true(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "agent_memory_exposure_trace_enabled", True)
    recs = _records(("lang", "preference", LANG_VALUE))
    emit_memory_exposure_at_prompt_boundary(
        memory_block="x",
        channel=MemoryExposureChannel.llm_planner,
        run_id="run-a",
        step_id="1",
        records=recs,
    )
    result = l3_exposed_from_events(
        run_id="run-a",
        expected_memory_hashes=(LANG_HASH,),
        events=get_memory_exposure_events(),
    )
    assert result.passed is True


def test_l3_evaluator_wrong_memory_run_step_false(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "agent_memory_exposure_trace_enabled", True)
    recs = _records(("lang", "preference", LANG_VALUE))
    emit_memory_exposure_at_prompt_boundary(
        memory_block="x",
        channel=MemoryExposureChannel.llm_planner,
        run_id="run-other",
        step_id="99",
        records=recs,
    )
    events = get_memory_exposure_events()
    wrong_run = l3_exposed_from_events(
        run_id="run-a",
        expected_memory_hashes=(LANG_HASH,),
        events=events,
    )
    wrong_step = l3_exposed_from_events(
        run_id="run-other",
        expected_memory_hashes=(LANG_HASH,),
        events=events,
        step_id="1",
    )
    wrong_hash = l3_exposed_from_events(
        run_id="run-other",
        expected_memory_hashes=("0" * 64,),
        events=events,
    )
    assert wrong_run.passed is False
    assert wrong_step.passed is False
    assert wrong_hash.passed is False


def test_memory_list_order_identical_on_off(monkeypatch: pytest.MonkeyPatch) -> None:
    m1 = SimpleNamespace(
        id="1",
        key="lang",
        memory_type="preference",
        value=LANG_VALUE,
        summary=None,
    )
    m2 = SimpleNamespace(
        id="2",
        key="tone",
        memory_type="preference",
        value={"tone": "formal"},
        summary=None,
    )
    monkeypatch.setattr(settings, "agent_memory_exposure_trace_enabled", False)
    off_records = build_memory_exposure_records([m1, m2])
    monkeypatch.setattr(settings, "agent_memory_exposure_trace_enabled", True)
    on_records = build_memory_exposure_records([m1, m2])
    assert [r.memory_key for r in off_records] == [r.memory_key for r in on_records]
    assert [r.memory_hash for r in off_records] == [r.memory_hash for r in on_records]
    assert [r.memory_hash for r in copy.deepcopy(off_records)] == [
        r.memory_hash for r in on_records
    ]


@pytest.mark.asyncio
async def test_prompt_identical_flag_on_off_llm_planner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    safety = SafetyFrame("hello")
    memory_ctx = '- [long_term] lang: {"language": "en"} (preference) importance=0.50'
    recs = _records(("lang", "preference", LANG_VALUE))
    prompts: list[str] = []

    for enabled in (False, True):
        clear_memory_exposure_events()
        monkeypatch.setattr(settings, "agent_memory_exposure_trace_enabled", enabled)
        planner = LLMPlanner(
            "hello",
            safety_frame=safety,
            tool_specs=safety.all_tool_specs(),
            memory_context=memory_ctx,
        )
        _attach_exposure(planner, records=recs)

        captured: dict[str, str] = {}

        async def _fake(messages, **_kwargs):
            captured["prompt"] = messages[0]["content"]
            return "[]", SimpleNamespace(has_value=False)

        with (
            patch(
                "app.services.rag.chat_llm.complete_chat_with_usage",
                new=AsyncMock(side_effect=_fake),
            ),
            patch(
                "app.services.rag.chat_llm.has_available_chat_provider_key",
                return_value=True,
            ),
        ):
            await planner._call_llm_for_plan("hello", {}, stage="plan")

        assert "prompt" in captured
        prompts.append(captured["prompt"])
        if enabled:
            assert len(get_memory_exposure_events()) == 1
        else:
            assert get_memory_exposure_events() == ()

    assert prompts[0] == prompts[1]
    assert memory_ctx in prompts[0]


@pytest.mark.asyncio
async def test_next_action_planner_emits_when_flag_on(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "agent_memory_exposure_trace_enabled", True)
    safety = SafetyFrame("hello")
    planner = NextActionPlanner(
        "hello",
        safety_frame=safety,
        tool_specs=safety.all_tool_specs(),
        memory_context="pref line",
    )
    _attach_exposure(
        planner,
        records=_records(("lang", "preference", LANG_VALUE)),
        step_id="0",
    )

    async def _fake(messages, **_kwargs):
        return (
            '{"action":"finish","reason_code":"done"}',
            SimpleNamespace(has_value=False),
        )

    state = init_agent_state(original_query="hello", max_steps=3)
    summary = summarize_state_for_planner(state)

    with (
        patch(
            "app.services.rag.chat_llm.complete_chat_with_usage",
            new=AsyncMock(side_effect=_fake),
        ),
        patch(
            "app.services.rag.chat_llm.has_available_chat_provider_key",
            return_value=True,
        ),
    ):
        await planner._call_llm(summary, safety.all_tool_specs())

    events = get_memory_exposure_events()
    assert len(events) == 1
    assert events[0].channel == MemoryExposureChannel.next_action_planner
    assert events[0].memory_hash == LANG_HASH
    assert SECRET_PLAINTEXT not in str(events[0].to_dict())
