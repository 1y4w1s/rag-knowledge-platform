# 03 — T1 companion run manifest

## Authorization revalidation (before run)

| # | Check | Result |
|---|---|---|
| 1 | `OWNER_AUTHORIZATION_ISSUED` | **YES** |
| 2 | `SOURCE_APPROVED` / `AFTER_SOURCE_APPROVED` | **YES** |
| 3 | frozen `base_sha` exact `3ce0e75…` | **PASS** |
| 4 | `source_identity` unchanged | **PASS** |
| 5 | capture path `eb15_harness_product_after_capture_path_a` | **PASS** |
| 6 | `capture_mode=product_stream` | **PASS** |
| 7 | runtime identity match | **PASS** |
| 8 | authorization scope unchanged (C01–C11 · C12 INELIGIBLE) | **PASS** |
| 9 | stamp not revoked · `APPROVED` · `auto_derived=false` | **PASS** |
| 10 | `review_by=2026-09-30` not exceeded (run 2026-08-25) | **PASS** |
| 11 | no contamination trigger | **PASS** |

```text
AUTHORIZATION_STILL_VALID = YES
```

## Run identity

```text
parent_acquisition_run = w10_showcase_narrow_eb38_20260825T085526Z
companion_run          = w10_showcase_narrow_eb41_t1_20260825T094148Z
pattern match          = w10_showcase_narrow_*     YES
E-B41 does not overwrite E-B38 After records
```

## Capture semantics

```text
capture_mode            = product_stream
model_backend_identity  = none_no_llm
llm_called_observed     = false
response_mode (C01–C11) = DEGRADED (allowed; T1 is scope compliance)
```

## Counts

```text
eligible   = 11
attempted  = 11
captured   = 11
failed     = 0
excluded   = 1 (C12 INELIGIBLE_NOT_SCORED)
```

Machine-readable: `companion-run-manifest.json`
