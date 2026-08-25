# 06 — E-B41 verdict

## Protocol provenance

```text
eb40_protocol_commit   = 8197147801081da262b01edfb7e21729d1630b54
                        ≠ frozen evaluation base_sha
frozen base_sha        = 3ce0e75f06d35aecaaccd245dd3a234b1c6f79a6
companion_run          = w10_showcase_narrow_eb41_t1_20260825T094148Z
parent_acquisition_run = w10_showcase_narrow_eb38_20260825T085526Z
```

## Gate matrix

```text
OWNER_AUTHORIZATION_ISSUED                 = YES
SOURCE_APPROVED                            = YES
AFTER_SOURCE_APPROVED                      = YES
AUTHORIZATION_STILL_VALID                  = YES

FROZEN_WORKTREE_PREFLIGHT                  = PASS
T1_GATED_SCOPE_SIGNAL_AVAILABLE            = YES

T1_COMPANION_REACQUISITION_EXECUTED        = YES
T1_COMPANION_CAPTURE_VALID                 = YES
T1_INPUT_BINDING_VALID                     = YES
T1_REAL_AFTER_INPUT_READY                  = YES

candidate_compliant_count                  = 11
candidate_violation_count                  = 0
(is Formal T1 rate?                        = NO)

T2_REAL_AFTER_INPUT_READY                  = NOT_APPLICABLE
T3_REAL_AFTER_INPUT_READY                  = NOT_APPLICABLE
T2_EB38_APPLICABILITY                      = NOT_APPLICABLE
T3_EB38_APPLICABILITY                      = NOT_APPLICABLE

E-B_FORMAL_READY                           = NO
MAY_ENTER_FORMAL_OBSERVATION_WINDOW        = NO
FORMAL_OBSERVATION                         = NOT_STARTED
FORMAL_T1_RESULT_WRITTEN                   = NO
```

## Exact blockers (remaining)

```text
1. Formal T1 readiness review not yet opened
2. T2/T3 remain NOT_APPLICABLE under DEGRADED Response Mode Gate (E-B40)
3. E-B_FORMAL_READY remains NO — no Formal Observation
```

No acquisition/capture blockers for T1 companion scope.

## Tests

```text
pytest backend/tests/test_w10_eb41_t1_companion_reacquisition.py -q
→ 14 passed
```

## Stop condition

```text
WAITING_FOR_T1_FORMAL_READINESS_REVIEW
```

Do **not** run Formal T1 scorer.  
Do **not** open Formal Observation.  
Do **not** reacquire for T2/T3 answer quality in this window.
