# 04 — Gold rebinding plan (post Product After)

> Plans how claim gold is rebound once **authorized Product After** exists.  
> Procedure design only — **no rebound execution**, no gold rewrite, no formal score.

## 1. Goal

When Product After bodies are acquired under an owner-approved source:

```text
Product After
    ↓
content hash          (BP-A observed_content_hash / source_hash)
    ↓
BP-A binding          (case_id ↔ gold.case_id · three-hash contract)
    ↓
Gold compatibility check
    ↓
BindingVerdict        (BOUND | INCOMPATIBLE | …)
```

Success criterion for formal denom readiness (future):  
∀ C01–C11 → `BindingVerdict = BOUND` under BP-A with **product** After hashes  
(not E-B18 synthetic hashes).

## 2. Preconditions

```text
[ ] Product After suite acquired for C01–C11 (schema in 02)
[ ] Owner approval stamp present (03) — AFTER_SOURCE_APPROVED may flip only then
[ ] capture_mode / model_identity / base_sha frozen and match stamp
[ ] E-B17 Binding Gate available (tests-only OK for procedure proof)
[ ] E-B18 codec rules understood — but E-B18 pack bodies MUST NOT be reused
[ ] formal gates still locked during rebound prep unless a later window unlocks write
```

## 3. Step design

### Step 1 — Product After freeze

- Load authorized Formal After Capture Records for C01–C11.  
- Recompute `source_hash` / `observed_content_hash` from `content` (BP-A codec).  
- Reject any record that fails recompute or carries synthetic provenance.

### Step 2 — Content hash ledger

- Build per-case map: `case_id → observed_content_hash` (+ evidence pool hash rules per E-B17/E-B18).  
- Record `run_identity`, `base_sha`, `after_source`.  
- Do **not** copy hashes from unrebounded E-B12B claim-text payload space.

### Step 3 — BP-A binding artifact

- For each case: construct binding inputs with `binding_policy = observed_after`.  
- Enforce `after.case_id ↔ gold.case_id`.  
- Separate hash spaces: never naive `gold_ledger_hash == observed_content_hash` across codecs.

### Step 4 — Gold compatibility check / rebound

- Produce **rebound gold** whose `content_sha256` uses **observed-content codec** aligned to Product After bodies (AG-5 live/authorized rebound path).  
- Distinguish from E-B18 compat pack: rebound target is **product** After, label must not say `compatibility_materialization_author_owned`.  
- Run compatibility validator / Binding Gate.

### Step 5 — BindingVerdict

| Verdict | Meaning for Narrow Formal |
|---|---|
| `BOUND` | Case may proceed toward formal denom **if** After also owner-approved and non-synthetic |
| `INCOMPATIBLE` | Case blocked — typical of unrebounded E-B12B × live After today |
| Other fail reasons | Treat as not ready; do not score formal rates |

Suite rule:

```text
AG-5 live/authorized rebound ready for Narrow  ⇔
  ∀ C01..C11: BindingVerdict = BOUND under BP-A on Product After hashes
  ∧ no synthetic contamination
  ∧ AFTER_SOURCE_APPROVED = YES
```

## 4. E-B18 synthetic pack — quarantine

```text
E-B18 synthetic / author-owned compat pack:
  - KEEP as tests-only hygiene / codec proof
  - DO NOT promote bodies into Product After
  - DO NOT mix E-B18 stubs into formal rates
  - DO NOT treat GOLD_AFTER_BINDING_COMPATIBLE (compat) as live rebound complete
  - LIVE_EB15_X_EB12B_COMPATIBLE remains the honesty probe until product rebound exists
```

```text
E-B18_TESTS_ONLY = YES  (unchanged policy)
```

## 5. What rebinding does **not** unlock

| Still locked / separate | Note |
|---|---|
| `E-B_FORMAL_READY` | Rebound ≠ formal write unlock |
| Formal observation execution | Needs full entry checklist |
| S2 / A4 | Still out of Narrow scope |
| T2/T3 formal rates | Scorer exists tests-only; formal compose still gate-locked (E-B22) |

## 6. Explicit non-goals (this window)

```text
DO NOT rewrite gold files.
DO NOT run Binding Gate as formal.
DO NOT flip AG-5 to CLEARED.
DO NOT set AFTER_SOURCE_APPROVED.
DO NOT create reserved formal result.
```

## 7. Stamp

```text
GOLD_REBINDING_PROCEDURE_DESIGNED = YES
GOLD_REBINDING_EXECUTED           = NO
AG-5                              = PARTIAL
LIVE_EB15_X_EB12B_COMPATIBLE      = NO
AFTER_SOURCE_APPROVED             = NO
E-B_FORMAL_READY                  = NO
```
