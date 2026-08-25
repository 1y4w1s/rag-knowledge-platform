# 04 — Issuance Gate Simulation

> Dry-run of E-B30 `MAY_ISSUE_APPROVED_OWNER_STAMP` and
> `OWNER_AUTHORIZATION_ISSUED` preconditions.  
> **Simulation only** — no stamp issued; no gates flipped.

## 1. Predicates under simulation

### 1.1 APPROVED issuance conjunct (E-B30 `04` §2)

```text
MAY_ISSUE_APPROVED_OWNER_STAMP = YES  ⇔
    OWNER_AUTHORIZATION_DESIGNED = YES
  ∧ OWNER_STAMP_ISSUANCE_DESIGNED = YES
  ∧ STAMP_SCHEMA_COMPLETE = YES
  ∧ SOURCE_IDENTITY_COMPLETE = YES
  ∧ CAPTURE_MODE_FROZEN = YES
  ∧ model_backend_identity frozen and stamped
  ∧ runtime_identity frozen and stamped
  ∧ base_sha declared (exact) and stamped
  ∧ run_identity declared and stamped
  ∧ expiration_or_review_policy present
  ∧ authorization_scope matches Narrow Formal
  ∧ E-B28 separation acknowledged on stamp
  ∧ anti-contamination policy acknowledged
  ∧ issuer = human owner | written delegate
  ∧ auto_derived = false
  ∧ E-B_FORMAL_READY remains intentionally unlocked elsewhere
```

### 1.2 “Issued” meaning (not claimed this window)

```text
OWNER_AUTHORIZATION_ISSUED = YES  ⇔
    human-issued stamp artifact exists (eb30_owner_stamp_v1)
  ∧ auto_derived = false
  ∧ authorization_status ∈ { APPROVED, DENIED, REVOKED }
  ∧ mandatory fields present
  ∧ issuer human / written delegate
```

WITHHELD drafts do **not** count as issued. E-B31 creates **no** draft or
decision stamp.

## 2. Conjunct table (dry-run)

| # | Conjunct | Result | Class |
|---|---|---|---|
| 1 | `OWNER_AUTHORIZATION_DESIGNED` | YES | READY |
| 2 | `OWNER_STAMP_ISSUANCE_DESIGNED` | YES | READY |
| 3 | `STAMP_SCHEMA_COMPLETE` | **NO** | BLOCKED (`01`) |
| 4 | `SOURCE_IDENTITY_COMPLETE` | **NO** | BLOCKED (`02`) |
| 5 | `CAPTURE_MODE_FROZEN` | **NO** | BLOCKED (`03`) |
| 6 | `model_backend_identity` frozen+stamped | **NO** | BLOCKED · human |
| 7 | `runtime_identity` frozen+stamped | **NO** | BLOCKED · human |
| 8 | `base_sha` exact+stamped | **NO** | BLOCKED · human |
| 9 | `run_identity` declared+stamped | **NO** | BLOCKED · human |
| 10 | `expiration_or_review_policy` present | **NO** (live) | BLOCKED · human |
| 11 | Narrow `authorization_scope` on stamp | **NO** (live) | BLOCKED · human |
| 12 | E-B28 acknowledged **on stamp** | **NO** (no stamp) | BLOCKED |
| 13 | Anti-contamination acknowledged **on freeze/stamp** | **NO** (live) | BLOCKED · human |
| 14 | Human issuer identified | **NO** | BLOCKED · human |
| 15 | `auto_derived=false` | rule READY · no stamp | BLOCKED until issue |
| 16 | Formal remains unlocked (`E-B_FORMAL_READY=NO`) | YES (held) | READY / honesty |

```text
Missing any conjunct ⇒ do not issue APPROVED.
```

## 3. Simulation outcomes

```text
MAY_ISSUE_APPROVED_OWNER_STAMP = NO
OWNER_AUTHORIZATION_ISSUED     = NO   # no artifact · status remains WITHHELD
SOURCE_APPROVED                = NO
AFTER_SOURCE_APPROVED          = NO
```

### 3.1 What a green MAY_ISSUE would still *not* unlock

Even in a future window where MAY_ISSUE becomes YES and a human issues
APPROVED:

```text
ACQUISITION_EXECUTION_READY     still requires E-B29 entry conjunction
E-B_FORMAL_READY                still NO until dedicated unlock
MAY_ENTER_FORMAL_OBSERVATION_WINDOW still NO
FORMAL_OBSERVATION              remains NOT_STARTED
```

E-B31 does **not** simulate those flips as YES.

### 3.2 DENIED / REVOKED path (not exercised)

Gate design allows DENIED/REVOKED to count as “issued” without approving
sources. E-B31 does **not** recommend or create those records; current
effective status stays WITHHELD.

## 4. Pre-APPROVED checklist (E-B30 §4) — current ticks

```text
[ ] schema eb30_owner_stamp_v1 fields complete (01)          → NO
[ ] source identifier + product version + deployment
    + environment frozen (02)                                → NO
[ ] capture_mode frozen ∈ enum (03)                          → NO
[ ] model / runtime / base_sha / run_identity set            → NO
[ ] expiration_or_review_policy set                          → NO
[ ] authorization_scope Narrow · BP-A · C01–C11 · C12 INEL.  → design only
[ ] human issuer identified; auto_derived=false              → NO / rule only
[x] formal gates remain locked (E-B_FORMAL_READY=NO)         → YES (held)
```

**Checked:** 1/8 (honesty lock only). **Issuance checklist:** FAIL.

## 5. Who may issue (reaffirm)

```text
MAY_ISSUE     = project owner (human) or written human delegate
MAY_NOT_ISSUE = CI · pytest · coding agent · E-B31 audit package ·
                E-B30 design · candidate A selection · harness green
```

## 6. Stamp

```text
ISSUANCE_GATE_DESIGNED         = YES   (E-B30)
ISSUANCE_GATE_SIMULATED        = YES   (this window)
MAY_ISSUE_APPROVED_OWNER_STAMP = NO
OWNER_AUTHORIZATION_ISSUED     = NO
SOURCE_APPROVED                = NO
AFTER_SOURCE_APPROVED          = NO
ACQUISITION_EXECUTION_READY    = NO
E-B_FORMAL_READY               = NO
CAPTURE_MODE_FROZEN            = NO
```
