# 05 — Gate matrix

```text
FORMAL_TARGET_SCOPE_V2_IMPLEMENTED     = YES
FORMAL_SCOPE_V2_FROZEN                 = YES
FORMAL_MEASUREMENT_SCOPE               = T1_ONLY
measurement_scope_id                   = w10_showcase_t1_only_v1

T1_FORMAL_INPUT_READY                  = YES
T1_FORMAL_READY                        = YES
T2_FORMAL_STATUS                       = NOT_APPLICABLE
T3_FORMAL_STATUS                       = NOT_APPLICABLE
TARGET_FORMAL_READY(T1)                = YES
TARGET_FORMAL_READY(T2)                = NOT_APPLICABLE
TARGET_FORMAL_READY(T3)                = NOT_APPLICABLE

E_B_FORMAL_READY_V2                    = YES
MAY_ENTER_T1_FORMAL_MEASUREMENT_V2     = YES
MAY_ENTER_T1_FORMAL_MEASUREMENT        = YES

FORMAL_ORACLE_LEAK_RISK                = NO
T2_T3_COMPANION_STATUS                 = NOT_APPLICABLE
AUTHORIZATION_STILL_VALID              = YES

# Historical (unchanged)
FORMAL_TARGET_SCOPE_SEMANTICS          = AMBIGUOUS   (E-B42 preserved)
GLOBAL_E_B_FORMAL_READY_SEMANTICS      = UNDEFINED   (E-B42 preserved)
E-B_FORMAL_READY                       = NO
MAY_ENTER_FORMAL_OBSERVATION_WINDOW    = NO
FORMAL_OBSERVATION                     = NOT_STARTED
FORMAL_T1_RESULT_WRITTEN               = NO

EXACT_BLOCKERS                         = NONE
VERDICT                                = READY_FOR_T1_FORMAL_MEASUREMENT
```

## E_B_FORMAL_READY_V2 definition

```text
E_B_FORMAL_READY_V2 = YES ⇔
    formal_measurement_scope frozen
  ∧ every authorized target READY
  ∧ every N/A target has valid N/A basis
  ∧ no required target unresolved
  ∧ authorization valid
  ∧ formal input immutable
  ∧ writer compatibility ready
  ∧ oracle leak risk = NO
```

Do **not** claim historical `E-B_FORMAL_READY` equals ANY_TARGET or ALL_TARGETS.
