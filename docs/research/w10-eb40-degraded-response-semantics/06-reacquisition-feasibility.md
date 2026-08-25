# 06 — Reacquisition feasibility

```text
REACQUISITION_WITH_SAME_FROZEN_BASELINE_FEASIBLE = YES
REACQUISITION_WITH_SAME_BASELINE_VALID           = YES
requires_backend_app_change                      = NO
frozen_base_sha                                  = 3ce0e75f06d35aecaaccd245dd3a234b1c6f79a6
```

## What is already available (no reacquisition)

- `response_mode` control-plane signals (`capture_path_submode`, `plan_refusal`, `llm_called`)
- Real After content + citations + dual hashes

```text
response_mode_signal_reacquisition_needed = NO
```

## What still needs companion capture

Persist during E-B15 product path (already in memory on `gen_plan`):

- `gated_chunks` / `gated_chunks_ordered`
- authorized citation scope / plan citations
- `align_bucket` if present

Via **external orchestration** on the same frozen worktree — not by mutating
`backend/app` under the old stamp.

```text
t1_scope_companion_reacquisition_needed = YES
```

If `backend/app` must change → new baseline → re-freeze → re-authorization.
This window does **not** execute reacquisition.
