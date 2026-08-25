# 04 — T1 companion binding

## Policy

```text
T1_SAME_EXECUTION_BINDING_REQUIRED = YES
```

Gated scope and final citations **must** come from the same product execution
trajectory. Cross-run splice (new scope + E-B38 finals) is forbidden.

## Per-record binding fields

| Field | Value |
|---|---|
| `parent_acquisition_run` | `w10_showcase_narrow_eb38_20260825T085526Z` |
| `companion_run` | `w10_showcase_narrow_eb41_t1_20260825T094148Z` |
| `plan_scope_provenance.owner` | `gen_plan.gated_chunks` |
| `inferred_from_final_citations` | `false` |
| `final_citation_source` | E-B41 companion **same-run** product finals |
| `same_trajectory_binding` | `true` |

## Honesty vs E-B38 (not used for binding)

Observed hash match to E-B38 Product After (informational only):

```text
eb38_content_hash_match         = 11/11
eb38_citations_hash_match       = 11/11
eb38_gen_plan_reference_match   = 11/11
```

Even with full match, T1 binding uses **E-B41 same-run** finals + scope —
never splices E-B38 After into a different run's scope.

## Binding validity

```text
T1_INPUT_BINDING_VALID (suite) = YES
C01–C11 same-trajectory        = YES
C12                            = INELIGIBLE_NOT_SCORED
```
