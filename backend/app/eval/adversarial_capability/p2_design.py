"""ADVERSARIAL P2 real measurement protocol — design freeze (no LLM run)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

STAGE = "ADVERSARIAL_REAL_MEASUREMENT_PROTOCOL_P2_FREEZE"
DESIGN_REL = Path(
    "tests/fixtures/l4_adversarial_capability/adversarial-real-measurement-protocol-p2-design.json"
)

ROUND_START_MASTER_SHA = "32c8830e92990a00d7824f0145c7cda3ba639fd7"
P1_MERGE_SHA = ROUND_START_MASTER_SHA

PRIMARY_CAPABILITY_CASE_IDS: tuple[str, ...] = (
    "ADV-P1-ANS-001",
    "ADV-P1-UNA-001",
    "ADV-P1-PART-001",
    "ADV-P1-CON-001",
)

LAYER_R = {
    "name": "REAL_RETRIEVAL_VALIDATION",
    "engine": "production hybrid retriever against frozen P1 corpus fixtures",
    "readiness": "READY",
    "requirements": [
        "corpus_fingerprint match before run",
        "scoped kb_id per corpus_fixture_id",
        "index + embed + chunker config frozen in sidecar manifest",
        "retrieval behavior logged independently of answerability label",
    ],
    "forbidden_claims": [
        "always_topk_hit_equals_retriever_false_positive",
        "empty_hit_equals_capability_pass",
    ],
}

LAYER_A = {
    "name": "REAL_LOCAL_AGENT_CAPABILITY",
    "model": "zai-org/glm-4.6v-flash",
    "thinking": "OFF",
    "readiness": "READY_AFTER_R",
    "runner_profile": "local_agent_trajectory harness (same family as MEMORY P3)",
    "requirements": [
        "P1 CAPABILITY_VALID_DENOMINATOR > 0",
        "P0 8-stage evaluator with first_failed_stage",
        "no product remediation during measurement",
    ],
}

CONTROLS = [
    "HC-ALWAYS-REFUSE",
    "HC-ALWAYS-ANSWER",
    "HC-ALWAYS-RETRIEVE",
    "HC-NO-RETRIEVAL",
]

SUCCESS_LABELS = {
    "case_pass": "all applicable P0 stages pass (first_failed_stage=null)",
    "aggregate": "passed / CAPABILITY_VALID_DENOMINATOR",
    "blocked_when": "CAPABILITY_VALID_DENOMINATOR=0",
}

ANSWERABILITY_INVARIANT = {
    "source": "ANSWERABILITY_TRUTH",
    "derived_from": [
        "frozen fact registry",
        "corpus contract (fingerprint + absent propositions)",
    ],
    "not_derived_from": [
        "top-k retrieval hits",
        "embedding scores",
        "model outputs",
        "retriever rank alone",
    ],
}

MODEL_CONFIG = {
    "model": "zai-org/glm-4.6v-flash",
    "thinking": "OFF",
    "context_tokens": 8192,
    "temperature": 0,
    "timeout_seconds": 90,
    "warmup_trials": 3,
    "single_model_residency": True,
    "no_lm_studio_in_pr": True,
    "no_cloud_llm": True,
}


def build_p2_design(*, p1_denominator: int, p1_merge_sha: str) -> dict[str, Any]:
    blocked = p1_denominator <= 0
    return {
        "schema_version": "adversarial-real-measurement-protocol-p2-freeze-v1",
        "stage": STAGE,
        "round_start_master_sha": ROUND_START_MASTER_SHA,
        "p1_merge_sha": p1_merge_sha,
        "p1_denominator": p1_denominator,
        "CAPABILITY_VALID_DENOMINATOR": p1_denominator,
        "primary_capability_cases": list(PRIMARY_CAPABILITY_CASE_IDS),
        "state": "BLOCKED_BY_P1" if blocked else "FROZEN",
        "adv_p2": "PASS/FROZEN" if not blocked else "BLOCKED",
        "ready_for_real_run": not blocked,
        "real_run_executed_in_pr": False,
        "runtime_rollout": False,
        "product_remediation": False,
        "answerability_invariant": ANSWERABILITY_INVARIANT,
        "pipeline": [
            "VALID_CORPUS (P1 frozen fixtures)",
            "REAL_RETRIEVAL (Layer R)",
            "REAL_LOCAL_AGENT (Layer A, GLM-4.6V-Flash Thinking OFF)",
            "P0_STAGE_EVALUATOR (first_failed_stage)",
        ],
        "layer_R": LAYER_R,
        "layer_A": LAYER_A,
        "controls": CONTROLS,
        "controls_role": "evaluator_sanity_checks_not_primary_denominator",
        "success_labels": SUCCESS_LABELS,
        "sample_policy": {
            "deterministic_first": True,
            "full_denominator_before_sampling": True,
            "min_per_corpus_class": 1,
        },
        "model_config": MODEL_CONFIG,
        "non_goals": [
            "no remediation design",
            "no Golden rewrite",
            "no runtime rollout",
        ],
    }
