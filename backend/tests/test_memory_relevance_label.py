"""MEMORY C1 product experiment — gated contrastive relevance framing.

Deterministic safety tests. Flag default OFF; OFF must not change baseline.
Does not touch P3/P4 scoring.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from app.core.config import settings
from app.eval.memory_capability.exposure_event import MemoryExposureChannel
from app.models.agent_memory import AgentMemory
from app.services.agent.memory import format_memory_context
from app.services.agent.memory_exposure import (
    MemoryExposureRecord,
    clear_memory_exposure_events,
    emit_memory_exposure_at_prompt_boundary,
    get_memory_exposure_events,
)
from app.services.agent.memory_relevance_label import (
    BASELINE_MEMORY_HEADER,
    C1_RELEVANCE_HEADER,
    build_planner_memory_block,
    extract_memory_proposition_lines,
)


def _fake_memory(
    *,
    key: str = "lang",
    memory_type: str = "preference",
    value: object | None = None,
    tier: str = "working",
    importance: float = 0.9,
    kb_id=None,
) -> AgentMemory:
    return AgentMemory(
        id=uuid4(),
        user_id=uuid4(),
        kb_id=kb_id,
        memory_type=memory_type,
        key=key,
        value=value if value is not None else {"language": "en"},
        confidence=1.0,
        last_accessed_at=datetime.now(timezone.utc),
        source="rule_inference",
        status="active",
        tier=tier,
        importance_score=importance,
        summary=None,
    )


def _baseline_block(memory_context: str) -> str:
    return f"\n\n{BASELINE_MEMORY_HEADER}\n{memory_context}"


def test_relevance_label_flag_default_off() -> None:
    assert settings.agent_memory_relevance_label_enabled is False
    assert (
        type(settings).model_fields["agent_memory_relevance_label_enabled"].default
        is False
    )


def test_off_prompt_identity_with_format_memory_context() -> None:
    assert settings.agent_memory_relevance_label_enabled is False
    ctx = format_memory_context(
        [_fake_memory(key="lang", value={"language": "en"})]
    )
    assert ctx.startswith(BASELINE_MEMORY_HEADER)
    off = build_planner_memory_block(ctx, enabled=False)
    assert off == _baseline_block(ctx)
    assert off == build_planner_memory_block(ctx)  # settings default OFF


def test_on_adds_relevance_framing_only() -> None:
    m1 = _fake_memory(key="lang", value={"language": "en"}, importance=0.9)
    m2 = _fake_memory(
        key="retrieval_depth",
        memory_type="pattern",
        value={"mode": "thorough"},
        tier="long_term",
        importance=0.4,
    )
    ctx = format_memory_context([m1, m2])
    lines = extract_memory_proposition_lines(ctx)
    on = build_planner_memory_block(ctx, enabled=True)

    assert C1_RELEVANCE_HEADER in on
    assert BASELINE_MEMORY_HEADER not in on
    assert "不覆盖检索结果" not in on
    assert lines in on
    assert on.count("- [working] lang:") == 1
    assert on.count("- [long_term] retrieval_depth:") == 1
    # Order preserved relative to pipeline output
    assert on.index("- [working] lang:") < on.index("- [long_term] retrieval_depth:")
    # No authority / force-use language
    lower = on.lower()
    assert "must use" not in lower
    assert "definitely correct" not in lower
    assert "expected answer" not in lower


def test_on_does_not_change_content_order_or_selection() -> None:
    memories = [
        _fake_memory(key="a", value={"v": 1}, importance=0.95),
        _fake_memory(key="b", value={"v": 2}, importance=0.80),
        _fake_memory(key="c", value={"v": 3}, importance=0.70),
    ]
    ctx = format_memory_context(memories)
    off = build_planner_memory_block(ctx, enabled=False)
    on = build_planner_memory_block(ctx, enabled=True)

    body = extract_memory_proposition_lines(ctx)
    assert on.split(C1_RELEVANCE_HEADER, 1)[1].lstrip("\n") == body
    assert extract_memory_proposition_lines(off) == body
    keys_in_order = [line.split("]", 1)[1].split(":", 1)[0].strip() for line in body.splitlines()]
    assert keys_in_order == ["a", "b", "c"]
    # OFF still double-wraps baseline header (frozen C0 identity)
    assert off.count(BASELINE_MEMORY_HEADER) == 2
    assert on.count(C1_RELEVANCE_HEADER) == 1
    # Selection unchanged: only pipeline memories appear
    assert "secret_other" not in on


def test_wrong_scope_still_excluded_from_block() -> None:
    """Helper only formats what the pipeline passed — no scope expansion."""
    in_scope = _fake_memory(key="lang", value={"language": "en"})
    # Simulate pipeline that already excluded other-user / wrong-kb rows:
    ctx = format_memory_context([in_scope])
    block = build_planner_memory_block(ctx, enabled=True)
    assert "lang" in block
    assert "other_user_secret" not in block
    assert "wrong_kb" not in block
    # Passing only selected memories never invents excluded keys
    assert extract_memory_proposition_lines(ctx).count("\n") == 0  # single line


def test_empty_memory_no_label_block() -> None:
    assert build_planner_memory_block("", enabled=False) == ""
    assert build_planner_memory_block("", enabled=True) == ""
    assert build_planner_memory_block(format_memory_context([]), enabled=True) == ""


def test_privacy_exposure_event_unchanged(monkeypatch) -> None:
    monkeypatch.setattr(settings, "agent_memory_exposure_trace_enabled", True)
    clear_memory_exposure_events()
    ctx = format_memory_context([_fake_memory(key="lang", value={"language": "en"})])
    rec = MemoryExposureRecord(
        memory_hash="hash_lang_en",
        memory_key="lang",
        memory_id=str(uuid4()),
    )
    off_block = build_planner_memory_block(ctx, enabled=False)
    on_block = build_planner_memory_block(ctx, enabled=True)

    emit_memory_exposure_at_prompt_boundary(
        memory_block=off_block,
        channel=MemoryExposureChannel.llm_planner,
        run_id="run-1",
        step_id="step-1",
        records=(rec,),
    )
    emit_memory_exposure_at_prompt_boundary(
        memory_block=on_block,
        channel=MemoryExposureChannel.llm_planner,
        run_id="run-1",
        step_id="step-2",
        records=(rec,),
    )
    events = get_memory_exposure_events()
    assert len(events) == 2
    for ev in events:
        payload = ev.to_dict()
        assert "value" not in payload
        assert "plaintext" not in payload
        assert "prompt" not in payload
        assert C1_RELEVANCE_HEADER not in str(payload)
        assert BASELINE_MEMORY_HEADER not in str(payload)
        assert payload["memory_hash"] == "hash_lang_en"
        assert payload["memory_key"] == "lang"
        assert payload["injected_to_context"] is True
    clear_memory_exposure_events()
