# W10 E-B20 · T2/T3 Scorer Implementation

> **Does:** tests/docs only — land E-B19 contract as tests-only `execute_score_t2` /
> `execute_score_t3` · implementation artifact + validation · BP-A compat pack
> scoring with E-B2 `grounding_observation_status` honesty · flip
> `T2_T3_SCORER_IMPLEMENTED=YES`.
>
> **Does not:** LLM / NLI / fuzzy / Critic oracle · formal observation write ·
> flip `E-B_FORMAL_READY` · `backend/app`.

## Status freeze

```text
Claim Gold                         = YES
Product After Capture              = YES
BINDING_GATE_IMPLEMENTED           = YES   (E-B17)
GOLD_AFTER_BINDING_COMPATIBLE      = YES   (E-B18 BP-A rebound pack)
T2_T3_SCORER_CONTRACT_DESIGNED     = YES   (E-B19)
T2_T3_SCORER_IMPLEMENTED           = YES   (this window · tests-only)
E-B_FORMAL_READY                   = NO
MAY_ENTER_FORMAL_OBSERVATION_WINDOW = NO
B2_PRIME_AFTER_SNAPSHOTS           = BLOCKING_RESIDUAL
```

## Module

- `backend/tests/w10_eb20_t2_t3_scorer_implementation.py`
- `backend/tests/test_w10_eb20_t2_t3_scorer_implementation.py`
- `protocol_version = w10_eb20_t2_t3_scorer_implementation_v1`
- `artifact_kind = T2_T3_SCORER_IMPLEMENTATION`
- Results always `formal_measurement=false` · `implementation_only=true` · `contract_only=false`

## Executors

| Executor | Input | Output |
|---|---|---|
| `execute_score_t2` | observed_after + claim_gold (+ BP) | unsupported_rate / status |
| `execute_score_t3` | + final_citations / gated_chunks / align_bucket | grounded_rate + per_claim G1∧G2 |

Rules inherited from E-B19 (unchanged formulas):

- Labels **only** from gold (never re-label)
- Exact evidence / chunk id equality (no fuzzy / NLI / LLM judge)
- `unverifiable` ∈ T2 denom；∉ unsupported numerator
- Denom 0 → `NOT_APPLICABLE`（≠ 0.0/1.0 PASS）
- keep-all chips alone ≠ G2 true

## Honesty · E-B2 slot wiring

| Scorer status | `grounding_observation_status` |
|---|---|
| `OBSERVED_SLOT` | `OBSERVED_SLOT` |
| `NOT_APPLICABLE` / `NOT_OBSERVED` | `NOT_OBSERVED` |
| `INVALID` / `INCOMPATIBLE` | `INELIGIBLE` |

`OBSERVED_SLOT` on BP-A compat pack means **formulas applied after BOUND** on
author-owned After bodies — **not** product LLM faithfulness, **not** formal ready.

Optional `attach_gold_supporting_pointers=True` is wiring-only G2 proof
(`t3_pointer_source=gold_supporting_ids_wiring_only`).

## Remaining blockers（post E-B20）

| Id | Status | Note |
|---|---|---|
| AG-3 | PARTIAL | implemented tests-only；formal wire-up NO |
| AG-4 | OPEN | E-B15 degraded/refusal vs BP-B |
| AG-5 | PARTIAL | live/authorized After rebound absent |
| AG-6 | OPEN | E-B6 synthetic ≠ claim_texts |
| B2′ / S2 / A4 / GATE | locked | formal window closed |
| SCORER | IMPLEMENTED_TESTS_ONLY | not formal measurement |
| FORMAL_WIREUP | OPEN | no reserved formal write |

```text
Full formal YES ⇏ Claim Gold ∧ After ∧ Binding ∧ Compat ∧ Scorer Implemented
Full formal YES  ⇒ those ∧ formal wire-up ∧ unlock ∧ honest live targets
```

## Acceptance

```text
cd backend
python -m pytest tests/test_w10_eb20_t2_t3_scorer_implementation.py -q
```

## Stop

```text
E-B_FORMAL_READY = NO
DO NOT write reserved formal result.
DO NOT call LLM / NLI.
DO NOT claim product faithfulness from implementation scores.
```
