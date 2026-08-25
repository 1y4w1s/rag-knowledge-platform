# 04 — Issuance Gate Design

> Defines preconditions for flipping  
> `OWNER_AUTHORIZATION_ISSUED = YES`.  
> Gate designed only — issuance does **not** happen in this window.

## 1. What “issued” means

```text
OWNER_AUTHORIZATION_ISSUED = YES  ⇔
    a human-issued stamp artifact exists under schema eb30_owner_stamp_v1
  ∧ stamp.auto_derived = false
  ∧ stamp.authorization_status ∈ { APPROVED, DENIED, REVOKED }
      # WITHHELD drafts do NOT count as issued
  ∧ all mandatory fields in 01 are present
  ∧ issuer is human owner or written human delegate
```

Notes:

- A **WITHHELD** draft is not issuance.
- **DENIED** / **REVOKED** still count as “issued” (decision recorded) but
  **must not** flip `SOURCE_APPROVED` / `AFTER_SOURCE_APPROVED` to YES.
- Only **APPROVED** issuance may flip those synonym gates (see §3).

```text
issuance gate designed  ⇏  authorization issued
OWNER_AUTHORIZATION_ISSUED = YES (APPROVED)
  ⇏  E-B_FORMAL_READY
  ⇏  acquisition executed
```

## 2. Preconditions for APPROVED issuance

All conjuncts required:

```text
MAY_ISSUE_APPROVED_OWNER_STAMP = YES  ⇔
    OWNER_AUTHORIZATION_DESIGNED = YES          # E-B29
  ∧ OWNER_STAMP_ISSUANCE_DESIGNED = YES         # E-B30
  ∧ STAMP_SCHEMA_COMPLETE = YES                 # 01 filled
  ∧ SOURCE_IDENTITY_COMPLETE = YES              # 02 four pillars
  ∧ CAPTURE_MODE_FROZEN = YES                   # 03 freeze_status=FROZEN
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
      (issuance MUST NOT flip formal ready)
```

Missing **any** conjunct ⇒ do not issue `APPROVED`.

## 3. Effects of issuance (by status)

### 3.1 APPROVED

```text
OWNER_AUTHORIZATION_ISSUED = YES
SOURCE_APPROVED            = YES     # synonym for this Narrow chain
AFTER_SOURCE_APPROVED      = YES
authorization_status       = APPROVED
```

Still remains:

```text
ACQUISITION_EXECUTION_READY = NO until E-B29 entry gate (04) also green
E-B_FORMAL_READY            = NO
MAY_ENTER_FORMAL_OBSERVATION_WINDOW = NO
FORMAL_OBSERVATION          = NOT_STARTED
CAPTURE already done?       = NO unless separate acquisition window ran
```

### 3.2 DENIED

```text
OWNER_AUTHORIZATION_ISSUED = YES
SOURCE_APPROVED            = NO
AFTER_SOURCE_APPROVED      = NO
authorization_status       = DENIED
```

### 3.3 REVOKED

```text
OWNER_AUTHORIZATION_ISSUED = YES   # revocation record exists
SOURCE_APPROVED            = NO    # reverts prior YES if any
AFTER_SOURCE_APPROVED      = NO
authorization_status       = REVOKED
```

### 3.4 WITHHELD (current)

```text
OWNER_AUTHORIZATION_ISSUED = NO
SOURCE_APPROVED            = NO
AFTER_SOURCE_APPROVED      = NO
authorization_status       = WITHHELD
```

## 4. Issuance checklist (pre-APPROVED)

```text
[ ] schema eb30_owner_stamp_v1 fields complete (01)
[ ] source identifier + product version + deployment + environment frozen (02)
[ ] capture_mode frozen ∈ {product_stream, authorized_export, …} (03)
[ ] model_backend_identity / runtime_identity / base_sha / run_identity set
[ ] expiration_or_review_policy set (REVIEW_BY and/or EVENT_TRIGGERED)
[ ] authorization_scope Narrow · BP-A · C01–C11 · C12 INELIGIBLE
[ ] human issuer identified; auto_derived=false
[ ] formal gates remain locked (E-B_FORMAL_READY=NO)
```

### Current evaluation (E-B30 end)

| Item | Status |
|---|---|
| Authorization model designed (E-B29) | YES |
| Issuance protocol designed (E-B30) | YES |
| Schema complete as live stamp | **NO** (design only) |
| Source identity complete | **NO** |
| Capture mode frozen | **NO** |
| model / runtime / sha / run frozen | **NO** |
| Human APPROVED stamp | **NO** (WITHHELD) |
| SOURCE / AFTER_SOURCE approved | **NO** |

```text
MAY_ISSUE_APPROVED_OWNER_STAMP = NO
OWNER_AUTHORIZATION_ISSUED     = NO
```

## 5. Who may issue

```text
MAY_ISSUE     = project owner (human) or explicitly written human delegate
MAY_NOT_ISSUE = CI · pytest · coding agent · “LGTM” without full stamp
                · harness READY · candidate selection · architecture ADR
                · E-B30 design package itself
```

Default = **no delegation**.

## 6. Forbidden shortcuts

| Shortcut | Why forbidden |
|---|---|
| Flip `OWNER_AUTHORIZATION_ISSUED` without stamp artifact | Gate without evidence |
| APPROVED without `CAPTURE_MODE_FROZEN` | Incomplete honesty |
| APPROVED without four source pillars | Incomplete identity |
| Treat E-B30 docs as the stamp | Design ≠ issuance |
| Auto-issue from pytest green | Owner agency |
| Flip `E-B_FORMAL_READY` because stamp APPROVED | Separate unlock (05) |

## 7. Relation to acquisition entry (E-B29)

Issuance (APPROVED) is **necessary but not sufficient** for
`ACQUISITION_EXECUTION_READY`:

```text
ACQUISITION_EXECUTION_READY = YES  still requires
  owner stamp APPROVED
  ∧ CAPTURE_MODE_FROZEN
  ∧ identity checklist complete
  ∧ E-B26 plan artifacts
  ∧ formal gates remain locked
  ∧ … (full E-B29 04 conjunction)
```

## 8. Explicit non-goals (this window)

```text
DO NOT issue a stamp.
DO NOT set OWNER_AUTHORIZATION_ISSUED = YES.
DO NOT set SOURCE_APPROVED / AFTER_SOURCE_APPROVED = YES.
DO NOT set CAPTURE_MODE_FROZEN / ACQUISITION_EXECUTION_READY = YES.
DO NOT flip E-B_FORMAL_READY.
```

## 9. Stamp

```text
ISSUANCE_GATE_DESIGNED       = YES
OWNER_AUTHORIZATION_ISSUED   = NO
SOURCE_APPROVED              = NO
AFTER_SOURCE_APPROVED        = NO
ACQUISITION_EXECUTION_READY  = NO
E-B_FORMAL_READY             = NO
CAPTURE_MODE_FROZEN          = NO
```
