# 04 — Real After Binding v2 (`w10_eb40_real_after_binding_v1`)

```text
REAL_AFTER_BINDING_V2_IMPLEMENTED = YES
binding_schema                    = REAL_AFTER_BINDING_V2
forbids_eb18_compat_for_product   = YES
```

## Wrapper fields (per case)

```text
case_id
gold_ledger_hash              # from human gold · labels unchanged
real_observed_content_hash    # E-B38 utf8 observed hash
evidence_pool_hash            # from Product After citations (chunk_id+excerpt)
response_mode
bp_class_v2
provenance_bound
t2_t3_scorer_eligible
```

## Rules

- Does **not** modify human gold labels or E-B38 After bodies.
- Does **not** use E-B18 author-owned compatibility pack.
- Gold Ledger ≠ speech-act proof (still respected).
- `response_mode=DEGRADED` → provenance may bind; `T2_T3_SCORER_ELIGIBLE=NO`.
- `response_mode=ANSWER` → necessary for eligibility; still requires `gold.kind=observed_after`.

## E-B38 result

```text
provenance_bound (C01–C11)     = YES (11/11)
t2_t3_scorer_eligible          = NO  (11/11 · all DEGRADED)
T2_EB38_APPLICABILITY          = NOT_APPLICABLE
T3_EB38_APPLICABILITY          = NOT_APPLICABLE
```

NOT_APPLICABLE is neither failure nor pass.
