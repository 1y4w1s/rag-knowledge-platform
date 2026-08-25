# W10 E-B32 · Source Identity + Capture Freeze Preparation

> **Does:** Design Human Freeze Execution **preparation assets** only —
> source identity template · capture mode template · runtime/reproducibility
> template · human checklist · freeze execution entry gate.  
> **Preparation ≠ Freeze** · **Template ≠ Filled Record** · **Designed ≠ Approved**
>
> **Does not:** source approval · owner stamp issuance · acquisition execution ·
> After capture · formal observation · flip any approval/ready gate · call
> LM Studio / API / LLM · modify `backend/app`.

## Status freeze (this window)

```text
OWNER_STAMP_PRE_ISSUANCE_VALIDATED  = YES   (E-B31 · unchanged)
STAMP_SCHEMA_COMPLETE               = NO
SOURCE_IDENTITY_COMPLETE            = NO
CAPTURE_MODE_FROZEN                 = NO
MAY_ISSUE_APPROVED_OWNER_STAMP      = NO

E-B32_FREEZE_PREPARATION_DESIGNED   = YES   (this window)
SOURCE_IDENTITY_TEMPLATE_READY      = YES
CAPTURE_TEMPLATE_READY              = YES
RUNTIME_TEMPLATE_READY              = YES
HUMAN_CHECKLIST_READY               = YES
MAY_ENTER_HUMAN_FREEZE_EXECUTION    = YES

OWNER_AUTHORIZATION_ISSUED          = NO
SOURCE_APPROVED                     = NO
AFTER_SOURCE_APPROVED               = NO
ACQUISITION_EXECUTION_READY         = NO
E-B_FORMAL_READY                    = NO
FORMAL_OBSERVATION                  = NOT_STARTED

PRIMARY_CANDIDATE_SOURCE            = A     (selected design candidate only)
```

```text
PRIMARY_CANDIDATE_SOURCE=A is a selected design candidate only.
  ⇏  source approved
  ⇏  formal eligible
  ⇏  After approved
E-B15 harness = validated Product After capture path candidate
  ≠ Formal Evaluation Source
```

## Parent chain

| Window | Role |
|---|---|
| E-B27 | Source selection · `PRIMARY_CANDIDATE_SOURCE=A` (selected design candidate only) |
| E-B28 | Formal source ≠ Development backend |
| E-B29 | Owner authorization **contract** designed |
| E-B30 | Owner stamp **issuance protocol** designed |
| E-B31 | Pre-issuance readiness **audit** |
| **E-B32** | **Freeze preparation templates** (this window) |

## Documents

1. [`01-source-identity-freeze-template.md`](01-source-identity-freeze-template.md) — source identity field template
2. [`02-capture-mode-freeze-template.md`](02-capture-mode-freeze-template.md) — capture mode field template
3. [`03-runtime-and-reproducibility-freeze-template.md`](03-runtime-and-reproducibility-freeze-template.md) — runtime/repro surface
4. [`04-human-freeze-checklist.md`](04-human-freeze-checklist.md) — human checklist (unchecked)
5. [`05-freeze-execution-entry-gate.md`](05-freeze-execution-entry-gate.md) — `MAY_ENTER_HUMAN_FREEZE_EXECUTION`

## Core separations (must not collapse)

```text
candidate ≠ approved source
capture path candidate ≠ Formal Evaluation Source
template ≠ frozen record
Preparation ≠ Freeze
Designed ≠ Approved
MAY_ENTER_HUMAN_FREEZE_EXECUTION  ⇏  SOURCE_APPROVED
MAY_ENTER_HUMAN_FREEZE_EXECUTION  ⇏  E-B_FORMAL_READY
```

## Explicit non-goals

```text
DO NOT create a real owner stamp artifact.
DO NOT auto-generate source_identity or fill owner fields.
DO NOT set freeze_status = FROZEN as achieved in this window.
DO NOT set CAPTURE_MODE_FROZEN = YES.
DO NOT set OWNER_AUTHORIZATION_ISSUED = YES.
DO NOT set SOURCE_APPROVED / AFTER_SOURCE_APPROVED = YES.
DO NOT set E-B_FORMAL_READY = YES.
DO NOT set ACQUISITION_EXECUTION_READY = YES.
DO NOT execute acquisition / After capture / formal observation.
DO NOT call LM Studio / API / LLM.
DO NOT modify backend/app.
DO NOT auto-tick human checklist boxes.
```

## Stop

```text
E-B32_FREEZE_PREPARATION_DESIGNED = YES
MAY_ENTER_HUMAN_FREEZE_EXECUTION  = YES

SOURCE_IDENTITY_COMPLETE          = NO
CAPTURE_MODE_FROZEN               = NO
OWNER_AUTHORIZATION_ISSUED        = NO
SOURCE_APPROVED                   = NO
AFTER_SOURCE_APPROVED             = NO
ACQUISITION_EXECUTION_READY       = NO
E-B_FORMAL_READY                  = NO
FORMAL_OBSERVATION                = NOT_STARTED
```
