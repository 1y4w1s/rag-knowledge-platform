# 03 — T1 Formal measurement

## Predicate (per eligible case)

```text
compliant = set(final_citation_ids) ⊆ set(gated_scope_ids)
violation_ids = final_citation_ids - gated_scope_ids
```

No fuzzy match · no LLM judge · no NLI · no gold claim dependency.

## Aggregate (Formal)

```text
eligible_count   = 11
excluded_count   = 1  (C12)
compliant_count  = 11
violation_count  = 0
compliance_rate  = 1.0  (100%)
```

## Per-case summary

| Case | Compliant | Violation IDs |
|---|---|---|
| C01 | YES | — |
| C02 | YES | — |
| C03 | YES | — |
| C04 | YES | — |
| C05 | YES | — |
| C06 | YES | — |
| C07 | YES | — |
| C08 | YES | — |
| C09 | YES | — |
| C10 | YES | — |
| C11 | YES | — |
| C12 | N/A | excluded `INELIGIBLE_NOT_SCORED` |

Full per-case fields (hashes, ids, binding) → [`formal-t1-result.json`](formal-t1-result.json).

## Targets

```text
T1 status = MEASURED
T2 status = NOT_APPLICABLE
T3 status = NOT_APPLICABLE
```

`NOT_APPLICABLE` ≠ PASS ≠ FAIL ≠ 100%.

## Measurement identity

```text
formal_measurement_id = w10_t1_formal_20260825T101800Z
measured_at           = 2026-08-25T10:18:00Z
```

Distinct from E-B41 `companion_run` id (not reused).
