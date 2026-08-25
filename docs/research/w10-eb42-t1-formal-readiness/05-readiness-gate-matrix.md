# 05 — Readiness gate matrix

## Per-target

```text
T1_FORMAL_INPUT_READY           = YES
T1_FORMAL_READY                 = NO
MAY_ENTER_T1_FORMAL_MEASUREMENT = NO
T2_FORMAL_STATUS                = NOT_APPLICABLE
T3_FORMAL_STATUS                = NOT_APPLICABLE
```

## Semantics stamps

```text
FORMAL_TARGET_SCOPE_SEMANTICS       = AMBIGUOUS
GLOBAL_E_B_FORMAL_READY_SEMANTICS   = UNDEFINED
L_OBS_T1_ONLY_COMPATIBLE            = YES
T2_T3_NA_COMPANION_ALLOWED          = YES
T1_FORMAL_INPUT_IMMUTABLE           = YES
FORMAL_ORACLE_LEAK_RISK             = NO
FORMAL_TARGET_SCOPING_GAP           = YES
```

## Global locks (unchanged)

```text
E-B_FORMAL_READY                    = NO
MAY_ENTER_FORMAL_OBSERVATION_WINDOW = NO
FORMAL_OBSERVATION                  = NOT_STARTED
FORMAL_T1_RESULT_WRITTEN            = NO
```

Do **not** auto-flip global Formal gates from T1 input readiness.

## Exact blockers

```text
1. FORMAL_TARGET_SCOPE_SEMANTICS=AMBIGUOUS
   — E-B21/E-B10 subset language vs E-B24 Narrow {T1,T2,T3} supersession
2. FORMAL_TARGET_SCOPING_GAP=YES
   — no frozen declared scope for "T1 Formal Measurement" with T2/T3=N/A
3. GLOBAL_E_B_FORMAL_READY_SEMANTICS=UNDEFINED
   — Full vs Narrow write-lock meaning not unified
4. DEGRADED keeps T2/T3=NOT_APPLICABLE
   — conflicts with E-B24 declared Narrow targets until scope repair
```

Non-blockers (inputs / auth / wireup shape):

```text
- T1 same-trajectory raw records present & immutable
- Authorization still valid
- L-Obs can express T1-only; companion N/A expressible
- Candidate is not Formal oracle (raw recompute path exists)
```

## Verdict

```text
BLOCKED_PENDING_FORMAL_TARGET_SCOPING_REPAIR
```

Not `READY_FOR_T1_FORMAL_MEASUREMENT`.
