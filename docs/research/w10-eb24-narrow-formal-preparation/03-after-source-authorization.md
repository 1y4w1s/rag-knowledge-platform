# 03 — After source authorization (Narrow Formal)

> Defines **when** an After snapshot may become a **formal observation input**
> under Narrow Formal · BP-A · C01–C11.  
> Does **not** approve any After, capture any stream, or clear B2′ / AG-5.

## 1. Purpose

B2′ remains **BLOCKING_RESIDUAL**: harness readiness ≠ authorized formal After.
AG-5 remains **PARTIAL**: E-B18 compat rebound ≠ live / authorized product
rebound.

This document freezes the **acceptance contract** so a future clearance window
knows exactly what to approve.

## 2. Four mandatory conditions (conjunction)

An After may be used as Narrow Formal denominator input **only if all** hold:

### 2.1 Source identity

| Requirement | Detail |
|---|---|
| Named source | Explicit `after_source` / capture provenance id (not implied) |
| Case identity | `after_snapshot.case_id` ∈ {C01 … C11} for measured slots; C12 never claim-scored |
| Suite identity | Bound to `w9_critic_frozen_12` (or declared companion — **not** for Narrow T4) |
| Owner approval | Owner stamp that this source is **formal-eligible** for Narrow Formal |
| Non-product labels forbidden as product | Must not relabel smoke / synthetic / author-owned compat as product |

```text
source identity OK  ⇒  named · case-aligned · suite-aligned · owner-approved
source identity FAIL ⇒  After must not enter formal denom
```

### 2.2 Hash binding (BP-A)

| Requirement | Detail |
|---|---|
| Policy | `binding_policy = observed_after` (**BP-A only**) |
| Content bind | Gold `content_sha256` (rebound) == After observed content digest (same codec) |
| Pool bind | Evidence pool hash / id subset rules per E-B17–E-B18 |
| Case bind | `after.case_id` ↔ `gold.case_id` ↔ binding artifact |
| Verdict | Binding gate → `BOUND` under BP-A |

```text
E-B18 compat pack BOUND  ⇏  formal After authorized
Live unrebounded E-B12B × product After  ⇒  INCOMPATIBLE under BP-A
Formal needs: authorized After + AG-5 live/authorized rebound → BOUND
```

### 2.3 Capture mode

| Allowed for Narrow Formal (when later authorized) | Forbidden in this Narrow scope |
|---|---|
| Owner-approved **product-path** After capture under Scheme A harness (non-A4), with honest `llm_called` | **A4 live LLM** capture / thaw |
| Modes that do **not** require live model keys, if and only if owner still stamps them formal-eligible **and** labels honesty (`llm_called` matches reality) | Silent upgrade of harness smoke → formal |
| Capture that yields real After `state["content"]` / `state["citations"]` for C01–C11 | Empty-gate / S2 modes claimed as Narrow T1–T3 After |

```text
Narrow Formal capture mode must be declared and owner-approved.
A4 is out of scope — even if technically possible, it is not Narrow Formal.
S2 / empty-gate capture is out of scope for this Narrow target set.
```

### 2.4 No synthetic contamination

| Contamination class | Rule |
|---|---|
| E-B6 isomorphic / synthetic bodies | **Never** formal T2/T3 denom |
| E-B18 author-owned compatibility stubs | Hygiene / compat only — **not** product formal After |
| Schema examples / fixtures without owner formal stamp | Pre-formal only |
| Mixed synthetic + product in one rate | **Forbidden** |
| Narrating pytest green as product faithfulness | Honesty veto |

```text
no synthetic contamination  ⇒  formal After body is the authorized source body
                              ∧ gold rebound matches that body
                              ∧ rates do not mix synthetic slots
```

## 3. Authorization predicate (contract)

```text
AFTER_APPROVED_FOR_NARROW_FORMAL(case) ⇔
    source_identity_ok(case)
  ∧ hash_binding_bp_a_bound(case)
  ∧ capture_mode_declared_and_allowed(case)   # excludes A4 · excludes S2-as-T1–T3
  ∧ ¬synthetic_contamination(case)
  ∧ owner_approval_stamp_present
```

```text
Suite After approved for Narrow Formal ⇔
    ∀ case ∈ {C01 … C11}: AFTER_APPROVED_FOR_NARROW_FORMAL(case)
  ∧ C12 recorded INELIGIBLE (not claim-scored)
```

**Current stamp (E-B24):**

```text
AFTER_APPROVED_FOR_NARROW_FORMAL = NO
B2_PRIME_AFTER_SNAPSHOTS         = BLOCKING_RESIDUAL
AG-5                             = PARTIAL
```

## 4. What harness green still is not

| Green signal | Formal After? |
|---|---|
| E-B15 `PRODUCT_AFTER_CAPTURE_HARNESS_READY` | No |
| E-B18 `GOLD_AFTER_BINDING_COMPATIBLE` (compat pack) | No |
| E-B20 / E-B22 pytest green | No |
| Empty-gate material ready | Irrelevant to Narrow (S2 excluded) |

## 5. Stamp

```text
AFTER_SOURCE_AUTHORIZATION_CONTRACT = YES   (designed this window)
AFTER_SOURCE_APPROVED               = NO
B2_PRIME_AFTER_SNAPSHOTS            = BLOCKING_RESIDUAL
AG-5                                = PARTIAL
E-B_FORMAL_READY                    = NO
FORMAL_OBSERVATION                  = NOT_STARTED
```
