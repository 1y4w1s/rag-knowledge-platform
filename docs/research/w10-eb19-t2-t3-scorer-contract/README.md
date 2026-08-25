# W10 E-B19 · T2/T3 Scorer Contract Design

> **Does:** tests/docs only — freeze T2/T3 scorer **contract** schema · deterministic `score_t2` / `score_t3` · F1–F8 edge fixtures · remaining blockers.  
> **Does not:** LLM / NLI / fuzzy / Critic oracle · formal observation write · flip `T2_T3_SCORER_IMPLEMENTED` · flip `E-B_FORMAL_READY` · `backend/app`.

## Status freeze

```text
Claim Gold                         = YES
Product After Capture              = YES
BINDING_GATE_IMPLEMENTED           = YES   (E-B17)
GOLD_AFTER_BINDING_COMPATIBLE      = YES   (E-B18 BP-A rebound pack)
T2_T3_SCORER_CONTRACT_DESIGNED     = YES   (this window)
T2_T3_SCORER_IMPLEMENTED           = NO
E-B_FORMAL_READY                   = NO
MAY_ENTER_FORMAL_OBSERVATION_WINDOW = NO
B2_PRIME_AFTER_SNAPSHOTS           = BLOCKING_RESIDUAL
```

## Inputs / outputs

### T2

```text
score_t2(observed_after, claim_gold, binding_policy=BP-A)
  → unsupported_rate | NOT_APPLICABLE | INVALID | INCOMPATIBLE | NOT_OBSERVED
```

| Rule | Detail |
|---|---|
| Denom | gold `asserted_claims` |
| Numerator | `label == unsupported` only |
| `unverifiable` | in denom；**not** in numerator |
| Denom 0 | `NOT_APPLICABLE`（≠ 0.0 PASS） |
| Labels | **only** from gold |

### T3

```text
score_t3(..., final_citations, gated_chunks_ordered, align_bucket)
  → grounded_rate + per_claim {g1, g2, grounded}
```

| Gate | Definition |
|---|---|
| **G1** | `label==supported` ∧ `supporting_evidence_ids` non-empty ⊆ observed gated ids |
| **G2** | ≥1 `final_citations` id ∈ supporting set **or** legal `[片段N]` → supporting id（exact） |
| **grounded** | `G1 ∧ G2` |
| keep-all | full chip table alone **≠** G2 true |

## Matching（forbidden）

| Allowed | Forbidden |
|---|---|
| `case_id` + Binding Gate | LLM judge |
| `claim_id` identity | NLI auto-label |
| Exact evidence / chunk id equality | Fuzzy / embedding match |
| Ledger labels only | Critic `expected_action` / oracle |

## Module

- `backend/tests/w10_eb19_t2_t3_scorer_contract.py`
- `backend/tests/test_w10_eb19_t2_t3_scorer_contract.py`
- `protocol_version = w10_eb19_t2_t3_scorer_contract_v1`
- `artifact_kind = T2_T3_SCORER_CONTRACT`
- Results always `formal_measurement=false` · `contract_only=true`

## Edge cases（E-B8 F1–F8 + S1）

| Id | Expect |
|---|---|
| F1 | unsupported · G1 F · G2 F |
| F2 | unsupported + shape cite · G1 F · G2 F |
| F3 | supported · no pointer · G1 T · G2 F |
| F4 | supported · wrong chip · G1 T · G2 F |
| F5 | unverifiable · T2 rate 0 · not grounded |
| F6 | empty claims · T2/T3 `NOT_APPLICABLE` |
| F7 | keep-all chips · unsupported · not grounded |
| F8 | pool drift · `INVALID` |
| S1 | supported ∧ correct pointer · grounded |

## Remaining blockers（post E-B19）

| Id | Status | Note |
|---|---|---|
| AG-3 | PARTIAL | contract YES；`T2_T3_SCORER_IMPLEMENTED=NO` |
| AG-4 | OPEN | E-B15 degraded/refusal vs BP-B presence |
| AG-5 | PARTIAL | live/authorized After rebound absent |
| AG-6 | OPEN | E-B6 synthetic ≠ claim_texts |
| B2′ / S2 / A4 / GATE | locked | formal window closed |
| SCORER | CONTRACT_ONLY | formulas executable in tests；not formal wire-up |

## Acceptance

```text
cd backend
python -m pytest tests/test_w10_eb19_t2_t3_scorer_contract.py -q
```

## Stop

```text
E-B_FORMAL_READY = NO
T2_T3_SCORER_IMPLEMENTED = NO
DO NOT write reserved formal result.
DO NOT call LLM / NLI.
DO NOT claim product faithfulness from contract scores.
```
