# 01 — E-B39 provenance commit

```text
eb39_provenance_commit = 937e33bddd8278536125a28cbe151886e19959e7
message                = docs(research): record real-After scorer applicability gap
≠ frozen evaluation base_sha 3ce0e75f06d35aecaaccd245dd3a234b1c6f79a6
```

## Preserved E-B39 conclusions (not rewritten for E-B40)

```text
POST_ACQUISITION_RECORD_INTEGRITY           = PASS
REAL_AFTER_BINDING_COMPLETE                 = NO
BP_A_REAL_AFTER_BOUND                       = NO
CLAIM_PRESENCE_UNRESOLVED_BY_FROZEN_PROTOCOL = YES
BP_A_FORMAL_ELIGIBILITY                     = NO
T1_REAL_AFTER_INPUT_READY                   = NO
T2_REAL_AFTER_INPUT_READY                   = NO
T3_REAL_AFTER_INPUT_READY                   = NO
SCORER_APPLICABILITY_GAP                    = YES
BLOCKED_PENDING_PROTOCOL_REPAIR             = YES
E-B_FORMAL_READY                            = NO
```

E-B40 adds a **versioned successor** for future formal input selection.
It does **not** reinterpret E-B39 as model failure, and does **not** flip
historical `SCORER_APPLICABILITY_GAP=YES` inside the E-B39 artifact.
