# 03 — Acquisition run manifest

Machine-readable twin: [`acquisition-run-manifest.json`](acquisition-run-manifest.json).

## Run identity

```text
run_identity = w10_showcase_narrow_eb38_20260825T085526Z
pattern_match (w10_showcase_narrow_*) = YES
started_at   = 2026-08-25T08:55:30Z
completed_at = 2026-08-25T08:55:30Z
(clock = real UTC wall clock)
```

## Suite binding

```text
suite_id                 = w9_critic_frozen_12
binding_policy           = observed_after (BP-A)
base_sha                 = 3ce0e75f06d35aecaaccd245dd3a234b1c6f79a6
authorization_record_commit = bd23448f561a541ba6bed7fa1308c3f7de3f6236
source_identity          = suoyin_local_research_product_after_v1
after_source_id          = suoyin_local_research_product_after_v1
capture_mode             = product_stream
model_backend_identity   = none_no_llm
runtime_identity         = suoyin_backend_venv_cpython_3.11.9_win10_amd64
capture_path_identity    = eb15_harness_product_after_capture_path_a
harness_entry            = capture_frozen_case_product_after
```

## Counts

```text
eligible_count  = 11
attempted_count = 11
captured_count  = 11
failed_count    = 0
excluded_count  = 1
```

## Per-case status (C01–C12)

| Case | Status | Submode | llm_called_observed | citations |
|---|---|---|---|---|
| C01 | CAPTURED | product_stream_degraded | false | 1 |
| C02 | CAPTURED | product_stream_degraded | false | 1 |
| C03 | CAPTURED | product_stream_degraded | false | 1 |
| C04 | CAPTURED | product_stream_degraded | false | 1 |
| C05 | CAPTURED | product_stream_degraded | false | 2 |
| C06 | CAPTURED | product_stream_degraded | false | 1 |
| C07 | CAPTURED | product_stream_degraded | false | 1 |
| C08 | CAPTURED | product_stream_degraded | false | 1 |
| C09 | CAPTURED | product_stream_degraded | false | 1 |
| C10 | CAPTURED | product_stream_degraded | false | 2 |
| C11 | CAPTURED | product_stream_degraded | false | 1 |
| C12 | INELIGIBLE_NOT_SCORED | — | false | — |

C12 was **not** acquisition-attempted; recorded only as ineligible.

## Provider key handling (process-local)

```text
Cleared for acquisition process only (not persisted):
  DEEPSEEK_API_KEY / TONGYI_API_KEY / DASHSCOPE_API_KEY /
  OPENAI_API_KEY / ANTHROPIC_API_KEY / LM_STUDIO_API_KEY
E-B15 force_zero_llm additionally forces empty keys + forbids stream_deepseek_tokens
```
