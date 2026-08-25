# 03 — Frozen formal_measurement_scope

## Active scope (exactly one)

```text
measurement_scope_id       = w10_showcase_t1_only_v1
scope_version              = w10_eb43_formal_target_scope_v2
authorized_targets         = {T1}
not_applicable_targets     = {T2, T3}
excluded_targets           = {}
suite_id                   = w9_critic_frozen_12
case_scope                 = C01–C11
C12                        = INELIGIBLE_NOT_SCORED
measurement_scope label    = T1_ONLY

source_identity            = suoyin_local_research_product_after_v1
base_sha                   = 3ce0e75f06d35aecaaccd245dd3a234b1c6f79a6
runtime_identity           = suoyin_backend_venv_cpython_3.11.9_win10_amd64
response_mode_policy_ref   = w10_eb40_response_mode_gate_v1
authorization_ref          = docs/research/w10-eb36-human-owner-stamp-issuance/01-approved-owner-stamp.md
binding_ref                = w10_eb41_t1_companion_v1
frozen_by                  = suoyin_project_owner
frozen_at                  = 2026-08-25T10:00:00Z
```

## Basis

| Target | Basis |
|---|---|
| T1 authorized | E-B41 same-trajectory real Product After + gated scope |
| T2/T3 N/A | E-B40 DEGRADED response semantics |

## Closed expansions

```text
A4 · S2_denominator · Local_Model_capability · Research_Benchmark_Track
```

Human authority inherits `suoyin_project_owner` only; no second concurrent active scope.
