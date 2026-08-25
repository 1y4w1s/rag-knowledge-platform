# W10 E-B40 — Degraded Response Semantics & Real-After Binding Repair

> **Does:** Persist E-B39 · versioned response-mode gate · versioned real-After binding v2 · classify E-B38 C01–C11 from control-plane signals · close empty/degraded→perfect-score path · separate availability metrics.  
> **Does not:** Formal scorer · Formal Observation · LLM/NLI/embeddings · rewrite E-B16/17/19/20/21/22 · modify gold or E-B38 After · reinterpret E-B39 as model failure · execute new acquisition.

## Inherited

```text
E-B39 provenance commit              = 937e33bddd8278536125a28cbe151886e19959e7
E-B39 REAL_AFTER_BINDING_COMPLETE    = NO   (preserved · not rewritten)
E-B39 SCORER_APPLICABILITY_GAP       = YES  (preserved under old protocol)
E-B38 ACQUISITION_VALID              = YES
capture_submode                      = product_stream_degraded (C01–C11)
llm_called_observed                  = false
frozen evaluation base_sha           = 3ce0e75f06d35aecaaccd245dd3a234b1c6f79a6
```

## Verdict (this window)

```text
RESPONSE_MODE_GATE_IMPLEMENTED              = YES
REAL_AFTER_BINDING_V2_IMPLEMENTED           = YES
RESPONSE_MODE_SIGNAL_AVAILABLE              = YES
DEGRADED_BP_POLICY                          = VERSIONED_BP_D
DEGRADED_SCORER_PATH_DEFINED                = YES
EMPTY_OR_DEGRADED_PERFECT_SCORE_PATH        = CLOSED
SCORER_APPLICABILITY_GAP                    = RESOLVED_FOR_RESPONSE_MODE

T1_EB38_APPLICABILITY / READY               = NO (companion reacquisition)
T2_EB38_APPLICABILITY                       = NOT_APPLICABLE
T3_EB38_APPLICABILITY                       = NOT_APPLICABLE

E-B_FORMAL_READY                            = NO
MAY_ENTER_FORMAL_OBSERVATION_WINDOW         = NO
FORMAL_OBSERVATION                          = NOT_STARTED

PROTOCOL_REPAIR_COMPLETE_FOR_DEGRADED_SEMANTICS
WAITING_FOR_T1_COMPANION_REACQUISITION
```

## Package

| File | Role |
|---|---|
| `01-eb39-provenance-commit.md` | E-B39 commit identity |
| `02-response-mode-gate.md` | `w10_eb40_response_mode_gate_v1` |
| `03-eb38-response-mode-classification.md` | C01–C11 table |
| `04-real-after-binding-v2.md` | `w10_eb40_real_after_binding_v1` |
| `05-t1-t2-t3-status.md` | Per-target status |
| `06-reacquisition-feasibility.md` | Same-baseline companion capture |
| `07-eb40-verdict.md` | Gate matrix + stop |

## Code

- `backend/tests/w10_eb40_response_mode_gate.py`
- `backend/tests/w10_eb40_real_after_binding.py`
- `backend/tests/test_w10_eb40_degraded_response_semantics.py`

## Stop

Do **not** run Formal T1/T2/T3. Do **not** write Formal results. Next = T1 companion reacquisition (orchestration only) or Formal readiness review after T1 inputs exist.
