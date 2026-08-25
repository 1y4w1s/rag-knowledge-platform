# 02 — Remaining blockers · next window

> Design / readiness only. Gates remain locked.

## 1. What E-B21 cleared

| Item | Value |
|---|---|
| Formal wireup architecture | LAAE compose frozen |
| Scorer → E-B2 entry path | Status projection + companion L-Score (W1) |
| Formal field map | L-Obs fill rules + L-Score required fields |
| `measurement_validity` for T2/T3 | Gate ∧ bind ∧ gold-only ∧ companion ∧ BP honesty |
| BP-A/B/C formal isolation | Declare · stratify · no silent blend |
| `FORMAL_WIREUP_DESIGNED` | **YES** |
| `FORMAL_WIREUP_IMPLEMENTED` | **NO** |
| `E-B_FORMAL_READY` | **NO** (correct) |

## 2. Remaining blockers

### 2.1 Wireup-specific

| Id | Status | Clears formal alone? | Note |
|---|---|---|---|
| **FORMAL_WIREUP** | DESIGNED · **impl OPEN** | No | Need companion score contract + composer + validators |
| **AG-3** | PARTIAL | No | Implemented tests-only; formal wire-up still NO |
| **E-B2 score fields** | GAP MITIGATED BY W1 | No | v1 has no t2_*/t3_* numerics; companion required |
| **llm_called freeze** | OPEN for A4 | No | E-B2 validator forces `llm_called=false`; live formal needs thaw |

### 2.2 Binding / material residuals

| Id | Status | Clears formal alone? |
|---|---|---|
| AG-4 | OPEN | No — E-B15 degraded/refusal vs BP-B presence |
| AG-5 | PARTIAL | No — compat rebound ≠ live/authorized After rebound |
| AG-6 | OPEN | No — E-B6 synthetic ≠ claim_texts |

### 2.3 Broader formal residuals

| Id | Status | Clears formal alone? |
|---|---|---|
| B2′ | BLOCKING_RESIDUAL | No — authorized After + reserved write unlock |
| S2 | NO | No — empty-gate packaging unauthorized |
| A4 | NO | No — live LLM owner auth absent |
| GATE | `E-B_FORMAL_READY=NO` | Correct lock |

```text
Full formal YES ⇏ Claim Gold ∧ After ∧ Binding ∧ Compat ∧ Scorer Implemented ∧ Wireup Designed
Full formal YES  ⇒ those ∧ wireup implemented ∧ live/authorized targets ∧ unlock ∧ honest validity
```

## 3. Recommended next atomic window

**Recommended: E-B22 — Formal Wireup Contract (tests/docs only)**

Freeze companion `FORMAL_T2_T3_SCORE_RESULT` schema + L-Obs projection composer
stubs + `invalid_reasons` allowlist extension + BP isolation validator.
Still: `formal_measurement` hard-locked false unless gate YES; **no** reserved
file write; **no** `E-B_FORMAL_READY` flip.

**Alternate:** live/authorized After rebound materialization (AG-5 residual)
under owner auth — clears live bind path; still does not alone flip formal YES.

## 4. Explicit non-goals until unlock

```text
DO NOT flip E-B_FORMAL_READY on design alone.
DO NOT write w10-eb2-generation-observation-result.json.
DO NOT set measurement_valid=true.
DO NOT call LLM / LM Studio.
DO NOT treat E-B18/E-B20 scores as product faithfulness.
DO NOT modify backend/app for observation hooks.
```

## 5. Gate stamp

```text
FORMAL_WIREUP_DESIGNED              = YES
FORMAL_WIREUP_IMPLEMENTED           = NO
T2_T3_SCORER_IMPLEMENTED            = YES (tests-only)
E-B_FORMAL_READY                    = NO
MAY_ENTER_FORMAL_OBSERVATION_WINDOW = NO
B2_PRIME_AFTER_SNAPSHOTS            = BLOCKING_RESIDUAL
```

## 6. Stop

```text
E-B_FORMAL_READY = NO
```
