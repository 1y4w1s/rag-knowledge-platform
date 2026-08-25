# 04 — Acquisition entry gate

> Defines when a **future** Product After **acquisition execution** window
> may start for Narrow Formal under candidate A.  
> Gate designed only — `ACQUISITION_EXECUTION_READY=NO`.

## 1. Core separations

```text
Acquisition entry gate open  ≠  Acquisition executed
Acquisition executed         ≠  Formal Observation
Authorized After source      ≠  Completed observation / reserved result
authorization                ≠  formal ready
```

Even if this gate later turns YES, Formal Observation gates stay locked
unless a dedicated formal unlock window flips them.

## 2. Entry conjunction (all required)

```text
ACQUISITION_EXECUTION_READY = YES  ⇔
    PRIMARY_CANDIDATE_SOURCE = A (or later planning revision · not silent)
  ∧ SOURCE_MODEL_SEPARATION_DESIGNED = YES
  ∧ owner stamp present with authorization_status = APPROVED
  ∧ SOURCE_APPROVED = YES
  ∧ AFTER_SOURCE_APPROVED = YES
  ∧ CAPTURE_MODE_FROZEN = YES
  ∧ model_backend_identity frozen and stamped
  ∧ run_identity / base_sha declared and stamped
  ∧ after-source identity checklist complete (02)
  ∧ no synthetic contamination policy acknowledged for the suite
  ∧ E-B_FORMAL_READY = NO                    # must remain locked
  ∧ MAY_ENTER_FORMAL_OBSERVATION_WINDOW = NO # must remain locked
  ∧ acquisition plan artifacts present (E-B26 02 schema)
```

Missing **any** conjunct ⇒ gate stays **NO**.

## 3. Checklist (pre-acquisition-execution)

Inherited/extended from E-B26 `05`, now binding stamp + E-B28 separation:

```text
[ ] source selected (PRIMARY = A · design already YES)
[ ] source/model separation acknowledged (E-B28 · design already YES)
[ ] after-source identity checklist complete (02)
[ ] capture mode frozen (03 filled · freeze_status=FROZEN)
[ ] model/backend identity frozen
[ ] run identity + base sha declared
[ ] owner stamp issued · authorization_status=APPROVED
[ ] SOURCE_APPROVED=YES · AFTER_SOURCE_APPROVED=YES
[ ] gold rebinding procedure ready (E-B26 04 · plan only until after capture)
[ ] no synthetic contamination policy in force
[ ] formal gate still locked (E-B_FORMAL_READY=NO)
```

### Current evaluation (E-B29 end)

| Item | Status |
|---|---|
| source selected (A) | Design YES · **not approved** |
| source/model separation | Designed YES |
| identity checklist | Designed · **incomplete** |
| capture mode frozen | Template only · **NO** |
| model/backend frozen | **NO** |
| run identity / base sha | **NO** |
| owner stamp APPROVED | **NO** (WITHHELD) |
| SOURCE / AFTER_SOURCE approved | **NO** |
| gold rebound procedure | Designed (E-B26) |
| synthetic contamination policy | Policy YES · suite proof pending |
| formal gate locked | **YES (correct)** |

```text
ACQUISITION_EXECUTION_READY = NO
```

## 4. Allowed vs forbidden once gate later opens

### Allowed (future acquisition execution only)

| Action | Note |
|---|---|
| Capture Product After for C01–C11 | E-B26 Formal After Capture Record schema |
| Record C12 INELIGIBLE | Not claim After denom |
| Compute BP-A `source_hash` from observed content | Not from gold |
| Keep `formal_measurement=false` | Acquisition ≠ formal result |

### Forbidden (always in this chain until separate unlock)

| Action | Why |
|---|---|
| Formal T1/T2/T3 scoring as formal | Formal Observation only |
| Reserved result write | Reserved write gate |
| Flip `E-B_FORMAL_READY` | Dedicated unlock |
| Call LM Studio / API / open A4 under Narrow | Narrow freeze |
| Promote E-B18 synthetic bodies | Contamination |
| Modify `backend/app` as capture shortcut | Out of research/acquisition class unless planned |
| Auto-stamp from pytest | Owner agency |

## 5. Post-gate honesty

```text
ACQUISITION_EXECUTION_READY = YES
  ⇏  Formal Observation ready
  ⇏  observation completed
  ⇏  reserved result present

authorization = APPROVED
  ⇏  E-B_FORMAL_READY
  ⇏  completed observation
```

## 6. Explicit non-goals (this window)

```text
DO NOT claim any §3 box checked as execution-ready.
DO NOT start acquisition.
DO NOT generate After.
DO NOT flip ACQUISITION_EXECUTION_READY.
DO NOT flip E-B_FORMAL_READY.
```

## 7. Stamp

```text
ACQUISITION_ENTRY_GATE_DESIGNED = YES
ACQUISITION_EXECUTION_READY     = NO
ACQUISITION_EXECUTED            = NO
SOURCE_APPROVED                 = NO
AFTER_SOURCE_APPROVED           = NO
E-B_FORMAL_READY                = NO
FORMAL_OBSERVATION              = NOT_STARTED
```
