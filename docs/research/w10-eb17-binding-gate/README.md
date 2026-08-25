# W10 E-B17 · After↔Gold Binding Gate（LAAE）

> **Does:** tests-only Binding Gate — artifact · hash-space separation · BP-A/B/C validator.  
> **Does not:** LLM · T2/T3 formal scoring · formal observation write · flip `E-B_FORMAL_READY` · `backend/app`.

## Status freeze

```text
Claim Gold                         = YES
Product After Capture              = YES
BINDING_GATE_IMPLEMENTED           = YES   (this window)
GOLD_AFTER_BINDING_COMPATIBLE      = NO    (live E-B12B × E-B15 material)
T2_T3_SCORER_IMPLEMENTED           = NO
E-B_FORMAL_READY                   = NO
MAY_ENTER_FORMAL_OBSERVATION_WINDOW = NO
B2_PRIME_AFTER_SNAPSHOTS           = BLOCKING_RESIDUAL
```

## Binding artifact

```text
after_snapshot.case_id  ↔  gold.case_id
```

Contract module: `backend/tests/w10_eb17_binding_gate.py`  
`artifact_kind = AFTER_GOLD_BINDING` · `protocol_version = w10_eb17_binding_gate_v1`

Required fields: `after_case_id`, `gold_case_id`, `binding_policy`, plus optional hash/pool slots.

## Hash semantics（三者分离）

| Space | Producer today | Codec | Bound object |
|---|---|---|---|
| **gold_ledger_hash** | E-B12B `content_sha256` | bare 64-hex | BP-B: claim_texts payload；BP-A rebound: content string |
| **observed_content_hash** | E-B15 `after_content_hash` | `sha256:{hex}` | `state["content"]` string |
| **evidence_pool_hash** | E-B12B `pool_sha256` | bare 64-hex | gated excerpts `[{chunk_id,content}]` |

**Rule:** never naively `==` across spaces. Prefix normalize (`sha256:` strip) only inside one declared space.

## BP-A / BP-B / BP-C

| Policy | Role | Body bind | May prove |
|---|---|---|---|
| **BP-A `observed_after`** | **formal candidate** | gold `kind=observed_after` + content-string hash equal (normalized) + pool ⊆ | product-path faithfulness（需 owner auth） |
| **BP-B `synthetic_authored`** | **test only** | ledger claim_texts self-hash + claim text **presence** in After + pool | protocol wiring only；**not** model quality |
| **BP-C `refusal_exclude`** | **T4 exclusion** | skip T2/T3 | refusal behavior |

## Validator

`validate_binding(...)` → `BOUND | INVALID | EXCLUDED_T4 | INCOMPATIBLE`  
Deterministic · zero LLM · does **not** emit `unsupported_rate` / `grounded_rate`.

## Remaining blockers（post E-B17）

| Id | Status | Note |
|---|---|---|
| AG-1 | OPEN | payload hash ≠ content-string hash on live material |
| AG-2 | MITIGATED_BY_CODEC | prefix normalize in gate；does not clear AG-1 |
| AG-3 | PARTIAL | gate YES；scorer NO |
| AG-4 | OPEN | E-B15 degraded/refusal fails BP-B presence |
| AG-5 | OPEN | no BP-A rebound gold yet |
| AG-6 | OPEN | E-B6 synthetic ≠ E-B12B claim_texts |
| B2′ / S2 / A4 / Gate | still locked | formal window closed |

## Acceptance

```text
cd backend
python -m pytest tests/test_w10_eb17_binding_gate.py -q
```

## Stop

```text
E-B_FORMAL_READY = NO
DO NOT score formal T2/T3.
DO NOT write reserved formal result.
DO NOT call LLM.
```
