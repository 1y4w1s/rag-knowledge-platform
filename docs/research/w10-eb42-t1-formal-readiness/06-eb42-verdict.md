# 06 — E-B42 verdict

## Stamp

```text
eb41_provenance_commit                  = 2951914b3298ef63258d3a1df953bf10a899977b
frozen evaluation base_sha              = 3ce0e75f06d35aecaaccd245dd3a234b1c6f79a6

FORMAL_TARGET_SCOPE_SEMANTICS           = AMBIGUOUS
GLOBAL_E_B_FORMAL_READY_SEMANTICS       = UNDEFINED
L_OBS_T1_ONLY_COMPATIBLE                = YES
T2_T3_NA_COMPANION_ALLOWED              = YES
T1_FORMAL_INPUT_IMMUTABLE               = YES
T1_FORMAL_INPUT_READY                   = YES
T1_FORMAL_READY                         = NO
MAY_ENTER_T1_FORMAL_MEASUREMENT         = NO
T2_FORMAL_STATUS                        = NOT_APPLICABLE
T3_FORMAL_STATUS                        = NOT_APPLICABLE
FORMAL_TARGET_SCOPING_GAP               = YES
FORMAL_ORACLE_LEAK_RISK                 = NO

OWNER_AUTHORIZATION_ISSUED              = YES
SOURCE_APPROVED                         = YES
AFTER_SOURCE_APPROVED                   = YES
AUTHORIZATION_STILL_VALID               = YES

E-B_FORMAL_READY                        = NO
MAY_ENTER_FORMAL_OBSERVATION_WINDOW     = NO
FORMAL_OBSERVATION                      = NOT_STARTED

VERDICT = BLOCKED_PENDING_FORMAL_TARGET_SCOPING_REPAIR
```

## Tests

```text
pytest backend/tests/test_w10_eb42_t1_formal_readiness.py -q
→ 16 passed
```

## Stop

Do **not** run Formal Measurement.  
Do **not** write Formal result.  
Do **not** modify E-B21/E-B22 in this window.  

Next allowed action: **versioned Formal target-scoping repair** (declare whether Showcase T1-only Formal Measurement is a legal scope while T2/T3 remain NOT_APPLICABLE under DEGRADED).
