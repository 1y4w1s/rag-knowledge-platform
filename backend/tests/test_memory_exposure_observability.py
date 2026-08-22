"""MEMORY P2 L3 observability contract — deterministic tests (eval-only)."""

from __future__ import annotations

from app.eval.memory_capability.exposure_audit import (
    TRUE_EXPOSURE_BOUNDARY,
    exposure_boundary_audit,
)
from app.eval.memory_capability.exposure_event import (
    MEMORY_EXPOSURE_EVENT_FIELDS,
    PRIVACY_POLICY,
    MemoryExposureEvent,
    MemoryExposureScope,
    MemoryExposureSource,
    stable_memory_hash,
    stable_proposition_id,
)
from app.eval.memory_capability.exposure_fixtures import (
    EXPECTED_HASHES_LANG_EN,
    FIXTURE_BEFORE_INJECTION,
    FIXTURE_LOAD_ONLY,
    FIXTURE_REPEAT_STEP2,
    FIXTURE_VALID_EXPOSURE,
    FIXTURE_WRONG_HASH,
    FIXTURE_WRONG_RUN,
    FIXTURE_WRONG_STEP,
    LANG_EN_HASH,
    RUN_A,
    STEP_1,
)
from app.eval.memory_capability.exposure_semantics import (
    count_unique_exposures,
    dedupe_unique_exposures,
    is_authoritative_exposure,
)
from app.eval.memory_capability.instrumentation_options import (
    PRODUCT_PATCH_BUDGET,
    RECOMMENDED_OPTION,
    instrumentation_design,
)
from app.eval.memory_capability.l3_exposure_evaluator import (
    EVALUATOR_INTERFACE_READY,
    l3_exposed_from_events,
    validate_exposure_event,
)


def test_l3_gap_confirmed_and_boundary_is_planner_prompt() -> None:
    audit = exposure_boundary_audit()
    assert audit["l3_gap"]["status"] == "CONFIRMED"
    assert audit["runtime_emit"] is False
    assert audit["product_code_modified"] is False
    boundary = TRUE_EXPOSURE_BOUNDARY
    assert boundary["file"].endswith("planners.py")
    assert "LLMPlanner._call_llm_for_plan" in boundary["functions"]
    assert "NextActionPlanner._call_llm" in boundary["functions"]
    assert "load_active_memories return value" in boundary["not_exposure"]


def test_privacy_prefers_hash_not_raw_content() -> None:
    assert PRIVACY_POLICY["store_raw_memory_content"] is False
    assert "memory_hash" in MEMORY_EXPOSURE_EVENT_FIELDS
    assert "proposition_id" in MEMORY_EXPOSURE_EVENT_FIELDS
    h = stable_memory_hash(
        key="lang", memory_type="preference", value={"language": "en"}
    )
    assert h == LANG_EN_HASH
    assert len(h) == 64
    pid = stable_proposition_id(
        key="lang", kind="language_preference", expected="en"
    )
    assert pid.startswith("prop_")


def test_loaded_but_no_event_l3_false() -> None:
    result = l3_exposed_from_events(
        run_id=RUN_A,
        expected_memory_hashes=EXPECTED_HASHES_LANG_EN,
        events=(),
    )
    assert result.passed is False
    assert "loaded≠exposed" in result.reason or "no exposure" in result.reason


def test_valid_exposure_l3_true() -> None:
    ok, reason = validate_exposure_event(FIXTURE_VALID_EXPOSURE)
    assert ok is True
    assert reason == ""
    result = l3_exposed_from_events(
        run_id=RUN_A,
        expected_memory_hashes=EXPECTED_HASHES_LANG_EN,
        events=(FIXTURE_VALID_EXPOSURE,),
    )
    assert result.passed is True


def test_wrong_run_step_hash_l3_false() -> None:
    wrong_run = l3_exposed_from_events(
        run_id=RUN_A,
        expected_memory_hashes=EXPECTED_HASHES_LANG_EN,
        events=(FIXTURE_WRONG_RUN,),
    )
    wrong_step = l3_exposed_from_events(
        run_id=RUN_A,
        expected_memory_hashes=EXPECTED_HASHES_LANG_EN,
        events=(FIXTURE_WRONG_STEP,),
        step_id=STEP_1,
    )
    wrong_hash = l3_exposed_from_events(
        run_id=RUN_A,
        expected_memory_hashes=EXPECTED_HASHES_LANG_EN,
        events=(FIXTURE_WRONG_HASH,),
    )
    assert wrong_run.passed is False
    assert wrong_step.passed is False
    assert wrong_hash.passed is False


def test_duplicate_unique_semantics_scope_run() -> None:
    events = (FIXTURE_VALID_EXPOSURE, FIXTURE_REPEAT_STEP2)
    assert count_unique_exposures(events, scope=MemoryExposureScope.run) == 1
    assert count_unique_exposures(events, scope=MemoryExposureScope.step) == 2
    unique = dedupe_unique_exposures(events, scope=MemoryExposureScope.run)
    assert len(unique) == 1
    result = l3_exposed_from_events(
        run_id=RUN_A,
        expected_memory_hashes=EXPECTED_HASHES_LANG_EN,
        events=events,
    )
    assert result.passed is True


def test_event_before_injection_invalid() -> None:
    assert is_authoritative_exposure(FIXTURE_BEFORE_INJECTION) is False
    ok, reason = validate_exposure_event(FIXTURE_BEFORE_INJECTION)
    assert ok is False
    assert "injected_to_context" in reason

    result = l3_exposed_from_events(
        run_id=RUN_A,
        expected_memory_hashes=EXPECTED_HASHES_LANG_EN,
        events=(FIXTURE_BEFORE_INJECTION,),
    )
    assert result.passed is False

    # load_only with injected=True still non-authoritative
    assert is_authoritative_exposure(FIXTURE_LOAD_ONLY) is False
    result_load = l3_exposed_from_events(
        run_id=RUN_A,
        expected_memory_hashes=EXPECTED_HASHES_LANG_EN,
        events=(FIXTURE_LOAD_ONLY,),
    )
    assert result_load.passed is False


def test_empty_memory_no_exposure_expected() -> None:
    result = l3_exposed_from_events(
        run_id=RUN_A,
        expected_memory_hashes=(),
        events=(),
        empty_memory_case=True,
    )
    assert result.passed is True

    fail = l3_exposed_from_events(
        run_id=RUN_A,
        expected_memory_hashes=(),
        events=(FIXTURE_VALID_EXPOSURE,),
        empty_memory_case=True,
    )
    assert fail.passed is False


def test_instrumentation_recommends_option_b_not_implemented() -> None:
    design = instrumentation_design()
    assert design["recommended"] == "B"
    assert RECOMMENDED_OPTION == "B"
    assert design["implemented_in_this_task"] is False
    assert PRODUCT_PATCH_BUDGET["behavior_change"] == "NONE"
    assert PRODUCT_PATCH_BUDGET["migration"] is False
    assert PRODUCT_PATCH_BUDGET["flag_default"] is False


def test_evaluator_interface_ready_without_runtime_emit() -> None:
    assert EVALUATOR_INTERFACE_READY["status"] == "READY"
    assert EVALUATOR_INTERFACE_READY["runtime_emit"] is False


def test_event_to_dict_has_no_raw_value_field() -> None:
    payload = FIXTURE_VALID_EXPOSURE.to_dict()
    assert "value" not in payload
    assert "content" not in payload
    assert payload["memory_hash"] == LANG_EN_HASH
    assert isinstance(payload["injected_to_context"], bool)


def test_memory_exposure_event_frozen() -> None:
    event = FIXTURE_VALID_EXPOSURE
    assert isinstance(event, MemoryExposureEvent)
    assert event.source == MemoryExposureSource.planner_prompt_injection
