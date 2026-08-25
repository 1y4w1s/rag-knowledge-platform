"""W10 E-A5 — execute frozen E-A4 formal window (plan-construction scope only)."""

from __future__ import annotations

import json

import pytest

from tests.w10_ea4_formal_window_contract import (
    ARTIFACT_KIND_FORMAL_RUN,
    C12_CASE_ID,
    CLASSIFICATION_INVALID,
    P2_R1_STATUS_BLOCKED,
    PROTOCOL_VERSION,
    RESERVED_RESULT_PATH,
    RUNNER_ID,
    execute_and_write_formal_window,
    validate_reserved_artifact,
)


@pytest.mark.asyncio
async def test_ea5_preflight_and_formal_window_write() -> None:
    assert RUNNER_ID == "w10_ea4_formal_window_runner"
    assert PROTOCOL_VERSION == "1.0.0"
    assert CLASSIFICATION_INVALID == "INVALID_FOR_PRODUCT_PATH_EXECUTION"
    assert P2_R1_STATUS_BLOCKED == "BLOCKED"

    path = await execute_and_write_formal_window()
    assert path == RESERVED_RESULT_PATH
    payload = json.loads(path.read_text(encoding="utf-8"))
    validate_reserved_artifact(payload)

    assert payload["runner_id"] == RUNNER_ID
    assert payload["protocol_version"] == PROTOCOL_VERSION
    assert len(payload["base_sha"]) >= 7
    assert payload["suite_id"] == "w9_critic_frozen_12"
    assert payload["artifact_kind"] == ARTIFACT_KIND_FORMAL_RUN
    assert payload["p2_r1_status"] == "BLOCKED"
    assert payload["does_not_unblock_p2_r1"] is True
    assert payload["measurement_validity"]["measurement_valid"] is True
    assert payload["eligibility_summary"]["product_path_eligible"] == 11
    assert payload["eligibility_summary"]["invalid_for_product_path"] == 1
    assert payload["eligibility_summary"]["c12_in_denominator"] is False

    c12 = next(item for item in payload["per_case_result"] if item["case_id"] == C12_CASE_ID)
    assert c12["classification"] == CLASSIFICATION_INVALID
    assert c12["executor_path"] == "refused_ineligible"
    assert c12["in_pass_rate_denominator"] is False
