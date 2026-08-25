# 02 — Edge cases · remaining blockers · next window

## 1. F1–F8 (+ S1) contract expectations

| Id | T2 | G1 | G2 | grounded | Case status |
|---|---|---|---|---|---|
| F1 hallucination no cite | 1.0 | F | F | F | OBSERVED_SLOT |
| F2 hallucination + chip | 1.0 | F | F | F | OBSERVED_SLOT |
| F3 supported no pointer | 0.0 | T | F | F | OBSERVED_SLOT |
| F4 wrong pointer | 0.0 | T | F | F | OBSERVED_SLOT |
| F5 unverifiable | 0.0 | F | F | F | OBSERVED_SLOT |
| F6 empty claims / refusal denom | — | — | — | — | NOT_APPLICABLE |
| F7 keep-all unsupported | 1.0 | F | F | F | OBSERVED_SLOT |
| F8 pool / bind drift | — | — | — | — | INVALID |
| S1 success | 0.0 | T | T | T | OBSERVED_SLOT |

Fixtures live in `edge_case_fixtures()`（tests module）.

## 2. Remaining blockers after E-B19

| Id | Status | Clears formal? |
|---|---|---|
| AG-3 | PARTIAL（contract designed；implemented NO） | No |
| AG-4 | OPEN | No |
| AG-5 | PARTIAL（compat rebound ≠ live rebound） | No |
| AG-6 | OPEN | No |
| B2′ | BLOCKING_RESIDUAL | No |
| S2 | NO | No |
| A4 | NO | No |
| GATE | `E-B_FORMAL_READY=NO` | No |
| SCORER | CONTRACT_ONLY | No — need formal wire-up window |

```text
Full formal YES ⇏ Claim Gold ∧ After Harness ∧ Binding ∧ Compat ∧ Scorer Contract
Full formal YES  ⇒ those ∧ SCORER_IMPLEMENTED wire-up ∧ unlock ∧ honest targets
```

## 3. Recommended next atomic window

**Recommended:** E-B20 — tests-only scorer **implementation gate** wiring  
`grounding_observation_status=OBSERVED_SLOT` honesty fields onto E-B2 slots for BP-A compat pack **without** reserved formal write / without flipping `E-B_FORMAL_READY`.

**Alternate:** live/authorized After rebound materialization（AG-5 residual）under owner auth — still no formal YES alone.

## 4. Stop

```text
E-B_FORMAL_READY = NO
T2_T3_SCORER_IMPLEMENTED = NO
```
