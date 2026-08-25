# W10 E-B29 · Owner Authorization & After Source Preparation

> **Does:** Prepare the **owner authorization contract** for Narrow Formal
> Product After acquisition — stamp model, After-source identity checklist,
> capture-mode freeze template, acquisition entry gate, blocker resolution
> plan.
>
> **Does not:** acquisition execution · generate After · call LM Studio /
> API / LLM · write formal / reserved result · issue a real owner stamp ·
> flip any ready / approved gate · modify `backend/app`.

## Status freeze (this window)

```text
SOURCE_MODEL_SEPARATION_DESIGNED    = YES   (E-B28 input)
PRIMARY_CANDIDATE_SOURCE            = A     (selected design candidate only)
SOURCE_APPROVED                     = NO
AFTER_SOURCE_APPROVED               = NO
ACQUISITION_EXECUTION_READY         = NO
E-B_FORMAL_READY                    = NO
FORMAL_OBSERVATION                  = NOT_STARTED

E-B29_OWNER_AUTHORIZATION_DESIGNED  = YES   (this window)
OWNER_AUTHORIZATION_DESIGNED        = YES
OWNER_AUTHORIZATION_ISSUED          = NO
CAPTURE_MODE_FROZEN                 = NO    (template only · not frozen)
```

## Parent chain

| Window | Role |
|---|---|
| E-B25 | After source authorization review → `AFTER_SOURCE_APPROVED=NO` |
| E-B26 | Acquisition planning · stamp schema sketch · readiness checklist |
| E-B27 | Source selection · `PRIMARY_CANDIDATE_SOURCE=A` · not approved |
| E-B28 | Formal source ≠ Development backend · separation designed |
| **E-B29** | **Owner authorization contract preparation** (this window) |

## Documents

1. [`01-owner-authorization-model.md`](01-owner-authorization-model.md) — stamp fields · predicates · gate separations
2. [`02-after-source-identity-checklist.md`](02-after-source-identity-checklist.md) — identity surface for candidate A
3. [`03-capture-mode-freeze-template.md`](03-capture-mode-freeze-template.md) — freeze template · not executed freeze
4. [`04-acquisition-entry-gate.md`](04-acquisition-entry-gate.md) — what must be green before acquisition execution
5. [`05-blocker-resolution-plan.md`](05-blocker-resolution-plan.md) — ordered clearance · still not execution

## Core separations (must not collapse)

```text
authorization          ≠  formal ready
approved source        ≠  completed observation
PRIMARY candidate A    ≠  Formal Evaluation Source
E-B15 harness          ≠  Formal Evaluation Source
stamp designed         ≠  stamp issued
capture-mode template  ≠  capture-mode frozen
acquisition entry gate ≠  acquisition executed
```

**Terminology (anti-ambiguity, inherited E-B28):**

```text
PRIMARY_CANDIDATE_SOURCE=A is a selected design candidate only.
PRIMARY_CANDIDATE_SOURCE = A
  = selected design candidate only
  = E-B15 harness validated Product After capture path candidate
  ≠ Formal Evaluation Source
  ≠ owner-approved After
  ⇏  source approved
  ⇏  formal eligible
  ⇏  After approved
```

## Mandatory owner stamp surface (design)

An issued stamp (future human action — **not** this window) must bind:

| Element | Role |
|---|---|
| **source identity** | Named Product After provenance id |
| **capture path identity** | Capture-path candidate id (A = E-B15 harness validated Product After capture path candidate · ≠ Formal Evaluation Source) |
| **run identity** | Suite / batch id approved |
| **base sha** | Code/config tree sha |
| **model/backend identity** | Frozen generator identity (or explicit `none_no_llm` / N/A) |
| **capture mode** | Owner-approved Narrow mode id |
| **authorization status** | Explicit APPROVED / DENIED / WITHHELD with scope |

## Inheritance (unchanged)

```text
PRIMARY_CANDIDATE_SOURCE         = A     (selected design candidate only)
SOURCE_MODEL_SEPARATION_DESIGNED = YES
SOURCE_APPROVED                  = NO
AFTER_SOURCE_APPROVED            = NO
ACQUISITION_EXECUTION_READY      = NO
E-B_FORMAL_READY                 = NO
```

```text
PRIMARY_CANDIDATE_SOURCE=A is a selected design candidate only.
E-B15 harness = validated Product After capture path candidate
  ≠ Formal Evaluation Source
```

## Explicit non-goals

```text
DO NOT execute acquisition.
DO NOT generate After / Product After.
DO NOT call LM Studio / API / LLM.
DO NOT write formal observation / reserved result.
DO NOT issue a real owner approval stamp.
DO NOT set SOURCE_APPROVED / AFTER_SOURCE_APPROVED = YES.
DO NOT set ACQUISITION_EXECUTION_READY = YES.
DO NOT flip E-B_FORMAL_READY / MAY_ENTER_FORMAL_OBSERVATION_WINDOW.
DO NOT modify backend/app.
DO NOT treat E-B15 harness / E-B27 candidate / E-B28 separation as approval.
```

## Stop

```text
OWNER_AUTHORIZATION_DESIGNED     = YES
OWNER_AUTHORIZATION_ISSUED       = NO
SOURCE_APPROVED                  = NO
AFTER_SOURCE_APPROVED            = NO
ACQUISITION_EXECUTION_READY      = NO
E-B_FORMAL_READY                 = NO
FORMAL_OBSERVATION               = NOT_STARTED
NEXT = human owner stamp issuance for candidate A
       (fill 01 stamp · check 02 · freeze 03)
       OR capture-mode + model identity freeze window
       — still not acquisition execution;
         still not formal observation
```
