# 04 — Formal entry checklist + blocker inventory

> Pre-entry checklist for **Narrow Formal Observation** (BP-A · C01–C11 ·
> T1–T3 · no S2 · no A4).  
> All items remain **unchecked** in E-B24 (preparation only).  
> Blockers are **inventoried**, not cleared.

## 1. Mandatory entry checklist

Enter Formal Observation execution **only after** every box is checked in a
future authorization window:

```text
[ ] Claim Gold frozen
    — E-B12B ledger frozen for C01–C11 claim texts
    — C12 asserted_claims=[] honored
    — no silent re-annotation mid-run

[ ] After source approved
    — owner stamp under 03-after-source-authorization.md
    — source identity · capture mode declared
    — B2′ residual cleared for Narrow denom (authorized After on disk)

[ ] Binding compatible
    — BP-A only · BindingVerdict BOUND per C01–C11
    — AG-5 live/authorized rebound (not E-B18 compat-only narrative)
    — three-hash / codec honesty preserved

[ ] Scorer available
    — E-B20 executors + E-B22 L-Score companion path
    — rates only in FORMAL_T2_T3_SCORE_RESULT companion
    — no rates stuffed into E-B2 notes

[ ] Reserved write authorized
    — independent write step unlocked
    — compose ≠ write honesty preserved
    — AG-3 write path YES (not wireup-only)

[ ] Formal gate unlocked
    — MAY_ENTER_FORMAL_OBSERVATION_WINDOW = YES (owner stamp)
    — E-B_FORMAL_READY flip plan executed only when write is intended
    — scope = Narrow Formal as defined in 01/02 (not Full / not A4)
```

## 2. Narrow-specific confirmations (also unchecked)

```text
[ ] targets_measured = {T1, T2, T3} only
[ ] measured cases = C01–C11; C12 = INELIGIBLE
[ ] S2 packaging not claimed
[ ] A4 live LLM not claimed · no LLM call under freeze
[ ] BP-A declared · no silent BP blend
[ ] no synthetic / compat pack mistaken as product evidence
```

## 3. Blocker inventory (do not clear in E-B24)

> Organize only. Status values unchanged from E-B23 end-state.

| Id | Name | Status | Blocks Narrow Formal Entry? | Residual (unchanged) |
|---|---|---|---|---|
| **B2′** | Formal / authorized After evidence | **BLOCKING_RESIDUAL** | **Yes** | Authorized After for C01–C11 formal denom missing; harness ≠ formal After |
| **AG-5** | Live / authorized After rebound | **PARTIAL** | **Yes** | Compat pack rebound YES; live/authorized product After rebound gold NO |
| **AG-3** | Wireup → Formal write | **PARTIAL** | **Yes** | Wireup contract YES (E-B22); reserved formal write / owner unlock still NO |

### Scope-excluded blockers (not required to clear for *this* Narrow scope)

| Id | Status | Note for Narrow Formal |
|---|---|---|
| **S2** | NO | **Excluded** from Narrow — do not clear for this scope; still blocks Full/T4 |
| **A4** | NO | **Excluded** from Narrow — do not clear for this scope; still blocks live LLM |

### Peer residuals (open; not sole Narrow Entry focus)

| Id | Status | Note |
|---|---|---|
| AG-1 | `CLEARED_FOR_BP_A_REBOUND` | Unrebounded live path still non-binding |
| AG-2 | `MITIGATED_BY_CODEC` | Do not regress |
| AG-4 | OPEN | Degraded/refusal vs BP-B presence — BP-B out of Narrow default |
| AG-6 | OPEN | E-B6 synthetic ≠ claim_texts — contamination veto |
| GATE | `E-B_FORMAL_READY=NO` | Correct lock |
| Reserved Write | BLOCKED | Result path absent |

## 4. Blocker delta vs E-B23

| Item | E-B23 end | E-B24 end | Change |
|---|---|---|---|
| B2′ | BLOCKING_RESIDUAL | BLOCKING_RESIDUAL | **no clearance** — inventoried for Narrow |
| AG-5 | PARTIAL | PARTIAL | **no clearance** |
| AG-3 | PARTIAL (contract YES · write NO) | PARTIAL (same) | **no clearance** |
| S2 | NO | NO | **no clearance** · **scope-excluded** |
| A4 | NO | NO | **no clearance** · **scope-excluded** |
| `E-B24_SCOPE_DEFINED` | — | **YES** | **new** (design stamp) |
| `E-B_FORMAL_READY` | NO | NO | **must stay NO** |
| `MAY_ENTER_FORMAL_OBSERVATION_WINDOW` | NO | NO | **must stay NO** |
| `FORMAL_OBSERVATION` | NOT_STARTED | NOT_STARTED | unchanged |
| `RESERVED_RESULT` | ABSENT | ABSENT | unchanged |

**Summary:** E-B24 defines Narrow Formal scope and freezes the entry checklist.
It does **not** clear Formal Entry blockers and does **not** start observation.

## 5. Suggested clearance order (suggestion only · not this window)

1. **B2′:** owner-authorize After capture for C01–C11 under declared non-A4 mode.  
2. **AG-5:** rebound claim gold to authorized After content hashes → BP-A `BOUND`.  
3. **AG-3 write:** reserved formal write unlock plan under `E-B_FORMAL_READY`.  
4. Owner stamp checklist §1 all green → only then consider `MAY_ENTER…=YES`.  
5. **Do not** open S2 or A4 unless scope is explicitly widened beyond Narrow.

## 6. E-B24 preparation result

```text
§1 checklist items checked:           0 / 6
E-B24_SCOPE_DEFINED                   = YES
E-B_FORMAL_READY                      = NO
MAY_ENTER_FORMAL_OBSERVATION_WINDOW   = NO
FORMAL_OBSERVATION                    = NOT_STARTED
RESERVED_RESULT                       = ABSENT
B2_PRIME_AFTER_SNAPSHOTS              = BLOCKING_RESIDUAL
AG-5                                  = PARTIAL
AG-3                                  = PARTIAL
```

## 7. Stop

```text
DO NOT open Formal Observation execution from this window.
DO NOT write formal / reserved results.
DO NOT call LLM / open A4 / open S2.
DO NOT clear B2′ / AG-5 / AG-3.
NEXT = authorization clearance windows only (After → rebound → write unlock).
```
