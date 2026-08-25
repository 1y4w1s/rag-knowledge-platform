# 01 — Formal entry preflight

Revalidated immediately before Formal T1 measurement execution.

## Required gates (all PASS)

```text
FORMAL_TARGET_SCOPE_V2_IMPLEMENTED = YES
FORMAL_SCOPE_V2_FROZEN              = YES
FORMAL_MEASUREMENT_SCOPE            = T1_ONLY
T1_FORMAL_INPUT_READY               = YES
T1_FORMAL_READY                     = YES
E_B_FORMAL_READY_V2                 = YES
MAY_ENTER_T1_FORMAL_MEASUREMENT     = YES
T2_FORMAL_STATUS                    = NOT_APPLICABLE
T3_FORMAL_STATUS                    = NOT_APPLICABLE

OWNER_AUTHORIZATION_ISSUED          = YES
SOURCE_APPROVED                     = YES
AFTER_SOURCE_APPROVED               = YES
AUTHORIZATION_STILL_VALID           = YES
```

## Provenance

```text
eb43_protocol_commit     = 07a0dcbea9b676c297f45ef0a6edc54831c4ad16
eb41_provenance_commit   = 2951914b3298ef63258d3a1df953bf10a899977b
frozen evaluation base_sha = 3ce0e75f06d35aecaaccd245dd3a234b1c6f79a6
```

`eb43_protocol_commit` ≠ `frozen evaluation base_sha` (by design).

## Historical gates (unchanged)

```text
E-B_FORMAL_READY = NO
FORMAL_TARGET_SCOPE_SEMANTICS (historical) = AMBIGUOUS
```

Any preflight FAIL would set `FORMAL_T1_MEASUREMENT_EXECUTED = NO` and STOP.
