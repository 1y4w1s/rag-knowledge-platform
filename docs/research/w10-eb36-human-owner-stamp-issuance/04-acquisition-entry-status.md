# 04 — Acquisition Entry Status (E-B36 · stamp-only window)

> Re-reads E-B29 `04-acquisition-entry-gate.md` conjunction.  
> **E-B36 does not execute acquisition.**  
> Default this window: leave `ACQUISITION_EXECUTION_READY=NO` and hand off to
> a dedicated acquisition-entry review.

## 1. E-B29 entry conjunction (status after APPROVED stamp)

```text
E-B29 predicate (definition only · not a current claim):
  ACQUISITION_EXECUTION_READY becomes YES only when ALL conjuncts below hold.
```

| # | Conjunct | Status after E-B36 stamp | Notes |
|---|---|---|---|
| 1 | `PRIMARY_CANDIDATE_SOURCE = A` | YES | design candidate only |
| 2 | `SOURCE_MODEL_SEPARATION_DESIGNED = YES` | YES | E-B28 |
| 3 | owner stamp `authorization_status=APPROVED` | YES | this window `01` |
| 4 | `SOURCE_APPROVED = YES` | YES | E-B30 §3.1 effect |
| 5 | `AFTER_SOURCE_APPROVED = YES` | YES | E-B30 §3.1 effect |
| 6 | `CAPTURE_MODE_FROZEN = YES` | YES | E-B35b |
| 7 | `model_backend_identity` frozen & stamped | YES | `none_no_llm` on stamp |
| 8 | `run_identity` / `base_sha` declared & stamped | YES | on stamp |
| 9 | after-source identity checklist complete | YES | E-B35b `SOURCE_IDENTITY_COMPLETE` |
| 10 | no synthetic contamination policy acknowledged | YES | freeze + stamp ack |
| 11 | `E-B_FORMAL_READY = NO` | YES (locked) | correct |
| 12 | `MAY_ENTER_FORMAL_OBSERVATION_WINDOW = NO` | YES (locked) | correct |
| 13 | acquisition plan artifacts present (E-B26 02) | YES (plan exists) | design package present |

```text
CONJUNCTION_SURFACE_LOOKS_GREEN = YES
```

## 2. Why this window still keeps READY = NO

Per E-B36 scope (stamp issuance only · no acquisition):

```text
ACQUISITION_EXECUTION_READY = NO

Reasons (process · not invented blockers):
  - E-B36 forbids auto-opening acquisition from stamp alone
  - dedicated Acquisition Entry Review window required before flip
  - no acquisition / After capture executed in this window
```

```text
WAITING_FOR_ACQUISITION_ENTRY_REVIEW = YES
```

## 3. Explicit non-actions

```text
DO NOT start Product After acquisition here.
DO NOT generate After bodies.
DO NOT bind / score / open Formal Observation.
DO NOT call LM Studio / API / LLM.
DO NOT modify backend/app.
```

## 4. Stamp

```text
ACQUISITION_ENTRY_STATUS_EVALUATED = YES
ACQUISITION_EXECUTION_READY        = NO
ACQUISITION_EXECUTED               = NO
WAITING_FOR_ACQUISITION_ENTRY_REVIEW = YES
E-B_FORMAL_READY                   = NO
FORMAL_OBSERVATION                 = NOT_STARTED
```
