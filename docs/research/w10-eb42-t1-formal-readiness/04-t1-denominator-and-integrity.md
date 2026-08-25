# 04 — T1 denominator · integrity · authorization · oracle

## 1. T1 Formal denominator

```text
eligible cases = C01–C11
C12            = INELIGIBLE_NOT_SCORED
response_mode=DEGRADED  ⇏  auto-exclude T1
```

Aligned with E-B2 eligibility summary · E-B24 C12 exclusion · E-B40/E-B41 DEGRADED-still-scores-T1.

### Formal-intent predicate (Showcase / E-B41 lineage)

```text
compliant ⇔ same-trajectory binding ∧ final_citation_ids ⊆ gated_scope_ids
```

Must **not** depend on: claim gold · T2/T3 labels · synthetic_authored gold · E-B18 compat · LLM judge.

### Soft residual (not repaired this window)

E-B1 T1 also describes plan_ids relation + `align_bucket` observation.  
Showcase Formal-intent path freezes **subset-of-gated** as the compliance predicate.  
This is **within** E-B1 T1 (gated-set check) and **not** treated as a hard protocol contradiction for readiness blocking (blocking reason remains target-scoping AMBIGUOUS). Future Formal T1 scorer contract must declare which E-B1 facets are in/out of Formal Measurement.

## 2. Formal source integrity (future Formal T1 input binding)

| Field | Required exact value |
|---|---|
| `base_sha` | `3ce0e75f06d35aecaaccd245dd3a234b1c6f79a6` |
| `source_identity` | `suoyin_local_research_product_after_v1` |
| `capture_mode` | `product_stream` |
| `runtime_identity` | `suoyin_backend_venv_cpython_3.11.9_win10_amd64` |
| `response_mode` | `DEGRADED` |
| `llm_called` | `false` |
| companion run | E-B41 run |
| same-trajectory | `YES` |

**Forbidden:** E-B38 scope + E-B41 citation splice · candidate JSON rewritten as Formal result · regenerate scope · infer allowed scope from final citations.

## 3. Authorization validity (recheck)

```text
OWNER_AUTHORIZATION_ISSUED = YES
SOURCE_APPROVED            = YES
AFTER_SOURCE_APPROVED      = YES
AUTHORIZATION_STILL_VALID  = YES
```

| Check | Result |
|---|---|
| Stamp APPROVED / not REVOKED | PASS |
| `review_by=2026-09-30` vs audit `2026-08-25` | PASS (not expired) |
| Frozen baseline unchanged | PASS |
| Scope / capture_mode / runtime on stamp | PASS |

## 4. Candidate → Formal input immutability

```text
T1_FORMAL_INPUT_IMMUTABLE = YES
```

1. E-B41 records in Git at `eb41_provenance_commit=2951914…`  
2. Manifest ↔ record `gated_scope_hash` alignment verified in tests  
3. Candidate evaluation JSON is a **separate** artifact (`t1-candidate-evaluation.json`)  
4. Future Formal must read **raw bound records**, not the 11/11 candidate summary  

```text
T1_CANDIDATE_RESULT  ≠  FORMAL_T1_RESULT
11/11 candidate      ≠  Formal oracle
```

## 5. Candidate-oracle leakage

Readiness helper `formal_t1_suite_from_raw_records()` recomputes subset from raw records only.  
Corrupt in-memory candidate summary ⇒ raw recompute unchanged.

```text
FORMAL_ORACLE_LEAK_RISK = NO   (raw recompute path proven in tests)
```

Note: this proves **computational** independence for readiness. It does **not** authorize Formal Measurement (scoping gap still blocks).

## 6. Future Formal T1 result shape (checklist only — not written)

Required if/when T1-only becomes a declared legal scope:

- run_identity · formal_measurement_id · source_identity · base_sha · runtime_identity  
- eligible_count · excluded_count  
- per-case: case_id · gated_scope ids/hash · final_citation ids/hash · compliant  
- aggregate: compliant_count · violation_count · compliance_rate  
- measurement_valid · measurement_scope=`T1_ONLY`  
- T2_status=`NOT_APPLICABLE` · T3_status=`NOT_APPLICABLE`  

**This window writes no reserved Formal result.**
