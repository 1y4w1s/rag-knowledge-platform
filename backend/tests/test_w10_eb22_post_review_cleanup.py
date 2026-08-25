"""W10 E-B22 post-review cleanup invariants (no new capability).

Confirms freeze after Formal Wireup Contract review cleanup:
E-B_FORMAL_READY=NO · reserved result absent · L-Obs has no rates ·
L-Score remains companion-only. Does not enter formal observation.
"""

from __future__ import annotations

from tests.w10_eb2_generation_observation_contract import RESERVED_RESULT_PATH
from tests.w10_eb22_formal_wireup_contract import (
    E_B_FORMAL_READY,
    FORMAL_WIREUP_IMPLEMENTED,
    L_SCORE_ARTIFACT_KIND,
    MAY_ENTER_FORMAL_OBSERVATION_WINDOW,
    build_l_obs_skeleton,
    build_l_score_companion,
    sample_scorer_result_for_wireup,
)


def test_eb22_post_review_cleanup_invariants() -> None:
    assert E_B_FORMAL_READY == "NO"
    assert MAY_ENTER_FORMAL_OBSERVATION_WINDOW == "NO"
    assert FORMAL_WIREUP_IMPLEMENTED == "YES"
    assert not RESERVED_RESULT_PATH.exists()

    run_id = "CLEANUP_eb22_not_formal"
    base_sha = "c" * 40
    l_obs = build_l_obs_skeleton(run_id=run_id, base_sha=base_sha)
    assert "t2" not in l_obs
    assert "t3" not in l_obs
    assert "unsupported_rate" not in l_obs
    assert "grounded_rate" not in l_obs
    for case in l_obs["per_case_observation"]:
        assert "t2" not in case
        assert "t3" not in case
        assert "unsupported_rate" not in case
        assert "grounded_rate" not in case
    assert l_obs["measurement_validity"]["measurement_valid"] is False

    scorer = sample_scorer_result_for_wireup()
    assert "unsupported_rate" in scorer["cases"][0]["t2"]
    assert "grounded_rate" in scorer["cases"][0]["t3"]

    l_score = build_l_score_companion(
        scorer_result=scorer,
        parent_run_id=run_id,
        parent_base_sha=base_sha,
    )
    assert l_score["artifact_kind"] == L_SCORE_ARTIFACT_KIND
    assert l_score["formal_measurement"] is False
    assert l_score["implementation_only"] is True
    assert l_score["parent_run_id"] == run_id
    assert "t2" in l_score and "t3" in l_score
    assert not RESERVED_RESULT_PATH.exists()
