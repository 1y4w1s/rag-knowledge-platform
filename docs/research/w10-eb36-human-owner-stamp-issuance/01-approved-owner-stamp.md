# 01 — Canonical APPROVED Owner Stamp (`eb30_owner_stamp_v1`)

> **CANONICAL ARTIFACT** — exactly one APPROVED Owner Stamp for this
> Showcase Narrow chain.  
> Do not create a second conflicting APPROVED stamp.

```text
================================================================
OWNER STAMP — APPROVED
stamp_kind                 = OWNER_AFTER_SOURCE_APPROVAL
schema_version             = eb30_owner_stamp_v1
authorization_status       = APPROVED
auto_derived               = false
issuer_class               = human_owner
================================================================

owner_identity             = suoyin_project_owner

source_identity            = suoyin_local_research_product_after_v1
after_source_id            = suoyin_local_research_product_after_v1
                           (exact match to source_identity)

capture_mode               = product_stream
model_backend_identity     = none_no_llm
runtime_identity           = suoyin_backend_venv_cpython_3.11.9_win10_amd64
base_sha                   = 3ce0e75f06d35aecaaccd245dd3a234b1c6f79a6
run_identity               = w10_showcase_narrow_*
                           (explicit allowlist pattern · E-B35b frozen)

authorization_scope:
  observation_track        = Showcase Track
  binding_policy           = BP-A (observed_after)
  suite_id                 = w9_critic_frozen_12
  cases_covered            = C01..C11
  c12_policy               = INELIGIBLE_NOT_SCORED
  primary_candidate_ref    = E-B27 Option A
                           (selected design candidate only
                            ≠ Formal Evaluation Source alone)
  capture_path_identity    = eb15_harness_product_after_capture_path_a
  formal_source_claim      = false
  excludes                 =
    - A4 live LLM
    - S2 empty-gate companion from Narrow T1–T3 denominator
    - synthetic/isomorphic After
    - E-B18 author-owned rebound
    - Development Backend substituted as Formal Source

issued_at                  = 2026-08-25T08:33:45Z
                           (issuance-event wall-clock UTC
                            ≠ frozen_at · not backfilled · not fixture)

expiration_or_review_policy:
  policy_kind              = EVENT_TRIGGERED + REVIEW_BY
  review_by                = 2026-09-30
  expires_at               = null
  on_trigger               = REVOKE_OR_REISSUE
  max_silent_reuse         = 0
  trigger_events           =
    [base_sha_change, capture_mode_change,
     model_backend_change, runtime_identity_change,
     scope_change]

approval_statement         =
  "APPROVED for Narrow Formal After denom (Showcase Track)"

source_model_separation    = YES
source_model_separation_acknowledged = true
anti_contamination_acknowledged      = true

llm_called_expected        = false
generation_config_ref      = N/A

formal_model_identity      = DEFER_TO_BENCHMARK_TRACK
                           (honesty residual · NOT concrete Formal Model pin
                            · NOT issuance blocker under none_no_llm)

dependency_snapshot        = EXPLICITLY_UNPINNED_SHOWCASE
DEPENDENCY_SNAPSHOT_PINNED = NO
classification             = SHOWCASE_REPRODUCIBILITY_LIMITATION
NOT_ISSUANCE_BLOCKER       = YES

----------------------------------------------------------------
BASELINE NOTE
  Frozen/authorized evaluation baseline = base_sha above.
  Documentation commits after E-B35b/E-B36 may move HEAD;
  they MUST NOT rewrite this stamp base_sha.

HISTORICAL SEPARATION
  fixtures/l4_critic/w10-ea4-formal-window-result.json
    = E-A4/E-A5 historical parent artifact
    ≠ this stamp base_sha
    ≠ current Formal Observation
================================================================
```

## Integrity summary (this artifact)

```text
schema_version             = eb30_owner_stamp_v1     OK
authorization_status       = APPROVED                OK
auto_derived               = false                   OK
owner_identity             = suoyin_project_owner    OK (matches freeze)
source / after_source_id   match E-B35b              OK
capture_mode / runtime / base_sha / scope            OK
review_policy / acknowledgements                     OK
issued_at ISO-8601 UTC issuance event                OK
no concrete Formal Model silently pinned             OK
```
