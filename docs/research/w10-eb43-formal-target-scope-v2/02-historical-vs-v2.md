# 02 — Historical vs v2 semantic separation

> Successor protocol. **Not** a retroactive reinterpretation.

## Preserved historical facts

| Window | Preserved statement |
|---|---|
| **E-B21** | `targets_measured` may be an **authorized subset** of `{T1,T2,T3}` |
| **E-B24** | Historical Narrow Formal froze `TARGETS_MEASURED={T1,T2,T3}` |
| **E-B42** | `FORMAL_TARGET_SCOPE_SEMANTICS=AMBIGUOUS` |
| **E-B42** | `GLOBAL_E_B_FORMAL_READY_SEMANTICS=UNDEFINED` |
| **E-B10/22/23** | Historical `E-B_FORMAL_READY` remains **NO** (not remapped) |

**Forbidden:** rewrite E-B42 to `TARGET_SPECIFIC_ALLOWED`.

## Versioned successor (E-B43)

```text
scope_version              = w10_eb43_formal_target_scope_v2
FORMAL_MEASUREMENT_SCOPE   = T1_ONLY   (via frozen formal_measurement_scope)
E_B_FORMAL_READY_V2        = YES  ⇔ authorized targets ready ∧ N/A valid ∧ scope frozen ∧ …
historical E-B_FORMAL_READY = NO  (unchanged)
```

## Compatibility decision (explicit)

```text
EXPLICIT_V2_WRITER_NOT_OLD_COMPOSE_UNLOCK
```

`E_B_FORMAL_READY_V2=YES` does **not** unlock E-B22 `compose_l_obs` / `compose_l_score`  
(those still require historical `E-B_FORMAL_READY=YES`).  

Formal T1 Measurement v2 uses the **writer_v2** contract:

- L-Obs T1-only skeleton (`build_l_obs_skeleton(targets_measured=("T1",))`)
- `T2_T3_COMPANION_STATUS=NOT_APPLICABLE` (no fabricated `FORMAL_T2_T3_SCORE_RESULT`)
