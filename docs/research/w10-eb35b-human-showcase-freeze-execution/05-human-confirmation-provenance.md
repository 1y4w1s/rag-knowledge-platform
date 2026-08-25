# 05 — Human Confirmation Provenance

> Authority record for E-B35b ticks and FROZEN field fills.  
> **This confirmation is a human owner decision · not CI / pytest / Cursor derived.**

## 1. Authority identity

```text
confirming_party     = suoyin_project_owner
role                 = Human Owner / Showcase Track freeze authority
window               = E-B35b — Human Showcase Freeze Execution
confirmation_kind    = SHOWCASE_FREEZE_HUMAN_OWNER_AUTHORIZATION
confirmation_channel = Cursor chat · explicit owner message
confirmation_time    = 2026-08-25 (owner message)
frozen_at_recorded   = 2026-08-25T08:15:42Z
```

```text
HUMAN_AUTHORITY_DECLARED:
  This confirmation is a human owner decision.
  It is not:
    - CI-derived
    - pytest-derived
    - Cursor-derived
    - automatically inferred
```

## 2. Confirmed field set (verbatim authority)

| Field | Owner-confirmed value |
|---|---|
| `base_sha` | `3ce0e75f06d35aecaaccd245dd3a234b1c6f79a6` |
| `owner_identity` | `suoyin_project_owner` |
| `source_identity` | `suoyin_local_research_product_after_v1` |
| `after_source_id` | `suoyin_local_research_product_after_v1` |
| `product_name` | `Suoyin / rag-knowledge-platform` |
| `product_version` | `showcase-research-instance-v1` |
| `deployment_identity` | `local_research_instance` |
| `environment_identity` | `windows_local_research_environment` |
| `capture_mode_id` | `product_stream` |
| `runtime_identity` | `suoyin_backend_venv_cpython_3.11.9_win10_amd64` |
| `model_backend_identity` | `none_no_llm` |
| `llm_called_expected` | `false` |
| `generation_config_ref` | `N/A` |
| `run_identity_pattern` | `w10_showcase_narrow_*` |
| `development_generation_backend` | `LM Studio` |
| `formal_model_identity` | `DEFER_TO_BENCHMARK_TRACK` |
| `LOCAL_MODEL_FIRST` | `YES` |
| `LOCAL_MODEL_PINNED` | `NO` |
| `LOCAL_MODEL_AS_NARROW_FORMAL_PRIMARY` | `NO` |
| `review_policy_kind` | `EVENT_TRIGGERED + REVIEW_BY` |
| `review_by` | `2026-09-30` |
| `on_trigger` | `REVOKE_OR_REISSUE` |

## 3. Authorization scope (owner-confirmed)

```text
Track:     Showcase Track
Binding:   BP-A
Suite:     w9_critic_frozen_12
Measured:  C01–C11
C12:       INELIGIBLE_NOT_SCORED
Excluded from Narrow T1–T3 denominator:
  - A4 live LLM
  - S2 empty-gate companion
  - synthetic/isomorphic After
  - E-B18 author-owned rebound
  - Development Backend substituted as Formal Source
```

## 4. Anti-contamination acknowledgement (owner)

```text
[x] synthetic After must not be relabeled Product After
[x] E-B18 author-owned rebound must not be relabeled Product After
[x] Development Backend output must not be silently substituted as Formal Source
[x] provenance_class=Product After names a target evidence category only
[x] tracked Empty-gate/S2 assets do not enter the current BP-A T1–T3 denominator
[x] PRIMARY_CANDIDATE_SOURCE=A does not by itself imply source approval
[x] LM Studio Development Backend ≠ Formal Evaluation Source
[x] historical E-A4 artifact ≠ this freeze base_sha ≠ Formal Observation
```

## 5. Baseline acknowledgements (owner)

```text
[x] WORKING_TREE_CLEAN = YES at baseline materialization (E-B35a.3)
[x] BASE_SHA_PROTOCOL_COVERAGE = COMPLETE
[x] FREEZE_BASELINE_REPRODUCIBILITY_GAP = NO
[x] pinned E-A4 historical artifact retains historical internal base_sha
```

## 6. Permitted vs forbidden gate flips (owner)

```text
PERMITTED if predicates pass:
  SOURCE_IDENTITY_COMPLETE = YES
  CAPTURE_MODE_FROZEN      = YES
  BASE_SHA_FROZEN          = YES
  HUMAN_CHECKLIST_COMPLETE = YES

FORBIDDEN in E-B35b (must remain NO):
  MAY_ISSUE_APPROVED_OWNER_STAMP = NO
  OWNER_AUTHORIZATION_ISSUED     = NO
  SOURCE_APPROVED                = NO
  AFTER_SOURCE_APPROVED          = NO
  ACQUISITION_EXECUTION_READY    = NO
  E-B_FORMAL_READY               = NO
```

## 7. Stamp (this file)

```text
HUMAN_CONFIRMATION_PROVENANCE_RECORDED = YES
HUMAN_AUTHORITY                        = suoyin_project_owner
CONFIRMATION_NOT_CI_DERIVED            = YES
CONFIRMATION_NOT_PYTEST_DERIVED        = YES
CONFIRMATION_NOT_CURSOR_INFERRED       = YES
```
