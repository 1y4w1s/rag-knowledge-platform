# 02 — Formal input binding

Formal input sourced exclusively from E-B41 immutable raw companion records.

## Identity binding

```text
measurement_scope_id = w10_showcase_t1_only_v1
source_identity      = suoyin_local_research_product_after_v1
frozen base_sha      = 3ce0e75f06d35aecaaccd245dd3a234b1c6f79a6
runtime_identity     = suoyin_backend_venv_cpython_3.11.9_win10_amd64
capture_mode         = product_stream
suite                = w9_critic_frozen_12
input_run_identity   = w10_showcase_narrow_eb41_t1_20260825T094148Z
input_provenance_commit = 2951914b3298ef63258d3a1df953bf10a899977b
```

## Case scope

| Bucket | Cases |
|---|---|
| Eligible (denominator) | C01–C11 |
| Excluded | C12 `INELIGIBLE_NOT_SCORED` |

## Response mode

All eligible cases: `response_mode = DEGRADED` (allowed for T1; T2/T3 remain N/A per E-B40).

## Integrity checks

- Manifest + per-record `base_sha` / `source_identity` / `runtime_identity` exact match
- `gated_scope_hash` manifest ↔ record consistency
- `same_trajectory_binding = true` for all eligible cases
- `llm_called_observed = false` for all eligible cases
- Raw records not mutated during measurement

## Forbidden input

- `t1-candidate-evaluation.json` aggregate fields (`candidate_compliant_count`, etc.) — **not** used as Formal oracle
