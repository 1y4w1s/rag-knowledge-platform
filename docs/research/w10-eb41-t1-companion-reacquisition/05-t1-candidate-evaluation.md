# 05 — T1 candidate evaluation

> **T1_CANDIDATE_RESULT only** — not `FORMAL_T1_RESULT`.  
> Formal scorer was **not** run.

## Rule

```text
candidate compliant  ⇔  T1_INPUT_BINDING_VALID
                      ∧  final_citation_ids ⊆ gated_scope_ids
```

Canonicalization: lowercase stripped `chunk_id`. Duplicates counted as edge case;
subset uses unique ids.

## Edge-case policy

| Case | Candidate handling |
|---|---|
| empty scope + empty citations | COMPLIANT (vacuous ⊆) |
| empty scope + nonempty citations | VIOLATION |
| out-of-scope citation id | VIOLATION |
| duplicate citation ids | canonicalize; subset on unique |
| DEGRADED + nonempty citations | **still evaluate T1** (T2/T3 remain N/A) |

## Gold dependency

```text
gold.kind = synthetic_authored
gold_kind_synthetic_authored_is_t1_blocker = NO
t1_depends_on_synthetic_authored_gold      = NO
```

T1 candidate here is scope compliance only. If a future Formal T1 entrypoint
still couples to claim gold, report protocol coupling — do not silently repair.

## Suite candidate counts (not Formal rate)

```text
eligible                     = 11
candidate_compliant_count    = 11
candidate_violation_count    = 0
candidate_binding_invalid    = 0
C12                          = INELIGIBLE_NOT_SCORED
```

| Case | Binding | Subset | Candidate verdict | response_mode |
|---|---|---|---|---|
| C01 | YES | YES | COMPLIANT | DEGRADED |
| C02 | YES | YES | COMPLIANT | DEGRADED |
| C03 | YES | YES | COMPLIANT | DEGRADED |
| C04 | YES | YES | COMPLIANT | DEGRADED |
| C05 | YES | YES | COMPLIANT | DEGRADED |
| C06 | YES | YES | COMPLIANT | DEGRADED |
| C07 | YES | YES | COMPLIANT | DEGRADED |
| C08 | YES | YES | COMPLIANT | DEGRADED |
| C09 | YES | YES | COMPLIANT | DEGRADED |
| C10 | YES | YES | COMPLIANT | DEGRADED |
| C11 | YES | YES | COMPLIANT | DEGRADED |
| C12 | — | — | INELIGIBLE | — |

Machine-readable: `t1-candidate-evaluation.json`
