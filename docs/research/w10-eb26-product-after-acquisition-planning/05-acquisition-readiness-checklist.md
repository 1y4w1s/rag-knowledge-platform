# 05 — Acquisition readiness checklist

> Entry checklist **before** any Product After **acquisition execution** window.  
> This window only designs the checklist — **no boxes are claimed checked** as
> execution-ready (all remain unchecked for acquisition start).

## 1. Checklist (pre-acquisition-execution)

```text
[ ] source selected
[ ] owner approval defined
[ ] model identity frozen
[ ] capture mode frozen
[ ] gold rebinding procedure ready
[ ] no synthetic contamination
[ ] formal gate still locked
```

## 2. Interpretation of each item

| Item | Means “ready” when… | Current (E-B26 end) |
|---|---|---|
| **source selected** | Owner/process picks exactly one acquisition option (A/B/C/D or revised) consistent with Narrow scope | **Unchecked** — E-B26 analyzed only (`OPTION_SELECTED=NONE`) |
| **owner approval defined** | Stamp schema + predicate exist (`03`); issuance may still be pending for execution | **Schema designed**; **stamp not issued** — treat acquisition-start as needing issued stamp + selected source |
| **model identity frozen** | Exact `model_identity` string chosen and recorded for the suite run | **Unchecked** |
| **capture mode frozen** | Exact Narrow-allowed `capture_mode` id chosen; A4/S2-as-T1–T3 excluded | **Unchecked** |
| **gold rebinding procedure ready** | Procedure in `04` accepted as the post-capture path | **Designed** — execution of rebound still NO |
| **no synthetic contamination** | Plan forbids E-B6/E-B18 bodies as Product After; suite policy documented | **Policy YES** · **suite proof pending acquisition** |
| **formal gate still locked** | `E-B_FORMAL_READY=NO` ∧ `MAY_ENTER_FORMAL_OBSERVATION_WINDOW=NO` ∧ no reserved formal write | **Locked (correct)** |

## 3. Hard locks that must remain during acquisition execution

Even after the checklist above is satisfied for **acquisition**:

```text
E-B_FORMAL_READY                    = NO   (unless a later dedicated unlock window)
MAY_ENTER_FORMAL_OBSERVATION_WINDOW = NO   (until full formal entry checklist)
FORMAL_OBSERVATION                  = NOT_STARTED
RESERVED_RESULT                     = ABSENT
DO NOT write formal observation result
DO NOT call LLM / LM Studio unless selected mode + separate auth explicitly allow
     (Narrow still excludes A4)
```

Acquisition execution ≠ Formal Observation.

## 4. Roll-up

```text
ACQUISITION_EXECUTION_READY = NO
  reason: source not selected · owner stamp not issued · model/mode not frozen
FORMAL_OBSERVATION_READY    = NO
E-B26_ACQUISITION_PLAN_DESIGNED = YES
AFTER_SOURCE_APPROVED           = NO
E-B_FORMAL_READY                = NO
```

## 5. Allowed next window class (suggestion only)

1. **Source selection + owner stamp issuance** (still not formal).  
2. **Acquisition execution** only after checklist §1 can be honestly checked.  
3. **Gold rebound execution** after Product After exists.  
4. **Re-authorization review** (E-B25-class) before any formal entry flip.

Forbidden next class until After approved + formal entry locks clear:

- Formal observation / reserved write / `E-B_FORMAL_READY=YES`

## 6. Stamp

```text
ACQUISITION_READINESS_CHECKLIST_DESIGNED = YES
ACQUISITION_EXECUTION_READY              = NO
AFTER_SOURCE_APPROVED                    = NO
E-B_FORMAL_READY                         = NO
FORMAL_OBSERVATION                       = NOT_STARTED
```
