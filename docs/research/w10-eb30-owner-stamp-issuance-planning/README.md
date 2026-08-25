# W10 E-B30 · Owner Stamp Issuance Planning

> **Does:** Design the **final protocol shape** for Owner Stamp Issuance —
> schema contract, source-identity freeze plan, capture-mode freeze plan,
> issuance gate, and post-issuance boundary.
>
> **Does not:** issue a real owner stamp · flip `SOURCE_APPROVED` /
> `AFTER_SOURCE_APPROVED` · acquisition execution · After capture ·
> formal observation · call LM Studio / API / LLM · modify `backend/app`.

## Status freeze (this window)

```text
OWNER_AUTHORIZATION_DESIGNED        = YES   (E-B29 input)
PRIMARY_CANDIDATE_SOURCE            = A     (selected design candidate only)
SOURCE_MODEL_SEPARATION_DESIGNED    = YES   (E-B28)

OWNER_STAMP_ISSUANCE_DESIGNED       = YES   (this window)
OWNER_AUTHORIZATION_ISSUED          = NO
SOURCE_APPROVED                     = NO
AFTER_SOURCE_APPROVED               = NO
ACQUISITION_EXECUTION_READY         = NO
E-B_FORMAL_READY                    = NO
CAPTURE_MODE_FROZEN                 = NO
FORMAL_OBSERVATION                  = NOT_STARTED
```

## Parent chain

| Window | Role |
|---|---|
| E-B26 | Acquisition planning · early stamp sketch |
| E-B27 | Source selection · `PRIMARY_CANDIDATE_SOURCE=A` |
| E-B28 | Formal source ≠ Development backend |
| E-B29 | Owner authorization **contract** designed |
| **E-B30** | Owner stamp **issuance protocol** designed (this window) |

## Documents

1. [`01-owner-stamp-schema-design.md`](01-owner-stamp-schema-design.md) — final field surface · types · honesty rules
2. [`02-source-identity-freeze-plan.md`](02-source-identity-freeze-plan.md) — when source identity is complete
3. [`03-capture-mode-freeze-plan.md`](03-capture-mode-freeze-plan.md) — mode enum · freeze plan · still not frozen
4. [`04-issuance-gate-design.md`](04-issuance-gate-design.md) — `OWNER_AUTHORIZATION_ISSUED=YES` preconditions
5. [`05-post-issuance-boundary.md`](05-post-issuance-boundary.md) — issued ≠ formal ready · remaining chain

## Core separations (must not collapse)

```text
schema designed            ≠  stamp issued
issuance designed          ≠  authorization issued
OWNER_AUTHORIZATION_ISSUED ≠  SOURCE_APPROVED alone (synonym only after match)
authorization issued       ≠  acquisition executed
authorization issued       ≠  After captured
authorization issued       ≠  Binding / Scoring done
authorization issued       ≠  E-B_FORMAL_READY / formal observation
capture-mode plan          ≠  CAPTURE_MODE_FROZEN
PRIMARY candidate A        ≠  Formal Evaluation Source
```

**Terminology (anti-ambiguity, inherited E-B28/E-B29):**

```text
PRIMARY_CANDIDATE_SOURCE=A is a selected design candidate only.
PRIMARY_CANDIDATE_SOURCE = A
  = E-B15 harness validated Product After capture path candidate
  ≠ Formal Evaluation Source
  ≠ owner-approved After
  ⇏  source approved
  ⇏  formal eligible
  ⇏  After approved
```

## Protocol surface (design summary)

An **issued** stamp (future human action — **not** this window) must bind
all fields in `01`, under freeze/completeness rules in `02`–`03`, only when
the issuance gate in `04` is green. After issuance, `05` still requires
After capture → Binding → Scoring → Formal gate before any formal ready.

## Explicit non-goals

```text
DO NOT issue a real owner stamp.
DO NOT set OWNER_AUTHORIZATION_ISSUED = YES.
DO NOT set SOURCE_APPROVED / AFTER_SOURCE_APPROVED = YES.
DO NOT set CAPTURE_MODE_FROZEN = YES.
DO NOT set ACQUISITION_EXECUTION_READY = YES.
DO NOT flip E-B_FORMAL_READY / MAY_ENTER_FORMAL_OBSERVATION_WINDOW.
DO NOT execute acquisition / After capture / formal observation.
DO NOT call LM Studio / API / LLM.
DO NOT modify backend/app.
DO NOT treat E-B29 designed contract as issued stamp.
```

## Stop

```text
OWNER_STAMP_ISSUANCE_DESIGNED  = YES
OWNER_AUTHORIZATION_ISSUED     = NO
SOURCE_APPROVED                = NO
AFTER_SOURCE_APPROVED          = NO
ACQUISITION_EXECUTION_READY    = NO
E-B_FORMAL_READY               = NO
CAPTURE_MODE_FROZEN            = NO
FORMAL_OBSERVATION             = NOT_STARTED
NEXT = human-facing issuance window that fills frozen identities +
       capture_mode + issues stamp under 04 gate
       — still not acquisition execution;
         still not formal observation
```
