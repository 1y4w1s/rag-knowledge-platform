# 04 — N/A · readiness · writer · oracle

## NOT_APPLICABLE semantics (T2/T3)

```text
in_denominator = false
score          = null
PASS           = false
FAIL           = false
perfect        = false
in_aggregate   = false

NOT_APPLICABLE ≠ PASS
NOT_APPLICABLE ≠ 100%
NOT_APPLICABLE ≠ zero-denominator success
```

E-B40 DEGRADED semantics remain in force.

## TARGET_FORMAL_READY(target)

```text
TARGET_FORMAL_READY(T1) = YES
  ⇔ T1 ∈ authorized_targets
  ∧ T1 input ready (E-B41 raw)
  ∧ binding / authorization / immutability valid
  ∧ no oracle leakage
  ∧ formal writer supports this scope

TARGET_FORMAL_READY(T2) = NOT_APPLICABLE
TARGET_FORMAL_READY(T3) = NOT_APPLICABLE
```

## Writer compatibility

| Check | Result |
|---|---|
| E-B22 L-Obs T1-only skeleton | reuse OK |
| L-Score companion when T2/T3 not measured | not required |
| `T2_T3_COMPANION_STATUS` | `NOT_APPLICABLE` |
| Fabricated `FORMAL_T2_T3_SCORE_RESULT` | **NO** |
| Old `compose_l_obs` unlocked via V2 | **NO** |

Schema extension lives in **tests/eval protocol layer only** (`backend/tests`).

## Formal Result v2 contract (dry-run only)

Required future fields designed; **not** written as reserved Formal result this window:

`schema_version` · `measurement_scope_id` · `measurement_scope=T1_ONLY` ·  
`formal_measurement_id` · identities · `eligible_count=11` · `excluded_count=1` ·  
per-case gated/final hashes · aggregate · `targets{T1=MEASURED,T2/T3=N/A}` ·  
`measurement_valid` (false until real Formal run).

## Oracle isolation

Formal dry-run recomputes `final_citation_ids ⊆ gated_scope_ids` from **E-B41 raw records**.  
Corrupt `t1-candidate-evaluation.json` aggregates → dry-run unchanged.  
Candidate `compliant=11` is **not** a Formal verdict.
