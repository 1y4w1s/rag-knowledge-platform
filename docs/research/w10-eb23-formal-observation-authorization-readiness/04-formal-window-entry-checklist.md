# 04 — Formal window entry checklist

> Confirm **before** opening any Formal Observation **execution** window.  
> All items remain unchecked in E-B23 (design / audit only).

## 1. Mandatory pre-entry checklist

```text
[ ] no synthetic mistaken as product evidence
    — E-B6 smoke · E-B15 harness · E-B18 author-owned compat pack
      must not be narrated as product LLM faithfulness

[ ] no LLM freeze violation
    — no LLM / LM Studio call unless A4 authorized + llm_called thaw honest

[ ] reserved result path controlled
    — compose ≠ write · RESERVED_RESULT remains ABSENT until unlock
    — no w10-eb2-generation-observation-result.json without gate YES

[ ] BP policy selected
    — BP-A / BP-B / BP-C declared per case or suite default
    — no silent blend of rates across policies

[ ] target cases frozen
    — targets_measured ⊆ {T1,T2,T3[,T4]} frozen
    — case_id set frozen · W9×12 identity intact if used
    — empty-gate only via S2 companion (never silent merge into case_count=12)

[ ] scorer companion aligned
    — L-Score artifact_kind=FORMAL_T2_T3_SCORE_RESULT
    — parent_run_id / parent_base_sha align L-Obs
    — rates only in companion (not E-B2 notes)
```

## 2. Extended clearance checklist (scope-aware)

Use in addition to §1 when claiming the corresponding scope.

### 2.1 Always (any Formal Entry)

```text
[ ] Claim gold present for every T2/T3 measured case
[ ] After source owner-approved for denominator cases (B2′)
[ ] BindingVerdict BOUND under declared BP (live rebound if BP-A product)
[ ] Wireup contract present · FORMAL_GATE_LOCKED still honored until unlock
[ ] Owner unlock stamp present for MAY_ENTER_FORMAL_OBSERVATION_WINDOW
[ ] E-B_FORMAL_READY flip plan documented (separate from entry MAY_ENTER)
```

### 2.2 If Full / T4

```text
[ ] E_B_S2_PACKAGING_AUTHORIZED = YES
[ ] Empty-gate After captured under authorized path
[ ] Dual-suite packaging result present · W9 envelope identity unchanged
```

### 2.3 If Live LLM (A4)

```text
[ ] A4 owner authorization recorded
[ ] llm_called freeze thawed under contract · matches reality
[ ] Rebound gold bound to live After content-string hash
```

## 3. Red-flag stop rules

If any red flag is true, **keep**:

```text
MAY_ENTER_FORMAL_OBSERVATION_WINDOW = NO
E-B_FORMAL_READY = NO
FORMAL_OBSERVATION = NOT_STARTED
RESERVED_RESULT = ABSENT
```

| Red flag | Action |
|---|---|
| Pytest green on harness / wireup only | Do not enter Formal Observation |
| Compat pack scored as product | Invalidate narrative · stay NO |
| LLM called under freeze | Abort · record freeze violation |
| Reserved file appears without unlock | Treat as hygiene failure · do not promote |
| T4 claimed without S2 auth | Stay NO |
| BP undeclared | Stay NO |

## 4. E-B23 audit result

```text
§1 checklist items checked: 0 / 6
MAY_ENTER_FORMAL_OBSERVATION_WINDOW = NO
E-B_FORMAL_READY                    = NO
FORMAL_OBSERVATION                  = NOT_STARTED
RESERVED_RESULT                     = ABSENT
E-B23_READINESS_DESIGNED            = YES
```

## 5. Stop

```text
DO NOT open Formal Observation execution from this window.
DO NOT write formal / reserved results.
NEXT = authorization clearance windows only.
```
