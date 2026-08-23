"""Deterministic MemoryExposureEvent fixtures (eval-only — no runtime emit)."""

from __future__ import annotations

from app.eval.memory_capability.exposure_event import (
    MemoryExposureChannel,
    MemoryExposureEvent,
    MemoryExposureScope,
    MemoryExposureSource,
    stable_memory_hash,
    stable_proposition_id,
)

LANG_EN_HASH = stable_memory_hash(
    key="lang",
    memory_type="preference",
    value={"language": "en"},
)
LANG_EN_PROP = stable_proposition_id(
    key="lang",
    kind="language_preference",
    expected="en",
)

RUN_A = "run-expose-a"
RUN_B = "run-expose-b"
STEP_1 = "1"
STEP_2 = "2"


def _valid(
    *,
    run_id: str = RUN_A,
    step_id: str = STEP_1,
    memory_hash: str = LANG_EN_HASH,
    injected: bool = True,
    source: MemoryExposureSource = MemoryExposureSource.planner_prompt_injection,
    channel: MemoryExposureChannel = MemoryExposureChannel.next_action_planner,
) -> MemoryExposureEvent:
    return MemoryExposureEvent(
        run_id=run_id,
        step_id=step_id,
        memory_hash=memory_hash,
        injected_to_context=injected,
        scope=MemoryExposureScope.run,
        source=source,
        context_slot="planner_user_prompt",
        channel=channel,
        memory_id="11111111-1111-1111-1111-111111111111",
        proposition_id=LANG_EN_PROP,
        memory_key="lang",
        timestamp="2026-08-23T00:00:00Z",
    )


# Valid model-visible exposure
FIXTURE_VALID_EXPOSURE = _valid()

# Same memory re-injected on step 2 (dedup under scope=run)
FIXTURE_REPEAT_STEP2 = _valid(step_id=STEP_2)

# Loaded / format / assign claims — NOT authoritative
FIXTURE_LOAD_ONLY = _valid(
    injected=True,
    source=MemoryExposureSource.load_only,
)
FIXTURE_BEFORE_INJECTION = _valid(
    injected=False,
    source=MemoryExposureSource.planner_prompt_injection,
)

# Wrong binding
FIXTURE_WRONG_RUN = _valid(run_id=RUN_B)
FIXTURE_WRONG_STEP = _valid(step_id="99")
FIXTURE_WRONG_HASH = _valid(
    memory_hash=stable_memory_hash(
        key="lang",
        memory_type="preference",
        value={"language": "zh-TW"},
    ),
)

EXPECTED_HASHES_LANG_EN: tuple[str, ...] = (LANG_EN_HASH,)
