# 03 — Showcase Freeze Candidate Record

> Unified freeze **candidate** for Showcase Track (PRIMARY).  
> **`freeze_status = PENDING_HUMAN_CONFIRMATION`**.  
> **Forbidden in this window (DO NOT set):** achieved freeze_status value FROZEN · `HUMAN_FROZEN` tags as achieved.

## Provenance legend

| Tag | Meaning |
|---|---|
| `HUMAN_SUPPLIED_CANDIDATE` | Accepted by owner in dialogue · not yet confirmation-ticked |
| `REPOSITORY_VERIFIED_CANDIDATE` | Taken from committed research / design docs |
| `RUNTIME_OBSERVED_CANDIDATE` | Read-only observation this window |
| `DEFER_TO_BENCHMARK_TRACK` | Explicitly deferred · must not invent |
| `HUMAN_CONFIRMATION_REQUIRED` | Still needs owner tick / exact fill |

## Banner

```text
RECORD_KIND                  = SHOWCASE_FREEZE_CANDIDATE
freeze_status                = PENDING_HUMAN_CONFIRMATION
FREEZE_CANDIDATE_STATUS      = PENDING_HUMAN_CONFIRMATION
E-B35A_FREEZE_CANDIDATE_MATERIALIZED = YES
FROZEN                       = NO
SOURCE_APPROVED              = NO
CAPTURE_MODE_FROZEN          = NO
OWNER_AUTHORIZATION_ISSUED   = NO
```

## Candidate record

```text
================================================================
SHOWCASE FREEZE CANDIDATE — PENDING_HUMAN_CONFIRMATION
================================================================
track                    = SHOWCASE_TRACK (PRIMARY)
                           provenance: REPOSITORY_VERIFIED_CANDIDATE
                           · docs/research/w10-eb34-showcase-owner-freeze-review/

owner_identity           = suoyin_project_owner
                           provenance: HUMAN_SUPPLIED_CANDIDATE

source_identity          = suoyin_local_research_product_after_v1
                           provenance: HUMAN_SUPPLIED_CANDIDATE
after_source_id          = suoyin_local_research_product_after_v1
                           provenance: HUMAN_SUPPLIED_CANDIDATE
                           (exact match to source_identity)

product_name             = Suoyin / rag-knowledge-platform
                           provenance: HUMAN_SUPPLIED_CANDIDATE
product_version          = showcase-research-instance-v1
                           provenance: HUMAN_SUPPLIED_CANDIDATE
deployment_identity      = local_research_instance
                           provenance: HUMAN_SUPPLIED_CANDIDATE
environment_identity     = windows_local_research_environment
                           provenance: HUMAN_SUPPLIED_CANDIDATE

primary_candidate_source = A
                           provenance: REPOSITORY_VERIFIED_CANDIDATE
                           NOTE: selected design candidate only
                           ≠ Formal Evaluation Source
capture_path_identity    = eb15_harness_product_after_capture_path_a
                           provenance: REPOSITORY_VERIFIED_CANDIDATE
                           · E-B15 / E-B32 / E-B34 design path
                           ≠ Formal Evaluation Source

capture_mode_id          = product_stream
                           provenance: HUMAN_SUPPLIED_CANDIDATE
model_backend_identity   = none_no_llm
                           provenance: HUMAN_SUPPLIED_CANDIDATE
llm_called_expected      = false
                           provenance: HUMAN_SUPPLIED_CANDIDATE
generation_config_ref    = N/A
                           provenance: HUMAN_SUPPLIED_CANDIDATE

development_generation_backend = LM Studio
                           provenance: HUMAN_SUPPLIED_CANDIDATE
                           = Development Generation Backend only
                           ≠ Narrow Formal Primary
formal_model_identity    = DEFER_TO_BENCHMARK_TRACK
                           provenance: HUMAN_SUPPLIED_CANDIDATE
                           + DEFER_TO_BENCHMARK_TRACK
LOCAL_MODEL_FIRST        = YES
                           provenance: REPOSITORY_VERIFIED_CANDIDATE
LOCAL_MODEL_PINNED       = NO
                           provenance: REPOSITORY_VERIFIED_CANDIDATE
LOCAL_MODEL_AS_NARROW_FORMAL_PRIMARY = NO
                           provenance: REPOSITORY_VERIFIED_CANDIDATE

runtime_identity_candidate =
  suoyin_backend_venv_cpython_3.11.9_win10_amd64
                           provenance: RUNTIME_OBSERVED_CANDIDATE
RUNTIME_IDENTITY_CANDIDATE_READY = YES
runtime_identity frozen  = NO

observed_base_sha        = ef7170ae397c1292febc40f69905315e1b33d9af
                           provenance: RUNTIME_OBSERVED_CANDIDATE
proposed_base_sha        = ef7170ae397c1292febc40f69905315e1b33d9af
                           provenance: RUNTIME_OBSERVED_CANDIDATE
observed_branch          = test/agent-l4-w9-p3-e1-local-runtime-exploration
                           provenance: RUNTIME_OBSERVED_CANDIDATE
WORKING_TREE_CLEAN       = NO
BASE_SHA_CANDIDATE_READY = NO
BASE_SHA_FREEZE_READINESS = BLOCKED_PENDING_OWNER_REVIEW
base_sha_frozen          = NO
BASE_SHA_FROZEN          = NO

run_identity_pattern     = w10_showcase_narrow_*
                           provenance: HUMAN_SUPPLIED_CANDIDATE

review_policy_kind       = EVENT_TRIGGERED + REVIEW_BY
                           provenance: HUMAN_SUPPLIED_CANDIDATE
review_by                = <UNSET>
                           provenance: HUMAN_CONFIRMATION_REQUIRED
                           DO NOT invent date

provenance_class         = Product After
                           provenance: REPOSITORY_VERIFIED_CANDIDATE
                           = target evidence category only
                           ⇏ AFTER_SOURCE_APPROVED

DEPENDENCY_SNAPSHOT_PINNED = NO
                           provenance: RUNTIME_OBSERVED_CANDIDATE

freeze_status            = PENDING_HUMAN_CONFIRMATION
frozen_by                = <UNSET>
                           provenance: HUMAN_CONFIRMATION_REQUIRED
frozen_at                = <UNSET>
                           provenance: HUMAN_CONFIRMATION_REQUIRED
================================================================
```

## Authorization scope candidate (proposal · not frozen)

```text
AUTHORIZATION_SCOPE_CANDIDATE_READY = YES
AUTHORIZATION_SCOPE_FROZEN          = NO

Track:     Showcase Track (PRIMARY)
Binding:   BP-A
Suite:     w9_critic_frozen_12
Cases:     C01–C11
C12:       INELIGIBLE_NOT_SCORED
Excluded:
  - A4 live LLM
  - S2 empty-gate as Narrow T1–T3 After
  - synthetic / isomorphic After
  - E-B18 author-owned rebound as Formal After source
  - Development Generation Backend (LM Studio) as Formal Source
```

Provenance for scope shape: `REPOSITORY_VERIFIED_CANDIDATE` from E-B24–E-B34
design inheritance · still requires human confirm on freeze execution.

## Explicit non-achievements

```text
achieved freeze_status value FROZEN            = NO (forbidden here · DO NOT set)
SOURCE_IDENTITY_COMPLETE                       = NO
CAPTURE_MODE_FROZEN                            = NO
MAY_ISSUE_APPROVED_OWNER_STAMP                 = NO
OWNER_AUTHORIZATION_ISSUED                     = NO
SOURCE_APPROVED                                = NO
AFTER_SOURCE_APPROVED                          = NO
ACQUISITION_EXECUTION_READY                    = NO
E-B_FORMAL_READY                               = NO
FORMAL_OBSERVATION                             = NOT_STARTED
```

## Stamp (this file)

```text
SHOWCASE_FREEZE_CANDIDATE_RECORD_READY = YES
freeze_status                          = PENDING_HUMAN_CONFIRMATION
ANY_FIELD_MARKED_HUMAN_FROZEN          = NO
```
