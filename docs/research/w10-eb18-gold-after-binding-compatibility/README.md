# W10 E-B18 · Gold↔After Binding Compatibility Materialization

> **Does:** tests/docs only — BP-A rebound pack · three-hash contract · compatibility validator · `after_snapshot.case_id ↔ gold.case_id`.  
> **Does not:** LLM · T2/T3 scorer · formal observation write · flip `E-B_FORMAL_READY` · `backend/app`.

## Status freeze

```text
Claim Gold                         = YES
Product After Capture              = YES
BINDING_GATE_IMPLEMENTED           = YES   (E-B17)
COMPATIBILITY_MATERIALIZED         = YES   (this window)
GOLD_AFTER_BINDING_COMPATIBLE      = YES   (BP-A rebound pack)
LIVE_EB15_X_EB12B_COMPATIBLE       = NO    (unrebounded live path)
T2_T3_SCORER_IMPLEMENTED           = NO
E-B_FORMAL_READY                   = NO
MAY_ENTER_FORMAL_OBSERVATION_WINDOW = NO
B2_PRIME_AFTER_SNAPSHOTS           = BLOCKING_RESIDUAL
```

## What this window solves

| Id | Before (E-B17) | After (E-B18) |
|---|---|---|
| **AG-1** | OPEN — payload hash ≠ content-string hash | **CLEARED_FOR_BP_A_REBOUND** — rebound gold uses observed-content codec |
| **AG-3** | PARTIAL — gate YES; scorer NO | **PARTIAL** — gate + compatibility YES; scorer still NO |
| **AG-5** | OPEN — no BP-A rebound gold | **PARTIAL** — compatibility pack rebound YES; live product After rebound NO |

## Binding artifact（BP-A）

```text
after_snapshot.case_id  ↔  gold.case_id
binding_policy          = observed_after
```

- Module: `backend/tests/w10_eb18_gold_after_binding_compatibility.py`
- Fixture: `backend/tests/fixtures/l4_critic/w10-eb-bp-a-binding-compatibility-v1.json`
- Pack `artifact_kind = GOLD_AFTER_BINDING_COMPATIBILITY`
- Per-case embeds E-B17 `AFTER_GOLD_BINDING` artifact + rebound gold + after stub

## Hash generation & verification（三者分离）

| Space | Generate | Verify |
|---|---|---|
| **gold_ledger_hash** | BP-B: claim_texts payload；**BP-A rebound: content string** (bare hex) | BP-A: `== observed_content_digest(after)` after normalize |
| **observed_content_hash** | `sha256(canonical_json(content))`；wire `sha256:{hex}` | wire ↔ recompute；BP-A also ↔ gold.content_sha256 |
| **evidence_pool_hash** | `sha256([{chunk_id,content},…])` bare hex | gold.pool == observed.pool；gold.ids ⊆ observed.ids |

**Hard rule:** never naive `==` across spaces. Unrebounded E-B12B × E-B15 remains `INCOMPATIBLE` under BP-A (honesty probe in tests).

## Compatibility validator

`validate_compatibility_case` / `validate_compatibility_pack`:

1. case_id identity（after ↔ gold ↔ binding artifact）
2. three-hash generation/verify helpers
3. gold `kind=observed_after`
4. E-B17 `validate_binding(..., BP_A) → BOUND`
5. honesty：`llm_called=false` · `formal_measurement=false` · `after_source=compatibility_materialization_author_owned`

Does **not** emit `unsupported_rate` / `grounded_rate` / formal scores.

## Remaining blockers（post E-B18）

| Id | Status | Note |
|---|---|---|
| AG-1 | CLEARED_FOR_BP_A_REBOUND | unrebounded live path still non-binding |
| AG-2 | MITIGATED_BY_CODEC | prefix normalize |
| AG-3 | PARTIAL | scorer still NO |
| AG-4 | OPEN | E-B15 degraded/refusal vs BP-B presence |
| AG-5 | PARTIAL | live/authorized After rebound absent |
| AG-6 | OPEN | E-B6 synthetic ≠ claim_texts |
| B2′ / S2 / A4 / GATE / SCORER | locked | formal window closed |

## Acceptance

```text
cd backend
python -m pytest tests/test_w10_eb18_gold_after_binding_compatibility.py -q
```

## Stop

```text
E-B_FORMAL_READY = NO
DO NOT score formal T2/T3.
DO NOT write reserved formal result.
DO NOT call LLM.
DO NOT claim product LLM faithfulness from this pack.
```
