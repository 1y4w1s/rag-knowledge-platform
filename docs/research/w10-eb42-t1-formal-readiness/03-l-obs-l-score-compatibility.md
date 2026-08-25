# 03 — L-Obs / L-Score compatibility

## Layer identities (E-B21 / E-B22)

| Layer | Artifact | Holds |
|---|---|---|
| **L-Obs** | `FORMAL_OBSERVATION_RESULT` (E-B2) | After slots · eligibility · status enums · `measurement_validity` · T1 `scope_compliance_result` |
| **L-Score** | `FORMAL_T2_T3_SCORE_RESULT` companion | T2/T3 rates · binding · honesty |

## Q1 — Can L-Obs legally carry T1-only observation?

**YES.**

- E-B21: T1 lives in L-Obs `scope_compliance_result`; `targets_measured` may be an authorized subset including only `T1`.
- When T2/T3 absent from `targets_measured`, grounding stays `NOT_OBSERVED` (not fake PASS).
- E-B22: companion not required if T2/T3 not targeted (`validate_compose_pair`).

```text
L_OBS_T1_ONLY_COMPATIBLE = YES
```

## Q2 — Can T2/T3 companion honestly be NOT_APPLICABLE?

**YES** (expression), with honesty constraints.

- E-B19: `NOT_APPLICABLE` when denom 0 / BP-C; **≠** `0.0` PASS.
- E-B21: maps `NOT_APPLICABLE` → L-Obs `NOT_OBSERVED`.
- E-B22: if T2/T3 not in `targets_measured`, companion may be **absent**.
- E-B40: DEGRADED ⇒ T2/T3 `NOT_APPLICABLE` (≠ PASS ≠ perfect).

```text
T2_T3_NA_COMPANION_ALLOWED = YES
```

**Forbidden:** invent `T2=PASS` / `T3=PASS` or treat 0-denominator as perfect to force Formal entry.

## Q3 — Does this unlock T1 Formal under E-B24 Narrow?

**NO** — L-Obs compatibility ≠ declared Narrow Formal authorization.

E-B24 still freezes Narrow Formal `targets_measured={T1,T2,T3}`. Honest N/A for T2/T3 under DEGRADED conflicts with that declared scope until a **versioned** scope repair defines T1-only Formal Measurement as its own declared scope.
