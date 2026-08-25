# W10 E-B44 — T1 Formal Measurement Execution

> **Formal Measurement** under frozen scope `w10_showcase_t1_only_v1`.  
> Recomputes T1 from immutable E-B41 raw companion records only.  
> Does **not** use candidate aggregates as oracle · does **not** modify `backend/app` / raw input.

## Verdict

```text
W10_T1_FORMAL_MEASUREMENT_COMPLETE
FORMAL_T1_MEASUREMENT_EXECUTED = YES
FORMAL_T1_MEASUREMENT_VALID     = YES
T1 Formal                       = 11/11 compliant
Compliance Rate                 = 100%
```

## Identity

| Field | Value |
|---|---|
| `eb43_protocol_commit` | `07a0dcbea9b676c297f45ef0a6edc54831c4ad16` |
| `formal_measurement_id` | `w10_t1_formal_20260825T101800Z` |
| `measured_at` | `2026-08-25T10:18:00Z` |
| `measurement_scope_id` | `w10_showcase_t1_only_v1` |
| `base_sha` | `3ce0e75f06d35aecaaccd245dd3a234b1c6f79a6` |
| `input_run_identity` | `w10_showcase_narrow_eb41_t1_20260825T094148Z` |

## Documents

| File | Content |
|---|---|
| [`01-formal-entry-preflight.md`](01-formal-entry-preflight.md) | Entry gate revalidation |
| [`02-formal-input-binding.md`](02-formal-input-binding.md) | Raw input identity |
| [`03-t1-formal-measurement.md`](03-t1-formal-measurement.md) | Per-case Formal computation |
| [`04-formal-integrity-audit.md`](04-formal-integrity-audit.md) | Oracle isolation · uniqueness |
| [`05-eb44-verdict.md`](05-eb44-verdict.md) | Final stamp + stop |
| [`formal-t1-result.json`](formal-t1-result.json) | Canonical machine-readable result |

## Hard locks honored

```text
Raw records only — candidate summary NOT used as oracle
C12 excluded before denominator (eligible=11, excluded=1)
T2/T3 = NOT_APPLICABLE (≠ PASS / 100% / zero-denom)
No LLM / API / LM Studio
No backend/app / frozen baseline / E-B41 raw mutation
Historical E-B_FORMAL_READY remains NO
```

## Tests

```text
pytest backend/tests/test_w10_eb44_t1_formal_measurement.py -q
→ 17 passed
```
