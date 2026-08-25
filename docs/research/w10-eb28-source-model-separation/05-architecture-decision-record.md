# 05 — Architecture Decision Record (ADR)

> E-B28 binding decision. Design-only; no gate flips beyond this ADR’s
> *designed* stamps.

## ADR title

**Separate Formal Evaluation Source from Development Generation Backend**

## Status

```text
Accepted (architecture freeze · design)
SOURCE_MODEL_SEPARATION_DESIGNED = YES
```

## Context

1. Project long-term goal is **not** permanent sole dependence on one API model.
2. Historical Development / product generation used cloud APIs (e.g. DeepSeek);
   pricing and availability are external variables.
3. E-B27 selected `PRIMARY_CANDIDATE_SOURCE=A` —
   **E-B15 harness validated Product After capture path candidate**
   (not Formal Evaluation Source; candidate only). Options B (LM Studio)
   and C (API) are OUT for Narrow PRIMARY candidacy.
4. Engineering still needs Local Model First for Agent / prompt experiments
   (`LOCAL_MODEL_AS_NARROW_FORMAL_PRIMARY=NO`).
5. Confusing “开发模型” / E-B15 harness with “Formal Evaluation Source”
   would invalidate T2/T3 provenance and owner authorization.

## Decision

```text
DECISION:
  Formal Evaluation Source  and  Development Generation Backend
  are separate architectural roles.

  They MUST NOT substitute for each other without a new owner contract
  and (if needed) Narrow Formal scope revision.
```

### Implications

| Role | May use | May claim |
|---|---|---|
| Formal Evaluation Source | Authorized Product After only | Formal T2/T3 · reserved results |
| Development Generation Backend | LM Studio / local LLM / API / harness (as **dev** surface) | Informal iteration · smoke · Agent work |
| E-B15 harness (Option A) | Capture-path candidacy only until stamped | Validated Product After capture path candidate · **not** Formal Evaluation Source |

### Related freezes

```text
LOCAL_MODEL_STRATEGY                 = PLANNED
LOCAL_MODEL_AS_NARROW_FORMAL_PRIMARY = NO
LOCAL_MODEL_EVALUATION_TRACK         = DESIGNED_NOT_EXECUTED
API_AS_SOLE_EXPERIMENT_BASE          = REJECTED_BY_POLICY
PRIMARY_CANDIDATE_SOURCE             = A
  (= E-B15 harness validated Product After capture path candidate
   · ≠ Formal Evaluation Source · unchanged from E-B27)
FORMAL_SOURCE_APPROVED               = NO
AFTER_SOURCE_APPROVED                = NO
SOURCE_APPROVED                      = NO
ACQUISITION_EXECUTION_READY          = NO
E-B_FORMAL_READY                     = NO
FORMAL_OBSERVATION                   = NOT_STARTED
```

## Reason

```text
REASON:
  Long-term maintainability (Local First for development)
  +
  Experimental credibility (Formal provenance / reproducibility / authorization)
```

## Consequences

**Positive**

- Dev can migrate to LM Studio + GLM/Qwen/Llama without rewriting Formal history.
- Formal rates stay honest under owner stamp + identity freeze.
- Future Tracks B/C can open without contaminating Track A.

**Negative / cost**

- Two (or more) configuration surfaces to document.
- Formal progress does not automatically validate Local Agent quality (and vice versa).
- Extra discipline required in reports and CI labels.

**Out of scope of this ADR**

- Calling LM Studio or any API.
- Generating After / Formal Observation.
- Approving Formal Evaluation Source / flipping ready gates.
- Changing `backend/app` LLM defaults.

## Alternatives considered

| Alternative | Why rejected |
|---|---|
| Single “the model” for both Formal and Dev | Provenance collapse; API risk; E-B27 B/C conflict |
| Make LM Studio Formal PRIMARY now | Violates E-B24/E-B27 Narrow freeze (A4-class) |
| Ban all API forever | Unnecessary; API OK for Dev + future authorized tracks |
| Delay Local First until Formal done | Leaves Development hostage to API variables |

## References

- `docs/research/w10-eb27-source-selection/` — candidate A · B/C OUT for Narrow
- `docs/research/w10-eb25-after-source-authorization-review/03-synthetic-vs-product-boundary.md`
- `docs/research/w10-eb24-narrow-formal-preparation/` — Narrow scope · A4 excluded
- This folder `01`–`04`

## Final stamp (E-B28)

```text
Decision: Formal Evaluation Source 与 Development Generation Backend 分离。

Terminology:
  E-B15 harness ≠ Formal Evaluation Source
  E-B15 harness = validated Product After capture path candidate

SOURCE_MODEL_SEPARATION_DESIGNED         = YES
FORMAL_SOURCE_APPROVED                   = NO
LOCAL_MODEL_STRATEGY                     = PLANNED
LOCAL_MODEL_AS_NARROW_FORMAL_PRIMARY     = NO
E-B_FORMAL_READY                         = NO
FORMAL_OBSERVATION                       = NOT_STARTED
ACQUISITION_EXECUTION_READY              = NO
AFTER_SOURCE_APPROVED                    = NO
SOURCE_APPROVED                          = NO
```
