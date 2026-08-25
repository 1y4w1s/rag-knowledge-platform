# 02 — Target case selection

> Selects and freezes the **case set** and **measurement targets** for the
> first Narrow Formal Observation. Design stamp only — not an execution unlock.

## 1. Suite and identity

| Field | Value |
|---|---|
| `suite_id` | `w9_critic_frozen_12` |
| Envelope `case_count` | `12` |
| Case ids | C01 … C12 (frozen W9 identity) |
| Claim gold parent | E-B12B ledger (`E_B_CLAIM_GOLD_ANNOTATED=YES`) |

## 2. Measured vs excluded cases

### 2.1 Measured (Narrow Formal denom)

| Case range | Role |
|---|---|
| **C01–C11** | Eligible slots for T1 / T2 / T3 under BP-A once After + rebound gold bind |

Rationale:

- E-B12B claim gold annotates **C01–C11** claim texts into the T2/T3 denominator  
- Product / harness After paths treat these eleven as product-path-valid slots  
- Narrow Formal keeps the same eleven as the **only** scored claim cases  

### 2.2 Excluded from measurement

| Case | Status in Narrow Formal | Rule |
|---|---|---|
| **C12** | **Excluded** | Remain in envelope as `INELIGIBLE` / `ineligible_no_after`; `asserted_claims=[]`; **not** in unsupported / grounded rates |

```text
C12 ∈ envelope        = YES (identity)
C12 ∈ claim denom     = NO
C12 ∈ T2/T3 rates     = NO
C12 ∈ T1 scored set   = NO (INELIGIBLE path)
```

## 3. Targets measured

| Target | In Narrow Formal? | Denominator |
|---|---|---|
| **T1** Final citation scope preservation | **Yes** | C01–C11 After citations vs plan/gated scope |
| **T2** Unsupported claim observation | **Yes** | C01–C11 After content + BP-A rebound claim gold |
| **T3** Answer grounding observation | **Yes** | C01–C11 After content+citations + BP-A gold (G1∧G2) |
| **T4** Empty-gate refuse | **No** | Requires S2 companion — **out of Narrow** |

```text
targets_measured (Narrow Formal) = {T1, T2, T3}
```

## 4. What this selection is *not*

| Non-selection | Note |
|---|---|
| Full Formal case set + T4 | Needs S2 packaging authorization |
| Live A4 After set | Needs A4 owner auth + `llm_called` thaw |
| E-B18 author-owned compat stubs as product cases | Compat ≠ product After |
| E-B6 synthetic bodies as formal denom | Synthetic contamination veto |
| Subset cherry-pick (e.g. C01–C04 only) | First Narrow Formal uses **full** C01–C11 |

## 5. Freeze checklist (design — unchecked until entry)

```text
[ ] targets_measured frozen = {T1, T2, T3}
[ ] measured case_ids frozen = {C01 … C11}
[ ] C12 status frozen = INELIGIBLE (not claim denom)
[ ] suite_id frozen = w9_critic_frozen_12
[ ] binding_policy frozen = BP-A
[ ] S2 / T4 explicitly absent from claimed scope
[ ] A4 / live LLM explicitly absent from claimed scope
```

**E-B24 design result:** selection **defined**; freeze stamps for Formal Entry
remain **unchecked** until a later authorization window.

## 6. Stamp

```text
TARGET_CASE_SELECTION_DEFINED       = YES
MEASURED_CASES                      = C01–C11
EXCLUDED_CASES                      = C12
TARGETS_MEASURED                    = {T1,T2,T3}
E-B_FORMAL_READY                    = NO
FORMAL_OBSERVATION                  = NOT_STARTED
```
