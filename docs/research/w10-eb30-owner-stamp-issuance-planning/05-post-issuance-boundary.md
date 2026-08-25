# 05 — Post Issuance Boundary

> Clarifies what happens **after** an owner stamp is issued, and what
> issuance still does **not** unlock.  
> Boundary design only — no issuance / capture / formal in this window.

## 1. Core claim

```text
owner stamp issued  ≠  formal ready
owner stamp issued  ≠  observation completed
owner stamp issued  ≠  reserved result present
```

Even when a future window sets:

```text
OWNER_AUTHORIZATION_ISSUED = YES
SOURCE_APPROVED            = YES
AFTER_SOURCE_APPROVED      = YES
```

the following remain **required** before any honest Formal Observation:

```text
After capture
  → Binding
  → Scoring
  → Formal gate unlock
```

## 2. Post-issuance chain (ordered)

```text
[Issued APPROVED stamp]
        │
        ▼
(1) Acquisition execution readiness
        · E-B29 acquisition entry gate green
        · CAPTURE_MODE_FROZEN already true
        · ACQUISITION_EXECUTION_READY may flip YES
        │
        ▼
(2) After capture
        · Product After for C01–C11 under frozen capture_mode
        · Formal After Capture Records
        · formal_measurement = false at capture
        · C12 INELIGIBLE only
        │
        ▼
(3) Binding
        · BP-A observed_after binding
        · gold ↔ after hashes / case_id alignment
        · rebound procedure (E-B26 04) as needed
        │
        ▼
(4) Scoring
        · T1/T2/T3 under authorized scorer/wireup contracts
        · still not reserved formal write unless gate allows
        │
        ▼
(5) Formal gate
        · E-B23/E-B24 entry checklist
        · MAY_ENTER_FORMAL_OBSERVATION_WINDOW
        · E-B_FORMAL_READY unlock (dedicated window)
        · only then Formal Observation / reserved result
```

```text
Skipping (2)–(5) because stamp exists  = FORBIDDEN
Treating (1) as Formal Observation     = FORBIDDEN
```

## 3. Gate matrix after APPROVED issuance

| Gate | After APPROVED stamp alone | Needs additionally |
|---|---|---|
| `OWNER_AUTHORIZATION_ISSUED` | YES | — |
| `SOURCE_APPROVED` / `AFTER_SOURCE_APPROVED` | YES | stamp match + Narrow scope |
| `CAPTURE_MODE_FROZEN` | must already be YES | freeze record |
| `ACQUISITION_EXECUTION_READY` | **not auto** | E-B29 entry conjunction |
| After captured | **NO** | acquisition execution window |
| Binding compatible (live suite) | **NO** | capture + bind |
| Scoring formal | **NO** | bind + formal unlock |
| `E-B_FORMAL_READY` | **NO** | dedicated formal unlock |
| `MAY_ENTER_FORMAL_OBSERVATION_WINDOW` | **NO** | full formal checklist |
| `FORMAL_OBSERVATION` | `NOT_STARTED` | execution window |

## 4. Hard separations (post-issuance)

| Left | Right | Rule |
|---|---|---|
| **authorization issued** | **formal ready** | Stamp approves After source denom eligibility; formal unlock is separate |
| **approved source** | **After captured** | Approval precedes capture; does not invent After bodies |
| **After captured** | **Binding done** | Capture records ≠ rebound/bind proof |
| **Binding done** | **Scoring done** | Bind ≠ T1/T2/T3 formal scores |
| **Scoring available** | **Formal gate open** | Scorer/wireup readiness ≠ observation authorization |
| **formal gate open** | **observation completed** | Unlock ≠ executed reserved result |

```text
authorization issued  ≠  formal ready
approved source       ≠  completed observation
```

## 5. What issuance may unlock (narrowly)

When `authorization_status=APPROVED` and match predicates hold:

- Honest claim that After **source** is owner-approved for Narrow Formal denom
- Progress toward `ACQUISITION_EXECUTION_READY` (still needs full entry gate)
- Clearance of B-AUTH-1 class blockers (stamp missing)

## 6. What issuance must never unlock alone

```text
DO NOT unlock E-B_FORMAL_READY
DO NOT unlock MAY_ENTER_FORMAL_OBSERVATION_WINDOW
DO NOT write reserved formal result
DO NOT claim Formal Observation started/completed
DO NOT treat E-B18 synthetic compat bodies as Product After
DO NOT call LM Studio / API / A4 under Narrow without scope revision
DO NOT skip After capture / Binding / Scoring
```

## 7. Expiration / review after issuance

From `01` policy:

```text
on base_sha | capture_mode | model_backend | runtime | scope change
  → REVOKE_OR_REISSUE
  → SOURCE_APPROVED / AFTER_SOURCE_APPROVED revert to NO until reissued
  → downstream acquisition/formal work using old stamp is invalid
```

Review-by date reached without reaffirmation ⇒ treat as **must review**;
do not silently extend.

## 8. Current boundary state (E-B30)

```text
OWNER_STAMP_ISSUANCE_DESIGNED  = YES
OWNER_AUTHORIZATION_ISSUED     = NO
SOURCE_APPROVED                = NO
AFTER_SOURCE_APPROVED          = NO
ACQUISITION_EXECUTION_READY    = NO
After capture                  = NOT_DONE
Binding (live authorized)      = NOT_DONE
Scoring (formal)               = NOT_DONE
Formal gate                    = LOCKED
E-B_FORMAL_READY               = NO
FORMAL_OBSERVATION             = NOT_STARTED
```

## 9. Explicit non-goals

```text
DO NOT issue stamp in this window.
DO NOT start After capture / Binding / Scoring / Formal Observation.
DO NOT flip any approved/ready gate.
DO NOT modify backend/app.
```

## 10. Package stamp

```text
POST_ISSUANCE_BOUNDARY_DESIGNED = YES
OWNER_STAMP_ISSUANCE_DESIGNED   = YES
OWNER_AUTHORIZATION_ISSUED      = NO
SOURCE_APPROVED                 = NO
AFTER_SOURCE_APPROVED           = NO
ACQUISITION_EXECUTION_READY     = NO
E-B_FORMAL_READY                = NO
CAPTURE_MODE_FROZEN             = NO
FORMAL_OBSERVATION              = NOT_STARTED
```
