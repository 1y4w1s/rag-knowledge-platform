# W10 E-B22 · Formal Wireup Contract

> **Does:** tests/docs only — implement E-B21 formal wireup as a **wiring
> contract**: L-Obs composer skeleton · L-Score companion · compose validators ·
> invalid-reason allowlist · BP-A/B/C isolation · flip
> `FORMAL_WIREUP_IMPLEMENTED=YES`.
>
> **Does not:** LLM / LM Studio · formal observation run · reserved formal
> result write · flip `E-B_FORMAL_READY` · modify `backend/app` · claim product
> faithfulness · treat E-B18 compat pack as live product observation.

## Status freeze

```text
Claim Gold                         = YES
Product After Capture              = YES
BINDING_GATE_IMPLEMENTED           = YES   (E-B17)
GOLD_AFTER_BINDING_COMPATIBLE      = YES   (E-B18 BP-A rebound pack)
T2_T3_SCORER_CONTRACT_DESIGNED     = YES   (E-B19)
T2_T3_SCORER_IMPLEMENTED           = YES   (E-B20 · tests-only)
FORMAL_WIREUP_DESIGNED             = YES   (E-B21)
FORMAL_WIREUP_IMPLEMENTED          = YES   (this window · tests-only contract)
E-B_FORMAL_READY                   = NO
MAY_ENTER_FORMAL_OBSERVATION_WINDOW = NO
B2_PRIME_AFTER_SNAPSHOTS           = BLOCKING_RESIDUAL
```

## Module

- `backend/tests/w10_eb22_formal_wireup_contract.py`
- `backend/tests/test_w10_eb22_formal_wireup_contract.py`
- Contract protocol: `w10_eb22_formal_wireup_contract_v1`
- L-Score: `w10_eb22_formal_t2_t3_score_v1` · `FORMAL_T2_T3_SCORE_RESULT`

## Documents

1. [`01-contract-and-composer.md`](01-contract-and-composer.md) — L-Obs / L-Score · gate · allowlist · BP  
2. [`02-blockers-and-gates.md`](02-blockers-and-gates.md) — remaining blockers · stop rules  

## Parent chain

| Window | Role |
|---|---|
| E-B2 | Observation envelope freeze (identity unchanged) |
| E-B17–E-B18 | Binding + BP-A compat pack |
| E-B19–E-B20 | Scorer contract + tests-only implementation |
| E-B21 | Formal wireup **design** freeze |
| E-B22 | Formal wireup **contract implementation** (this window) |

## Compose ≠ write

`compose_l_obs()` / `compose_l_score()` are **tests-only** helpers that
materialize skeleton / companion **artifact shape**. They do **not** mean:

- formal measurement completed
- reserved result written
- product faithfulness proven

Even if a future window unlocks `E-B_FORMAL_READY`, an **independent write
step** is still required before any reserved formal observation result exists.
Formal observation = NOT_STARTED · reserved result = ABSENT.

## Acceptance

```text
cd backend
python -m pytest tests/test_w10_eb22_formal_wireup_contract.py tests/test_w10_eb22_post_review_cleanup.py -q
```

## Stop

```text
E-B_FORMAL_READY = NO
MAY_ENTER_FORMAL_OBSERVATION_WINDOW = NO
FORMAL_OBSERVATION = NOT_STARTED
RESERVED_RESULT = ABSENT
DO NOT write w10-eb2-generation-observation-result.json.
DO NOT call LLM / LM Studio.
DO NOT claim product faithfulness from wireup contract.
```
