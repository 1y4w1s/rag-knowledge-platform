# 02 — BP-A eligibility review

> Applies E-B24 After authorization contract (§2.1–§2.4) to the **current**
> suite state. Conjunction required; any FAIL ⇒ suite not formal-eligible.

## 1. Predicate (inherited)

```text
AFTER_APPROVED_FOR_NARROW_FORMAL(case) ⇔
    source_identity_ok(case)
  ∧ hash_binding_bp_a_bound(case)
  ∧ capture_mode_declared_and_allowed(case)
  ∧ ¬synthetic_contamination(case)
  ∧ owner_approval_stamp_present

Suite After approved ⇔
    ∀ case ∈ {C01 … C11}: AFTER_APPROVED_FOR_NARROW_FORMAL(case)
  ∧ C12 recorded INELIGIBLE
```

This window **evaluates** the predicate. It does **not** grant stamps.

---

## 2. Condition-by-condition

### 2.1 Source identity

| Requirement | Current evidence | Result |
|---|---|---|
| Named `after_source` / provenance | E-B15: harness captures exist but **no** formal-eligible source id suite stamp; E-B18: `compatibility_materialization_author_owned` (explicit non-product) | **FAIL** for product formal |
| `case_id` ∈ {C01…C11} | Both packs can address C01–C11 slots | Partial OK (identity shape) |
| Suite = `w9_critic_frozen_12` | Inherited design | Partial OK |
| Owner formal-eligible stamp | Absent for A and C; B stamped **compat-only** | **FAIL** |
| Non-product not relabeled as product | Honesty labels present on B; A not upgraded | OK as hygiene; does not pass identity |

```text
source_identity_ok (suite formal) = NO
```

### 2.2 Hash binding (BP-A)

| Requirement | Current evidence | Result |
|---|---|---|
| `binding_policy = observed_after` | Declared for Narrow (E-B24) + E-B18 pack | Policy OK |
| Gold content hash ↔ After content digest (same codec) | E-B18 rebound pack: **YES** (compat bodies only) | Compat-path OK |
| Live E-B15 × unrebounded E-B12B | `LIVE_EB15_X_EB12B_COMPATIBLE=NO` → INCOMPATIBLE | **FAIL** for product path |
| Pool / case bind | E-B17–E-B18 validators exist | Tooling OK |
| BindingVerdict `BOUND` under BP-A for **formal** After | Only on author-owned compat stubs | **FAIL** for formal denom |

```text
hash_binding_bp_a_bound (formal product suite) = NO
# Note: compat pack BOUND does not satisfy formal After binding.
```

### 2.3 Capture mode

| Requirement | Current evidence | Result |
|---|---|---|
| Declared capture mode | E-B15 Scheme A harness declared as **harness**, not formal mode | **FAIL** formal mode |
| Allowed under Narrow (non-A4, non-S2-as-T1–T3) | A4 excluded; S2 excluded from Narrow targets | Scope OK |
| Owner-approved product-path formal capture | No owner formal capture approval | **FAIL** |
| Honest `llm_called` | E-B15/E-B18 keep `llm_called=false` | Honesty OK; not enough |

```text
capture_mode_declared_and_allowed (formal) = NO
```

### 2.4 No synthetic contamination

| Contamination class | Present in candidate denom? | Result |
|---|---|---|
| E-B6 isomorphic / synthetic bodies | Forbidden by E-B15 harness rules; not used as formal | N/A / OK if unused |
| E-B18 author-owned compatibility stubs | **Yes** if Candidate B used as denom | **FAIL** if B selected |
| Fixtures without formal stamp | E-B15 informal captures | **FAIL** if claimed formal |
| Mixed synthetic + product rates | Not currently a formal suite — risk if blend | Must remain forbidden |
| Pytest green as product faithfulness | Explicitly vetoed in E-B18 / E-B24 | Honesty OK |

```text
¬synthetic_contamination (if claiming A or C as formal today) = FAIL
  (no authorized product body suite exists to be clean)
¬synthetic_contamination (if claiming B)                     = FAIL
  (B is synthetic by construction)
```

---

## 3. Suite conjunction

| Condition | Suite status |
|---|---|
| source identity | **NO** |
| hash binding (BP-A formal) | **NO** |
| capture mode | **NO** |
| no synthetic contamination | **NO** (no clean authorized product After suite) |
| owner approval stamp | **NO** |

```text
AFTER_APPROVED_FOR_NARROW_FORMAL (suite) = NO
AFTER_SOURCE_APPROVED                    = NO
```

---

## 4. What is already true (and still insufficient)

| Ready signal | Satisfies formal After? |
|---|---|
| E-B15 harness READY | No |
| E-B18 `GOLD_AFTER_BINDING_COMPATIBLE=YES` | No (compat only) |
| E-B17 Binding Gate implemented | No (tooling ≠ authorized bind) |
| E-B20/E-B22 scorer + wireup tests-only | Irrelevant to After source |
| E-B24 scope defined | Necessary context; not After approval |

---

## 5. Residuals unchanged by this review

| Id | Status | Note |
|---|---|---|
| B2′ | BLOCKING_RESIDUAL | Authorized formal After still missing |
| AG-5 | PARTIAL | Compat rebound YES; live/authorized rebound NO |
| AG-3 | PARTIAL | Wireup YES; reserved write NO |
| A4 / S2 | NO | Excluded from Narrow; still locked |

## 6. Stamp

```text
BP_A_ELIGIBILITY_REVIEWED = YES
SOURCE_IDENTITY           = NO
HASH_BINDING_FORMAL       = NO
CAPTURE_MODE_FORMAL       = NO
NO_SYNTHETIC_CONTAMINATION = NO
AFTER_SOURCE_APPROVED     = NO
E-B_FORMAL_READY          = NO
```
