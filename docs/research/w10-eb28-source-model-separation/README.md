# W10 E-B28 · Formal Source vs Development Model Separation (Design)

> **Does:** Architecture freeze — separate **Formal Evaluation Source** from
> **Development Generation Backend**; local-model strategy (planned);
> API dependency risk; future multi-track evaluation extension; ADR.
>
> **Does not:** acquisition execution · call LM Studio / API / LLM ·
> generate After · formal / reserved result · flip any ready gate ·
> modify `backend/app` · owner stamp issuance · treat E-B27 candidate
> (E-B15 harness validated Product After capture path candidate) as
> Formal Evaluation Source.

## Status freeze (this window)

```text
E-B27_SOURCE_SELECTION_DESIGNED     = YES   (input)
PRIMARY_CANDIDATE_SOURCE            = A     (selected design candidate only · design)
SOURCE_APPROVED                     = NO
AFTER_SOURCE_APPROVED               = NO
ACQUISITION_EXECUTION_READY         = NO
E-B_FORMAL_READY                    = NO
FORMAL_OBSERVATION                  = NOT_STARTED

E-B28_SOURCE_MODEL_SEPARATION_DESIGNED = YES   (this window)
SOURCE_MODEL_SEPARATION_DESIGNED       = YES
FORMAL_SOURCE_APPROVED                 = NO
LOCAL_MODEL_STRATEGY                   = PLANNED
LOCAL_MODEL_AS_NARROW_FORMAL_PRIMARY   = NO
LOCAL_MODEL_EVALUATION_TRACK           = DESIGNED_NOT_EXECUTED
```

## Parent chain

| Window | Role |
|---|---|
| E-B25 | After source authorization → `AFTER_SOURCE_APPROVED=NO` |
| E-B26 | Acquisition planning · Options A–D |
| E-B27 | Source selection · `PRIMARY_CANDIDATE_SOURCE=A` · not approved |
| **E-B28** | **Formal source ≠ Development backend** (this window) |

## Documents

1. [`01-formal-source-vs-development-model-boundary.md`](01-formal-source-vs-development-model-boundary.md) — two concepts · non-substitution
2. [`02-local-model-strategy.md`](02-local-model-strategy.md) — LM Studio + GLM/Qwen/Llama · pin surface
3. [`03-api-dependency-risk-analysis.md`](03-api-dependency-risk-analysis.md) — price / availability / reproducibility
4. [`04-future-evaluation-extension-plan.md`](04-future-evaluation-extension-plan.md) — Tracks A/B/C · not executed
5. [`05-architecture-decision-record.md`](05-architecture-decision-record.md) — ADR + gate stamps

## Core decision (one line)

```text
Formal Evaluation Source  ≠  Development Generation Backend
```

- **Formal Evaluation Source** → authorized Product After · Binding · T2/T3 ·
  provenance (requires stamp; currently **not** approved).
- **Development Generation Backend** → daily Agent/prompt/tool experiments ·
  Local First OK.
- Neither substitutes for the other without a new owner contract.

**Terminology (anti-ambiguity):**

```text
E-B15 harness  ≠  Formal Evaluation Source
E-B15 harness  =  validated Product After capture path candidate
                  (PRIMARY_CANDIDATE_SOURCE=A · design · not approved)
```

## Inheritance from E-B27 (unchanged)

```text
PRIMARY_CANDIDATE_SOURCE = A
  = selected design candidate only
  = E-B15 harness validated Product After capture path candidate
  ≠ Formal Evaluation Source
SOURCE_APPROVED          = NO
```

```text
PRIMARY_CANDIDATE_SOURCE=A is a selected design candidate only.
  ⇏  source approved
  ⇏  formal eligible
  ⇏  After approved
```

E-B27 Option B (LM Studio) / C (API) remain **OUT** for Narrow Formal
PRIMARY capture-path candidacy. They may still be used as
**Development Generation Backend** and/or future evaluation tracks —
never as silent Formal Evaluation Source.

## Explicit non-goals

```text
DO NOT call LM Studio / API / LLM.
DO NOT generate After / Product After / formal observation.
DO NOT write reserved result.
DO NOT flip E-B_FORMAL_READY / AFTER_SOURCE_APPROVED / SOURCE_APPROVED.
DO NOT flip ACQUISITION_EXECUTION_READY.
DO NOT modify backend/app.
DO NOT execute Local Model Evaluation Track.
DO NOT treat Development Backend runs as Formal After.
```

## Stop

```text
SOURCE_MODEL_SEPARATION_DESIGNED = YES
FORMAL_SOURCE_APPROVED           = NO
LOCAL_MODEL_STRATEGY             = PLANNED
LOCAL_MODEL_AS_NARROW_FORMAL_PRIMARY = NO
E-B_FORMAL_READY                 = NO
FORMAL_OBSERVATION               = NOT_STARTED
NEXT = owner stamp / capture-mode freeze for candidate A
       (A = E-B15 harness validated Product After capture path candidate
        · ≠ Formal Evaluation Source)
       OR (separate window) Local Model Strategy pin-surface detailing
       — still not acquisition execution; still not formal observation
```
