# 02 — Formal Entry blocker inventory

> Focus: blockers that prevent
> `MAY_ENTER_FORMAL_OBSERVATION_WINDOW=YES` / `E-B_FORMAL_READY=YES`.  
> Design window only — no clearance executed here.

## 1. Priority Formal Entry blockers

| Id | Name | Status (post E-B22) | Clears Formal Entry alone? | Residual |
|---|---|---|---|---|
| **B2′** | Formal / authorized After evidence | **BLOCKING_RESIDUAL** | No | Product After for formal denominator + reserved-write unlock still missing; harness READY ≠ formal After |
| **AG-3** | Wireup → Formal write | **PARTIAL** | No | Wireup contract YES (E-B22); reserved formal write / owner unlock still NO |
| **AG-5** | Live authorized After rebound | **PARTIAL** | No | E-B18 compat rebound YES; live/authorized product After rebound gold NO |
| **S2** | Dual-suite packaging authorization | **NO** | No | Empty-gate material YES; `E_B_S2_PACKAGING_AUTHORIZED=NO` |
| **A4** | Live LLM product After | **NO** | No | Owner auth absent; `llm_called` freeze still forces false |

```text
Full Formal Entry YES ⇏ Gold ∧ Harness ∧ Binding ∧ Scorer ∧ Wireup
Full Formal Entry YES  ⇒ those ∧ B2′ authorized After ∧ AG-5 live rebound
                           ∧ AG-3 write unlock ∧ (S2 if T4) ∧ (A4 if live)
                           ∧ owner unlock ∧ honest validity
```

## 2. Peer residuals (still open; not sole Formal Entry focus)

| Id | Status | Note |
|---|---|---|
| AG-1 | `CLEARED_FOR_BP_A_REBOUND` | Live unrebounded path still non-binding |
| AG-2 | `MITIGATED_BY_CODEC` | Prefix normalize; do not regress |
| AG-4 | **OPEN** | E-B15 degraded/refusal vs BP-B claim-text presence |
| AG-6 | **OPEN** | E-B6 synthetic ≠ E-B12B claim_texts — never formal T2/T3 pair |
| GATE | `E-B_FORMAL_READY=NO` | Correct lock |
| Reserved Write | **BLOCKED** | Result path absent |

## 3. Blocker delta vs E-B22

| Item | E-B22 end | E-B23 end | Change |
|---|---|---|---|
| `FORMAL_WIREUP_IMPLEMENTED` | YES | YES | unchanged |
| `E-B22_CLEANUP_COMPLETE` | YES (input freeze) | YES | unchanged |
| AG-3 | PARTIAL (contract YES · write NO) | PARTIAL (same class) | **no clearance** — inventory only |
| AG-5 | PARTIAL | PARTIAL | **no clearance** |
| B2′ | BLOCKING_RESIDUAL | BLOCKING_RESIDUAL | **no clearance** |
| S2 | NO | NO | **no clearance** |
| A4 | NO | NO | **no clearance** |
| `E-B23_READINESS_DESIGNED` | — | **YES** | **new** (design stamp) |
| `E-B_FORMAL_READY` | NO | NO | **must stay NO** |
| `MAY_ENTER_FORMAL_OBSERVATION_WINDOW` | NO | NO | **must stay NO** |
| `FORMAL_OBSERVATION` | NOT_STARTED | NOT_STARTED | unchanged |
| `RESERVED_RESULT` | ABSENT | ABSENT | unchanged |

**Summary:** E-B23 does **not** clear Formal Entry blockers. It freezes the
authorization gate contract and checklist so future clearance windows know
exactly what must flip.

## 4. What is *not* a Formal Entry blocker anymore

| Cleared / ready material | Still insufficient for |
|---|---|
| Claim gold annotated | Live After bind (AG-5) |
| Empty-gate cases material | S2 packaging auth / T4 Full |
| After capture harness | B2′ formal After + write unlock |
| Binding gate + BP-A compat pack | Live product rebound / faithfulness claim |
| Scorer + wireup tests-only | Reserved formal write under unlocked gate |

## 5. Recommended clearance order (suggestion only · not this window)

1. **Choose Formal scope first:** Narrow (T1–T3 · no T4 · no A4) vs Full (+S2) vs Live (+A4 thaw).  
2. **B2′ + AG-5:** owner-authorized After capture → rebound gold → BindingVerdict `BOUND` under declared BP.  
3. **AG-3 write path:** reserved formal write unlock plan under `E-B_FORMAL_READY` (separate from compose).  
4. **If T4:** S2 dual-suite packaging authorization.  
5. **If live LLM:** A4 owner auth + honest `llm_called` thaw contract.  
6. Re-run gate → only then consider `MAY_ENTER_FORMAL_OBSERVATION_WINDOW=YES`.

## 6. Stamp

```text
BLOCKER_INVENTORY_FROZEN            = YES
E-B_FORMAL_READY                    = NO
MAY_ENTER_FORMAL_OBSERVATION_WINDOW = NO
B2_PRIME_AFTER_SNAPSHOTS            = BLOCKING_RESIDUAL
```
