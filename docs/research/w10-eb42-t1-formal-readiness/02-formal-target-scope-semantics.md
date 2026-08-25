# 02 — Formal target-scope semantics

> Evidence from existing contracts only. **Not** reverse-engineered from the desire to open T1-only Formal.

## Question

Is existing Formal readiness / wireup:

| Option | Meaning |
|---|---|
| **A** | Target-specific Formal Measurement allowed (e.g. T1-only; T2/T3 may be N/A) |
| **B** | T1/T2/T3 must jointly satisfy before Formal entry |
| **C** | Semantics unclear |

## Evidence favoring A (target-specific)

| Source | Quote / rule |
|---|---|
| **E-B21** §2.1 | `eligibility_summary.targets_measured` = **Authorized subset** of `{T1,T2,T3}` |
| **E-B10** §2 | Optional Narrow first window: `targets_measured ⊆ {T1}` only; separate `E-B_NARROW_FORMAL_READY` |
| **E-B22** `validate_compose_pair` | L-Score companion required **iff** `T2` or `T3` ∈ `targets_measured` |
| **E-B23** C-G | Gold required for every T2/T3 case **in** `targets_measured` (scope-relative) |
| **E-B19** | `NOT_OBSERVED` when targets exclude T2/T3; `NOT_APPLICABLE` is first-class |

## Evidence favoring B (all targets for declared Narrow)

| Source | Quote / rule |
|---|---|
| **E-B24** §1 | `TARGETS_MEASURED = {T1, T2, T3}` for Narrow Formal |
| **E-B24** §3 | E-B10 “T1-only isomorphic unlock” **superseded** for this first Narrow Formal |
| **E-B24** checklist | `targets_measured = {T1, T2, T3} only` |
| **E-B10** §4 | `E-B_FORMAL_READY=YES` authorizes **Full** formal (§1), not Narrow T1-only |

## Conflict

```text
Wireup / schema layer (E-B10 Narrow option · E-B21 subset · E-B22 companion rule)
  → TARGET_SPECIFIC_ALLOWED

Declared Narrow Formal scope (E-B24)
  → ALL_TARGETS_REQUIRED for that scope ({T1,T2,T3})

No later contract unifies:
  "T1 Formal Measurement"  vs  "Narrow Formal Observation Window"
No gate symbol MAY_ENTER_T1_FORMAL_MEASUREMENT exists in frozen contracts.
```

## Output

```text
FORMAL_TARGET_SCOPE_SEMANTICS = AMBIGUOUS
FORMAL_TARGET_SCOPING_GAP     = YES
```

Per E-B42 §11: when AMBIGUOUS → do **not** set `T1_FORMAL_READY=YES`; next window may do **versioned protocol repair** (not silent E-B21/E-B22 edit in this audit).

## Global gate

```text
GLOBAL_E_B_FORMAL_READY_SEMANTICS = UNDEFINED
```

- E-B10: flip ⇒ Full formal  
- E-B23/E-B22: write-time lock for `FORMAL_OBSERVATION_RESULT`  
- E-B24: same lock used for Narrow `{T1,T2,T3}`  
- Never frozen as clearly `ANY_TARGET` vs `ALL_TARGETS`
