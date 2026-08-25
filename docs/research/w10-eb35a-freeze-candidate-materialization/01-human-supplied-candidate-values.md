# 01 — Human-Supplied Candidate Values

> Values accepted by the human owner in dialogue **prior to this window**.  
> Provenance for every row below: **`HUMAN_SUPPLIED_CANDIDATE`**.  
> **`HUMAN_SUPPLIED_CANDIDATE ≠ HUMAN_FROZEN`**.

## 1. Accepted Showcase Narrow candidates

| Field | Candidate value | Provenance |
|---|---|---|
| `owner_identity` | `suoyin_project_owner` | HUMAN_SUPPLIED_CANDIDATE |
| `source_identity` | `suoyin_local_research_product_after_v1` | HUMAN_SUPPLIED_CANDIDATE |
| `after_source_id` | `suoyin_local_research_product_after_v1` | HUMAN_SUPPLIED_CANDIDATE |
| `product_name` | `Suoyin / rag-knowledge-platform` | HUMAN_SUPPLIED_CANDIDATE |
| `product_version` | `showcase-research-instance-v1` | HUMAN_SUPPLIED_CANDIDATE |
| `deployment_identity` | `local_research_instance` | HUMAN_SUPPLIED_CANDIDATE |
| `environment_identity` | `windows_local_research_environment` | HUMAN_SUPPLIED_CANDIDATE |
| `capture_mode_id` | `product_stream` | HUMAN_SUPPLIED_CANDIDATE |
| `model_backend_identity` | `none_no_llm` | HUMAN_SUPPLIED_CANDIDATE |
| `llm_called_expected` | `false` | HUMAN_SUPPLIED_CANDIDATE |
| `generation_config_ref` | `N/A` | HUMAN_SUPPLIED_CANDIDATE |
| `development_generation_backend` | `LM Studio` | HUMAN_SUPPLIED_CANDIDATE |
| `formal_model_identity` | `DEFER_TO_BENCHMARK_TRACK` | HUMAN_SUPPLIED_CANDIDATE + DEFER_TO_BENCHMARK_TRACK |
| `run_identity_pattern` | `w10_showcase_narrow_*` | HUMAN_SUPPLIED_CANDIDATE |
| `review_policy_kind` | `EVENT_TRIGGERED + REVIEW_BY` | HUMAN_SUPPLIED_CANDIDATE |

## 2. Explicitly **not** confirmed by human (still open)

| Field | State | Provenance |
|---|---|---|
| `review_by` (exact date) | unset | HUMAN_CONFIRMATION_REQUIRED |
| `base_sha` as **frozen** value | unset (observation only in `02`) | HUMAN_CONFIRMATION_REQUIRED |
| `runtime_identity` as **frozen** value | unset (observation candidate in `02`) | HUMAN_CONFIRMATION_REQUIRED |
| `authorization_scope` as **frozen** value | unset (scope **proposal** in `03`) | HUMAN_CONFIRMATION_REQUIRED |
| anti-contamination acknowledgement | unticked | HUMAN_CONFIRMATION_REQUIRED |

## 3. Alignment with E-B34 Showcase strategy

These human-supplied candidates align with E-B34:

- `SHOWCASE_TRACK = PRIMARY`
- `RESEARCH_BENCHMARK_TRACK = LONG_TERM` (not executed)
- `LOCAL_MODEL_FIRST = YES` · `LOCAL_MODEL_PINNED = NO`
- `LOCAL_MODEL_AS_NARROW_FORMAL_PRIMARY = NO`
- LM Studio = Development Generation Backend **≠** Narrow Formal Primary
- `formal_model_identity` deferred (not invented)
- Capture honesty tendency `product_stream` + `none_no_llm` (now owner-accepted as **candidate**, still not frozen)

## 4. Stamp (this file)

```text
HUMAN_SUPPLIED_CANDIDATES_RECORDED = YES
ANY_FIELD_HUMAN_FROZEN             = NO
review_by_exact_date_filled        = NO
```
