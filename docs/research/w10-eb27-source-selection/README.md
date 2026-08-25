# W10 E-B27 · Product After Source Selection (Design)

> **Does:** Narrow Formal **source selection design** only — criteria, decision
> matrix over E-B26 Options A–D, primary **candidate** pick, acquisition
> boundary freeze, and owner-stamp **preparation** (schema, not issuance).
>
> **Does not:** acquisition execution · capture Product After · call LLM /
> LM Studio / API · generate After data · formal / reserved result · flip
> `E-B_FORMAL_READY` · create owner approval stamp · set
> `AFTER_SOURCE_APPROVED=YES` · modify `backend/app`.

## Status freeze (this window)

```text
E-B26_ACQUISITION_PLAN_DESIGNED     = YES   (input)
E-B27_SOURCE_SELECTION_DESIGNED     = YES   (this window)
SOURCE_SELECTED_DESIGN              = YES   (candidate only)
OPTION_SELECTED                     = A     (PRIMARY_CANDIDATE_SOURCE · design)
SOURCE_APPROVED                     = NO
AFTER_SOURCE_APPROVED               = NO    (unchanged · must stay NO)
ACQUISITION_EXECUTION_READY         = NO    (unchanged · must stay NO)
E-B_FORMAL_READY                    = NO    (unchanged · must stay NO)
FORMAL_OBSERVATION                  = NOT_STARTED
RESERVED_RESULT                     = ABSENT
```

## Parent chain

| Window | Role |
|---|---|
| E-B24 | Narrow Formal scope + After authorization contract |
| E-B25 | After source authorization review → `AFTER_SOURCE_APPROVED=NO` |
| E-B26 | Acquisition planning · Options A–D analyzed · `OPTION_SELECTED=NONE` |
| **E-B27** | **Source selection design** (this window) · candidate ≠ approval |

## Documents

1. [`01-source-selection-criteria.md`](01-source-selection-criteria.md) — criteria + weights (no pick)
2. [`02-option-decision-matrix.md`](02-option-decision-matrix.md) — A–D re-score
3. [`03-selected-source-rationale.md`](03-selected-source-rationale.md) — primary candidate + blockers
4. [`04-acquisition-boundary.md`](04-acquisition-boundary.md) — execution ≠ formal
5. [`05-owner-stamp-preparation.md`](05-owner-stamp-preparation.md) — stamp fields prep (no stamp)

## Narrow Formal context (inherited)

```text
Scope name:     Narrow Formal Observation (first)
Binding:        BP-A only (observed_after)
Suite:          w9_critic_frozen_12
Cases measured: C01–C11
Cases excluded: C12 (INELIGIBLE / not claim denom)
Targets:        T1 · T2 · T3
Excluded:       T4 / S2 empty-gate packaging · A4 live LLM
```

## Selection verdict (this window)

```text
PRIMARY_CANDIDATE_SOURCE            = A
  = selected design candidate only
  name                              = E-B15 product stream harness
  role                              = validated Product After capture path candidate
  NOTE                              = E-B15 harness ≠ Formal Evaluation Source
  NOTE                              = PRIMARY_CANDIDATE_SOURCE=A is a selected design candidate only
                                      ⇏ source approved / formal eligible / After approved
SOURCE_SELECTED_DESIGN              = YES
SOURCE_APPROVED                     = NO
AFTER_SOURCE_APPROVED               = NO
ACQUISITION_EXECUTION_READY         = NO
E-B_FORMAL_READY                    = NO
FORMAL_OBSERVATION                  = NOT_STARTED
```

**May owner treat this as approval?** **NO** — `PRIMARY_CANDIDATE_SOURCE=A` is a selected design candidate only.

**May acquisition execution start now?** **NO** — stamp absent · mode/identity
not frozen · checklist from E-B26 still incomplete.

**May Formal Observation start now?** **NO.**

## Explicit non-goals

```text
DO NOT call LM Studio / API / LLM.
DO NOT generate After data / capture records.
DO NOT write formal observation result.
DO NOT write reserved result.
DO NOT flip E-B_FORMAL_READY.
DO NOT create owner approval stamp.
DO NOT set AFTER_SOURCE_APPROVED / SOURCE_APPROVED = YES.
DO NOT modify backend/app.
DO NOT treat candidate selection as authorization.
DO NOT equate E-B15 harness with Formal Evaluation Source
    (harness = validated Product After capture path candidate only).
```

## Stop

```text
E-B27_SOURCE_SELECTION_DESIGNED = YES
SOURCE_SELECTED_DESIGN          = YES
SOURCE_APPROVED                 = NO
ACQUISITION_EXECUTION_READY     = NO
E-B_FORMAL_READY                = NO
FORMAL_OBSERVATION              = NOT_STARTED
NEXT = owner stamp issuance / capture-mode+model freeze
       (still not acquisition execution until checklist green;
        still not formal observation)
```
