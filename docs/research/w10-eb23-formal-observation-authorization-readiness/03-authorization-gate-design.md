# 03 — Authorization gate design

> **Contract only.** Do not implement gate flip logic, reserved writers, or
> freeze thawers in this window.

## 1. Gate identity

```text
Gate name:  MAY_ENTER_FORMAL_OBSERVATION_WINDOW
Type:       Binary authorization predicate (YES | NO)
Authority:  Owner / readiness window stamp (not pytest green alone)
Companion:  E-B_FORMAL_READY  (write-time lock; remains independent)
```

**Semantics**

| Value | Meaning |
|---|---|
| `NO` | Formal Observation execution window **must not** start; clearance / planning only |
| `YES` | Next window **may** be a Formal Observation **execution** window under declared scope |

```text
MAY_ENTER_FORMAL_OBSERVATION_WINDOW = YES
  ⇏  reserved result already written
  ⇏  product faithfulness proven
  ⇒  authorized to *open* a scoped Formal Observation execution window

E-B_FORMAL_READY = YES
  ⇒  write-time permission for reserved FORMAL_OBSERVATION_RESULT
     (still requires independent write step + validity honesty)
```

**Relation:** entering the window (`MAY_ENTER…`) and writing the reserved
result (`E-B_FORMAL_READY` + write unlock) are **two locks**. Either alone is
insufficient for an honest formal artifact.

## 2. Required conditions (conjunction)

`MAY_ENTER_FORMAL_OBSERVATION_WINDOW` may become `YES` **only if all** of the
following hold for the **declared formal scope** (Narrow / Full / Live):

### 2.1 Material conditions

| # | Condition | Current |
|---|---|---|
| C-G | **Gold exists** for every T2/T3 case in `targets_measured` | Met for annotated ledger; must remain bound per case |
| C-A | **After source approved** for denominator cases (B2′ path) | **Not met** — harness ≠ approved formal After |
| C-B | **Binding compatible** under declared BP (AG-5 live rebound if BP-A product) | Compat pack only — **live not met** |
| C-S | **Scorer companion path exists** (L-Score contract + parent link rules) | Met (E-B20/E-B22 tests-only) |
| C-W | **Wireup compose contract exists** and compose≠write honesty preserved | Met (E-B22) |
| C-T | **Target cases authorized / frozen** (`targets_measured` + case_ids) | **Not met** — no formal target freeze stamp |
| C-O | **Owner unlock present** for Formal Observation window entry | **Not met** |

### 2.2 Scope-conditional conditions

| # | When required | Condition | Current |
|---|---|---|---|
| C-S2 | `T4` ∈ suite / Full dual-suite claim | `E_B_S2_PACKAGING_AUTHORIZED=YES` + empty-gate After path | **NO** |
| C-A4 | Live product LLM After | A4 owner auth + honest `llm_called` thaw contract | **NO** |
| C-BP | Always | BP policy selected per case/suite · no silent blend | Policy known; **formal selection stamp absent** |
| C-RW | Before any reserved write | Reserved result path controlled · gate-aware · independent of compose | Path designed; **write locked / ABSENT** |

### 2.3 Honesty vetoes (any one keeps gate = NO)

- Synthetic / smoke / E-B6 / E-B18 author-owned compat treated as **product** evidence  
- LLM / LM Studio called without A4 + thaw  
- Rates stuffed into E-B2 notes instead of L-Score companion  
- Silent BP-A/B/C blend  
- Attempt to write reserved result while `E-B_FORMAL_READY=NO`

## 3. Predicate (contract)

```text
MAY_ENTER_FORMAL_OBSERVATION_WINDOW ⇔
    C-G ∧ C-A ∧ C-B ∧ C-S ∧ C-W ∧ C-T ∧ C-O
  ∧ (C-S2 if T4/Full)
  ∧ (C-A4 if live LLM)
  ∧ C-BP
  ∧ ¬(honesty vetoes)
```

**This window stamp:**

```text
MAY_ENTER_FORMAL_OBSERVATION_WINDOW = NO
```

because C-A, C-B (live), C-T, C-O fail; C-S2 / C-A4 fail if those scopes are claimed.

## 4. Non-implementation boundaries

```text
DO NOT code a production flippable flag in backend/app.
DO NOT auto-flip from pytest green.
DO NOT imply YES from FORMAL_WIREUP_IMPLEMENTED=YES.
DO NOT imply YES from GOLD_AFTER_BINDING_COMPATIBLE=YES (compat pack).
DO NOT write reserved result when designing this gate.
```

Flip authority remains an **explicit owner / readiness stamp** in a future
authorization window — after clearance evidence is on disk and checklist green.

## 5. Stamp

```text
AUTHORIZATION_GATE_DESIGNED         = YES
MAY_ENTER_FORMAL_OBSERVATION_WINDOW = NO
E-B_FORMAL_READY                    = NO
```
