# 03 — Relation to E-A1 / E-A2 / E-A3

## Chain

```text
W10 Scope Ownership Decision (Direction A)
    → E-A1  eligibility + scoring protocol design
    → E-A2  deterministic adapter + unit tests
    → E-A3  measurement readiness review (CONDITIONAL GO for narrow window)
    → E-A4  formal window CONTRACT freeze (this directory)   ← you are here
    → (later) formal-run window that may write reserved result   ← NOT this window
```

## Binding table

| Layer | Authority | E-A4 rule |
|---|---|---|
| **Eligibility** | E-A1 (`docs/research/w10-ea1-scope-eligibility/`) | `eligibility_protocol_id = w10_ea1_scope_eligibility`; classification string `INVALID_FOR_PRODUCT_PATH_EXECUTION`; C12 out of denom |
| **Adapter / scorer** | E-A2 (`backend/tests/w10_ea2_scope_eligibility.py`) | `adapter_protocol_version = w10_ea2_scope_eligibility_v1`; executor allowlist from E-A2 paths only |
| **Readiness** | E-A3 (`docs/research/w10-ea3-measurement-readiness-review.md`) | Closes narrow-window blockers 1, 3–5 (schema, identity, honesty, P2-R1 BLOCKED flag); leaves blocker 2 (batch writer) open |
| **Formal envelope** | E-A4 (this freeze) | `protocol_version = 1.0.0`; runner ≠ P2-R1/P2-R3; claim boundary |

## What E-A4 is not redefining

- Does **not** invent new eligibility rules (no parallel to P2-R3 `DEFENSE_IN_DEPTH_PROBE` as W10 SSOT).
- Does **not** invent a new adapter (must cite E-A2; future formal run must call E-A2 helpers, not `execute_frozen_case`).
- Does **not** widen observation to generation-final without a new contract revision (`protocol_version` bump).

## Next step (honest)

Next authorized step is **not** “P2-R1 execute / unblock”.

If a later window continues the narrow track, it should:

1. Implement a batch writer that enumerates the frozen 12 via **E-A2** only.
2. Write **one** reserved file named `w10-ea4-formal-window-result.json` with `artifact_kind=FORMAL_RUN_RESULT`.
3. Keep `measurement_claims.asserted` ⊆ allowed claim; keep P2-R1 `BLOCKED`.

Until then, E-A4 schema examples remain the only in-repo payloads, all `measurement_valid=false`.

（2026-08-24 指针）E-A5 已写 reserved FORMAL_RUN_RESULT。A 轨下一研究章程：[`../w10-eb0-generation-boundary/`](../w10-eb0-generation-boundary/)。
