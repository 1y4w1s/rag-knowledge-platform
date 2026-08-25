# 04 — Future Evaluation Extension Plan

> Multi-track evaluation architecture.  
> **Designed only — DO NOT execute in this window.**

## 1. Motivation

One Formal Product track cannot answer all questions:

- Product faithfulness under authorized After (Narrow Formal).
- Agent capability under Local Model First development.
- Provider / backend comparison for ops decisions.

Mixing these into one rate table destroys provenance honesty.

---

## 2. Track design (future)

### Track A — Product Formal Evaluation

```text
Name:     Product Formal Evaluation
Purpose:  Binding + T2/T3 under authorized Product After
Source:   Formal Evaluation Source
            (authorized Product After only · stamp pending;
             Narrow capture path candidate A = E-B15 harness
             validated Product After capture path candidate
             · ≠ Formal Evaluation Source until approved)
Gates:    AFTER_SOURCE_APPROVED · E-B_FORMAL_READY · entry checklist
Status:   NOT_STARTED · FORMAL_OBSERVATION = NOT_STARTED
```

### Track B — Local Model Capability Evaluation

```text
Name:     Local Model Capability Evaluation
Purpose:  Measure Agent / generation quality on pinned local stack
Source:   Development Generation Backend with LOCAL_MODEL_PINNED=YES
Artifact: Separate from Product Formal reserved results
Status:   DESIGNED_NOT_EXECUTED
```

Requires (before any claim):

- Pin surface from `02-local-model-strategy.md` fully filled.
- Explicit non-formal labeling (`formal_measurement=false` unless later
  owner opens a Local Formal scope — not Narrow A).
- No silent merge into Track A denominators.

### Track C — Provider Comparison

```text
Name:     Provider Comparison
Purpose:  Side-by-side API / local / harness behavior for ops choice
Source:   Multiple backends · each labeled
Status:   DESIGNED_NOT_EXECUTED
```

Rules:

- Comparative tables must name backend identity per column.
- Never average across backends into one “product faithfulness” number.
- Not a substitute for Track A authorization.

---

## 3. Cross-track contamination (forbidden)

| Pattern | Verdict |
|---|---|
| Report Track B rates as Track A Formal | **VETO** |
| Blend API + local + harness in one unsupported_rate | **VETO** |
| Use Track C winner as automatic Formal Evaluation Source | **VETO** (needs stamp) |
| Equate E-B15 harness with Formal Evaluation Source | **VETO** (E-B15 harness = validated Product After capture path candidate only) |
| Keep tracks labeled + separate artifacts | **ALLOWED** |

---

## 4. Sequencing (advisory · not a schedule commitment)

```text
Now (E-B28):     separation designed · tracks sketched · execute none
Near:            owner stamp path for Track A
                 (capture path candidate A = E-B15 harness validated
                  Product After capture path candidate · still ≠ Formal
                  Evaluation Source until approved)
Later (optional): pin local model → open Track B planning window
Later (optional): Track C when ops needs provider decision evidence
Never:           flip E-B_FORMAL_READY from Track B/C alone
```

---

## 5. Stamp

```text
EVALUATION_EXTENSION_DESIGNED   = YES
TRACK_A_EXECUTED                = NO
TRACK_B_EXECUTED                = NO
TRACK_C_EXECUTED                = NO
LOCAL_MODEL_EVALUATION_TRACK    = DESIGNED_NOT_EXECUTED
E-B_FORMAL_READY                = NO
FORMAL_OBSERVATION              = NOT_STARTED
```
