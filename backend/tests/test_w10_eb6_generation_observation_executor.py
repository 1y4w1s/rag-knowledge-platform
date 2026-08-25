"""W10 E-B6 — After observation executor deterministic tests (no LLM / no formal run)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.w10_eb2_generation_observation_contract import (
    EA5_RESULT_PATH,
    OBSERVATION_POINT,
    RESERVED_RESULT_FILENAME,
    RESERVED_RESULT_PATH,
    GenerationObservationContractError,
    assert_reserved_result_absent,
    validate_reserved_artifact,
)
from tests.w10_eb6_generation_observation_executor import (
    CAPTURE_MODE_ISOMORPHIC,
    SYNTHETIC_BODY_PREFIX,
    AfterObservationSnapshot,
    GenerationObservationExecutorError,
    assert_formal_reserved_result_absent,
    author_owned_synthetic_content,
    build_smoke_observation_artifact,
    git_base_sha,
    observe_case,
    run_isomorphic_observation_suite,
    validate_observation_artifact,
    write_observation_artifact,
)
from tests.w10_ea2_scope_eligibility import load_frozen_suite


@pytest.mark.asyncio
async def test_observation_point_is_generation_final() -> None:
    snapshots = await run_isomorphic_observation_suite()
    payload = build_smoke_observation_artifact(snapshots, base_sha=git_base_sha())
    assert payload["observation_point"] == OBSERVATION_POINT
    assert payload["observation_point"] == "generation_final_content_and_citations"
    validate_reserved_artifact(payload)


@pytest.mark.asyncio
async def test_isomorphic_path_captures_before_after_and_hashes() -> None:
    suite = load_frozen_suite()
    case = next(c for c in suite.cases if c["case_id"].startswith("C01"))
    with pytest.MonkeyPatch.context() as mp:
        snap = await observe_case(mp, case)

    assert isinstance(snap, AfterObservationSnapshot)
    assert snap.eligibility is True
    assert snap.capture_mode == CAPTURE_MODE_ISOMORPHIC
    assert snap.llm_called is False
    assert snap.gen_plan_reference is not None
    assert snap.before_gen_plan_hash == snap.gen_plan_reference
    assert snap.before_gen_plan_hash.startswith("sha256:")
    assert snap.after_content is not None
    assert snap.after_content.startswith(SYNTHETIC_BODY_PREFIX)
    assert snap.after_content != case["answer"]
    assert snap.after_content_hash is not None
    assert snap.after_citations is not None
    assert snap.after_citations_hash is not None
    assert snap.plan_refusal is False
    assert snap.refusal_observation_status == "OBSERVED_SLOT"
    assert snap.state["content"] == snap.after_content
    assert snap.state["citations"] == list(snap.after_citations)


@pytest.mark.asyncio
async def test_c12_stays_ineligible_without_fabricated_after() -> None:
    suite = load_frozen_suite()
    case = next(c for c in suite.cases if c["case_id"] == "C12-out-of-scope-provenance")
    with pytest.MonkeyPatch.context() as mp:
        snap = await observe_case(mp, case)
    assert snap.eligibility is False
    assert snap.after_content is None
    assert snap.after_citations is None
    assert snap.gen_plan_reference is None
    assert snap.refusal_observation_status == "INELIGIBLE"
    assert snap.grounding_observation_status == "INELIGIBLE"


@pytest.mark.asyncio
async def test_ea5_artifact_cannot_be_accepted() -> None:
    assert EA5_RESULT_PATH.exists()
    ea5 = json.loads(EA5_RESULT_PATH.read_text(encoding="utf-8"))
    with pytest.raises(GenerationObservationExecutorError):
        validate_observation_artifact(ea5)
    with pytest.raises(GenerationObservationContractError):
        validate_reserved_artifact(ea5)


@pytest.mark.asyncio
async def test_p2_r3_and_critic_oracle_shapes_rejected() -> None:
    snapshots = await run_isomorphic_observation_suite()
    payload = build_smoke_observation_artifact(snapshots, base_sha=git_base_sha())

    bad_r3 = dict(payload)
    bad_r3["per_case_result"] = payload["per_case_observation"]
    with pytest.raises(GenerationObservationExecutorError):
        validate_observation_artifact(bad_r3)

    bad_critic = dict(payload)
    bad_critic["expected_action"] = "REFUSE"
    with pytest.raises(GenerationObservationExecutorError):
        validate_observation_artifact(bad_critic)

    bad_runner = dict(payload)
    bad_runner["runner_id"] = "w9_critic_p2_r3_formal_runner"
    with pytest.raises(GenerationObservationExecutorError):
        validate_observation_artifact(bad_runner)


@pytest.mark.asyncio
async def test_synthetic_path_cannot_claim_formal_result(tmp_path: Path) -> None:
    snapshots = await run_isomorphic_observation_suite()
    payload = build_smoke_observation_artifact(snapshots, base_sha=git_base_sha())

    assert payload["measurement_validity"]["measurement_valid"] is False
    assert payload["measurement_validity"]["llm_called"] is False
    assert "T1" in payload["eligibility_summary"]["targets_measured"]
    assert payload["p2_r1_status"] == "BLOCKED"

    forged = dict(payload)
    forged["measurement_validity"] = dict(payload["measurement_validity"])
    forged["measurement_validity"]["measurement_valid"] = True
    forged["measurement_validity"]["invalid_reasons"] = []
    out = tmp_path / "eb6-smoke.json"
    with pytest.raises(GenerationObservationExecutorError, match="formal"):
        write_observation_artifact(forged, out)

    written = write_observation_artifact(payload, out)
    assert written.exists()
    assert written.name != RESERVED_RESULT_FILENAME

    with pytest.raises(GenerationObservationExecutorError, match="reserved"):
        write_observation_artifact(payload, RESERVED_RESULT_PATH)

    assert_reserved_result_absent()
    assert_formal_reserved_result_absent()
    assert not RESERVED_RESULT_PATH.exists()


def test_author_owned_body_never_equals_fixture_answer_by_construction() -> None:
    suite = load_frozen_suite()
    for case in suite.cases:
        case_id = str(case["case_id"])
        if case_id.startswith("C12"):
            continue
        body = author_owned_synthetic_content(case_id, gated_count=1)
        assert body != case["answer"]
        assert SYNTHETIC_BODY_PREFIX in body
