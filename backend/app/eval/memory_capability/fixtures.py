"""Deterministic fixtures for MEMORY utilization evaluator (≥8 scenarios)."""

from __future__ import annotations

import json

from app.eval.memory_capability.schema import (
    CounterfactualPair,
    MemorySeed,
    MemoryTrajectoryInput,
)

_LANG_EN = MemorySeed(key="lang", memory_type="preference", value={"language": "en"})
_LANG_ZHTW = MemorySeed(key="lang", memory_type="preference", value={"language": "zh-TW"})
_TOPIC_DOCKER = MemorySeed(key="topic", memory_type="preference", value={"topic": "docker"})


def _exposed(*seeds: MemorySeed) -> str:
    lines = []
    for seed in seeds:
        payload = json.dumps(seed.value, ensure_ascii=False, sort_keys=True)
        lines.append(f"- [long_term] {seed.key}: {payload} ({seed.memory_type}) importance=0.50")
    return "用户长期偏好（仅供参考，不覆盖检索结果）：\n" + "\n".join(lines)


# 1. seeded + loaded + exposed + utilized + benefit
FIXTURE_FULL_UTILIZATION = MemoryTrajectoryInput(
    case_id="FIX-01-full-utilization",
    query="What is the user's preferred language for retrieval?",
    seeded_memories=(_LANG_EN,),
    seed_succeeded=True,
    loaded_memories=(_LANG_EN,),
    exposed_context=_exposed(_LANG_EN),
    output_text="The user's preferred language for retrieval is English.",
    task_contract_passed=True,
)

FIXTURE_FULL_UTILIZATION_COUNTERFACTUAL = CounterfactualPair(
    case_id="FIX-01-full-utilization",
    with_memory=FIXTURE_FULL_UTILIZATION,
    without_memory=MemoryTrajectoryInput(
        case_id="FIX-01-without",
        query=FIXTURE_FULL_UTILIZATION.query,
        seeded_memories=(),
        loaded_memories=(),
        exposed_context="",
        output_text="I do not know the user's language preference.",
        task_contract_passed=False,
    ),
)

# 2. seeded but not loaded
FIXTURE_SEEDED_NOT_LOADED = MemoryTrajectoryInput(
    case_id="FIX-02-seeded-not-loaded",
    query="What is the user's preferred language?",
    seeded_memories=(_LANG_EN,),
    seed_succeeded=True,
    loaded_memories=(),
    exposed_context="",
    output_text="Unable to determine preference.",
    task_contract_passed=False,
)

# 3. loaded but not exposed
FIXTURE_LOADED_NOT_EXPOSED = MemoryTrajectoryInput(
    case_id="FIX-03-loaded-not-exposed",
    query="What is the user's preferred language?",
    seeded_memories=(_LANG_EN,),
    seed_succeeded=True,
    loaded_memories=(_LANG_EN,),
    exposed_context="",
    output_text="Language preference unknown.",
    task_contract_passed=False,
)

# 4. exposed but ignored (no semantic use)
FIXTURE_EXPOSED_IGNORED = MemoryTrajectoryInput(
    case_id="FIX-04-exposed-ignored",
    query="What is the user's preferred language?",
    seeded_memories=(_LANG_EN,),
    seed_succeeded=True,
    loaded_memories=(_LANG_EN,),
    exposed_context=_exposed(_LANG_EN),
    output_text="I will search the knowledge base for relevant documents.",
    task_contract_passed=False,
)

# 5. keyword overlap but no semantic use
FIXTURE_KEYWORD_OVERLAP_ONLY = MemoryTrajectoryInput(
    case_id="FIX-05-keyword-overlap",
    query="What is the user's preferred language?",
    seeded_memories=(_LANG_ZHTW,),
    seed_succeeded=True,
    loaded_memories=(_LANG_ZHTW,),
    exposed_context=_exposed(_LANG_ZHTW),
    output_text="The memory key mentions zh-TW but I will respond in English.",
    task_contract_passed=False,
)

# 6. memory contradicted by output
FIXTURE_CONTRADICTED = MemoryTrajectoryInput(
    case_id="FIX-06-contradicted",
    query="What is the user's preferred language?",
    seeded_memories=(_LANG_EN,),
    seed_succeeded=True,
    loaded_memories=(_LANG_EN,),
    exposed_context=_exposed(_LANG_EN),
    output_text="The user prefers Chinese (中文) for all retrieval.",
    task_contract_passed=False,
)

# 7. empty memory correct behavior
FIXTURE_EMPTY_MEMORY = MemoryTrajectoryInput(
    case_id="FIX-07-empty-memory",
    query="What is the user's language preference?",
    seeded_memories=(),
    seed_succeeded=True,
    loaded_memories=(),
    exposed_context="",
    output_text="No stored language preference found; please clarify.",
    empty_memory_case=True,
    safe_termination=True,
    no_fabricated_memory=True,
    task_contract_passed=True,
)

# 8. without-memory also succeeds → no incremental benefit
FIXTURE_NO_INCREMENTAL_BENEFIT = CounterfactualPair(
    case_id="FIX-08-no-incremental-benefit",
    with_memory=MemoryTrajectoryInput(
        case_id="FIX-08-with",
        query="Search documents about Docker",
        seeded_memories=(_TOPIC_DOCKER,),
        seed_succeeded=True,
        loaded_memories=(_TOPIC_DOCKER,),
        exposed_context=_exposed(_TOPIC_DOCKER),
        output_text="Searching for docker container documentation.",
        tool_query="docker containers compose",
        task_contract_passed=True,
    ),
    without_memory=MemoryTrajectoryInput(
        case_id="FIX-08-without",
        query="Search documents about Docker",
        seeded_memories=(),
        loaded_memories=(),
        exposed_context="",
        output_text="Searching for docker container documentation.",
        tool_query="docker containers compose",
        task_contract_passed=True,
    ),
)

# GA-10 style dual preference utilization
FIXTURE_GA10_STYLE = MemoryTrajectoryInput(
    case_id="FIX-09-ga10-style",
    query="Search documents about Docker and React",
    seeded_memories=(_LANG_EN, _TOPIC_DOCKER),
    seed_succeeded=True,
    loaded_memories=(_LANG_EN, _TOPIC_DOCKER),
    exposed_context=_exposed(_LANG_EN, _TOPIC_DOCKER),
    output_text="Searching docker and compose docs in English; deprioritizing React.",
    tool_query="docker compose deployment",
    task_contract_passed=True,
)

ALL_TRAJECTORY_FIXTURES: tuple[MemoryTrajectoryInput, ...] = (
    FIXTURE_FULL_UTILIZATION,
    FIXTURE_SEEDED_NOT_LOADED,
    FIXTURE_LOADED_NOT_EXPOSED,
    FIXTURE_EXPOSED_IGNORED,
    FIXTURE_KEYWORD_OVERLAP_ONLY,
    FIXTURE_CONTRADICTED,
    FIXTURE_EMPTY_MEMORY,
    FIXTURE_GA10_STYLE,
)

ALL_COUNTERFACTUAL_FIXTURES: tuple[CounterfactualPair, ...] = (
    FIXTURE_FULL_UTILIZATION_COUNTERFACTUAL,
    FIXTURE_NO_INCREMENTAL_BENEFIT,
)

FIXTURE_BY_ID: dict[str, MemoryTrajectoryInput] = {f.case_id: f for f in ALL_TRAJECTORY_FIXTURES}
