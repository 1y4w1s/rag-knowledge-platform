# W10 E-B24 · Narrow Formal Observation Preparation

> **Does:** preparation / design only — define the **first Narrow Formal**
> Observation **scope** (cases, BP, exclusions, After authorization rules,
> entry checklist). Organizes remaining Formal Entry blockers without clearing
> them.
>
> **Does not:** formal observation run · formal result write · reserved result ·
> flip `E-B_FORMAL_READY` · set `MAY_ENTER_FORMAL_OBSERVATION_WINDOW=YES` ·
> call LLM / LM Studio · open A4 · open S2 · modify `backend/app` · clear
> B2′ / AG-5 / AG-3.

## Status freeze (this window)

```text
E-B23_READINESS_DESIGNED           = YES   (input)
E-B24_SCOPE_DEFINED                = YES   (this window)
E-B_FORMAL_READY                   = NO
MAY_ENTER_FORMAL_OBSERVATION_WINDOW = NO
FORMAL_OBSERVATION                 = NOT_STARTED
RESERVED_RESULT                    = ABSENT
B2_PRIME_AFTER_SNAPSHOTS           = BLOCKING_RESIDUAL
AG-5                               = PARTIAL
AG-3                               = PARTIAL
S2                                 = NO    (excluded from Narrow scope)
A4                                 = NO    (excluded from Narrow scope)
```

## Parent chain

| Window | Role |
|---|---|
| E-B12B | Claim gold annotated (C01–C11 claim denom; C12 empty) |
| E-B15 | Product After capture harness (Scheme A) |
| E-B17–E-B18 | Binding gate + BP-A compat pack |
| E-B19–E-B20 | T2/T3 scorer (tests-only) |
| E-B21–E-B22 | Formal wireup (tests-only) |
| E-B23 | Authorization readiness + `MAY_ENTER…` contract |
| **E-B24** | **Narrow Formal scope definition** (this window) |

## Documents

1. [`01-narrow-scope-definition.md`](01-narrow-scope-definition.md) — BP-A · C01–C11 · exclusions  
2. [`02-target-case-selection.md`](02-target-case-selection.md) — case / target freeze design  
3. [`03-after-source-authorization.md`](03-after-source-authorization.md) — when After may enter formal denom  
4. [`04-formal-entry-checklist.md`](04-formal-entry-checklist.md) — pre-entry checklist + blocker inventory  

## Narrow Formal (declared)

```text
Scope name:     Narrow Formal Observation (first)
Binding:        BP-A only (observed_after)
Suite:          w9_critic_frozen_12
Cases measured: C01–C11
Cases excluded: C12 (INELIGIBLE / not claim denom)
Targets:        T1 · T2 · T3
Excluded:       T4 / S2 empty-gate packaging · A4 live LLM
```

## Verdict (binary)

```text
E-B24_SCOPE_DEFINED                 = YES
E-B_FORMAL_READY                    = NO
MAY_ENTER_FORMAL_OBSERVATION_WINDOW = NO
FORMAL_OBSERVATION                  = NOT_STARTED
```

**May enter Narrow Formal execution?** **NO** — scope is defined; entry
blockers (B2′ · AG-5 · AG-3 write) remain open. This window is preparation
only.

## Explicit non-goals

```text
DO NOT write w10-eb2-generation-observation-result.json.
DO NOT flip E-B_FORMAL_READY.
DO NOT set MAY_ENTER_FORMAL_OBSERVATION_WINDOW=YES.
DO NOT call LLM / LM Studio / open A4.
DO NOT authorize or package S2 empty-gate.
DO NOT clear B2′ / AG-5 / AG-3.
DO NOT modify backend/app.
DO NOT execute measurement / scoring as formal.
DO NOT treat E-B18 compat pack as product faithfulness.
```

## Stop

```text
E-B24_SCOPE_DEFINED = YES
E-B_FORMAL_READY = NO
FORMAL_OBSERVATION = NOT_STARTED
NEXT = clearance / authorization windows only (not measurement)
```
