# 07 — E-B40 verdict

## 1. E-B39 provenance commit

```text
937e33bddd8278536125a28cbe151886e19959e7
```

## 2. Response-mode signal source

```text
RESPONSE_MODE_SIGNAL_AVAILABLE = YES
primary = capture_path_submode (E-B15 harness) ∈ {product_stream_degraded, product_stream_refusal}
also    = plan_refusal · llm_called · model_backend_identity
product = stream L1 degraded branch when chat provider keys unavailable
```

## 3. Versioned protocol artifacts

```text
w10_eb40_response_mode_gate_v1
w10_eb40_real_after_binding_v1
SUPERSEDES_FOR_FUTURE_FORMAL_INPUT_SELECTION ≠ rewrites historical result
```

## 4. E-B38 classification

C01–C11 all **DEGRADED** (see `03-eb38-response-mode-classification.md`).

## 5. Degraded BP policy

```text
DEGRADED_BP_POLICY = VERSIONED_BP_D
```

## 6. Real-After binding v2

```text
REAL_AFTER_BINDING_V2_IMPLEMENTED = YES
provenance_bound                  = YES (11/11)
t2_t3_scorer_eligible             = NO  (11/11)
```

## 7–9. Target status

```text
T1 = NO · T1_REQUIRES_COMPANION_REACQUISITION = YES
T2_EB38_APPLICABILITY = NOT_APPLICABLE
T3_EB38_APPLICABILITY = NOT_APPLICABLE
```

## 10. Regression tests

```text
pytest backend/tests/test_w10_eb40_degraded_response_semantics.py -q
→ 14 passed
```

## 11–12. Reacquisition

```text
reacquisition_required_for_T1_scope              = YES
REACQUISITION_WITH_SAME_FROZEN_BASELINE_FEASIBLE = YES
requires_backend_app_change                      = NO
```

## 13. Remaining blockers

1. T1 companion scope fields absent on E-B38 records  
2. No ANSWER-mode Product After under current freeze (`none_no_llm`)  
3. Gold still `synthetic_authored` (speech-act / BP-A rebound not this window)  
4. Formal Observation still not authorized  

## 14. Gate matrix

```text
RESPONSE_MODE_GATE_IMPLEMENTED              = YES
REAL_AFTER_BINDING_V2_IMPLEMENTED           = YES
RESPONSE_MODE_SIGNAL_AVAILABLE              = YES
DEGRADED_BP_POLICY                          = VERSIONED_BP_D
DEGRADED_SCORER_PATH_DEFINED                = YES
EMPTY_OR_DEGRADED_PERFECT_SCORE_PATH        = CLOSED
SCORER_APPLICABILITY_GAP                    = RESOLVED_FOR_RESPONSE_MODE

T1_REAL_AFTER_INPUT_READY                   = NO
T1_REQUIRES_COMPANION_REACQUISITION         = YES
T2_EB38_APPLICABILITY                       = NOT_APPLICABLE
T3_EB38_APPLICABILITY                       = NOT_APPLICABLE

E-B_FORMAL_READY                            = NO
MAY_ENTER_FORMAL_OBSERVATION_WINDOW         = NO
FORMAL_OBSERVATION                          = NOT_STARTED

E-B39 REAL_AFTER_BINDING_COMPLETE           = NO (preserved)
E-B39 SCORER_APPLICABILITY_GAP              = YES (preserved under old protocol)
```

## Close

```text
PROTOCOL_REPAIR_COMPLETE_FOR_DEGRADED_SEMANTICS
WAITING_FOR_T1_COMPANION_REACQUISITION
```

**STOP.** No Formal scorer. No Formal Observation. No LLM.
