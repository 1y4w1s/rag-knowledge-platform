# 01 — Formal wireup contract & composer

> Tests-only implementation of E-B21 W1 Soft compose. No reserved write.

## 1. Pipeline (unchanged architecture)

```text
Capture (E-B15) → Binding Gate (E-B17) → Scorer (E-B20)
  → Compose:
      A. L-Obs status / After slots (E-B2 v1)
      B. L-Score companion (same run_id / base_sha)
      C. Reserved write ONLY if E-B_FORMAL_READY=YES  ← still locked
```

## 2. L-Obs

| Field | Rule |
|---|---|
| `protocol_version` | `w10_eb2_generation_observation_v1` (**unchanged**) |
| `artifact_kind` | `FORMAL_OBSERVATION_RESULT` |
| Holds | After · status enums · `measurement_validity` |
| Forbidden | `t2` / `t3` / rates / scorer details / E-A5 / Critic keys |

APIs:

- `build_l_obs_skeleton(...)` — shape for contract tests; `measurement_valid=false`
- `compose_l_obs(...)` — formal path; raises `FormalWireupError("FORMAL_GATE_LOCKED")` while gate NO
- `attempt_formal_compose(target="l_obs"|"l_score", ...)` — test helper; gate locked → blocked dict

**Compose ≠ write:** `compose_l_obs` only yields skeleton shape. It does not
complete formal measurement, write the reserved result, or prove product
faithfulness. A future gate unlock still needs a separate write step.

## 3. L-Score companion

| Field | Rule |
|---|---|
| `protocol_version` | `w10_eb22_formal_t2_t3_score_v1` |
| `artifact_kind` | `FORMAL_T2_T3_SCORE_RESULT` |
| `parent_observation_protocol` | `w10_eb2_generation_observation_v1` |
| `parent_run_id` / `parent_base_sha` | **Must equal** L-Obs `run_id` / `base_sha` |
| `formal_measurement` | `true` only under gate YES (rejected while NO) |
| `implementation_only` | `true` on skeleton / contract fixtures |
| Holds | `cases` · `t2` · `t3` · `binding_verdict` · `honesty` |

APIs:

- `build_l_score_companion(...)` — shape builder (`formal_measurement=false`)
- `compose_l_score(...)` — formal path; gate-locked → raises `FORMAL_GATE_LOCKED`
- `attempt_formal_compose(target="l_score", ...)` — blocked dict for tests

**Compose ≠ write:** `compose_l_score` only yields companion artifact shape.
Rates (`unsupported_rate` / `grounded_rate`) stay on the scorer-side / L-Score
companion — never on L-Obs, never as product faithfulness proof. Unlock still
requires an independent reserved-write step.

## 4. Gate enforcement

Any formal compose / write attempt with `E-B_FORMAL_READY != YES`:

- **raise** `FormalWireupError("FORMAL_GATE_LOCKED")` from `compose_l_obs` / `compose_l_score`
- tests may call `attempt_formal_compose(...)` →
  `{status: blocked, invalid_reason: FORMAL_GATE_LOCKED, artifact: None}`

Must **not** produce a writable formal result or create
`w10-eb2-generation-observation-result.json`.

## 5. Invalid-reason allowlist (E-B22)

```text
FORMAL_GATE_LOCKED
BINDING_INCOMPATIBLE
GOLD_AFTER_HASH_MISMATCH
SCORER_COMPANION_MISSING
SCORER_RUN_ID_MISMATCH
SCORER_BASE_SHA_MISMATCH
BP_POLICY_VIOLATION
WIRING_ONLY_POINTER_AS_PRODUCT
COMPAT_PACK_AS_PRODUCT_FAITHFULNESS
LLM_CALLED_FREEZE_VIOLATION
```

- `parent_run_id` mismatch → `SCORER_RUN_ID_MISMATCH`
- `parent_base_sha` mismatch → `SCORER_BASE_SHA_MISMATCH`
- After↔gold content hash disagree → `GOLD_AFTER_HASH_MISMATCH`
  (`validate_gold_after_hash_alignment`)

E-B2 module `INVALID_REASON_CODES` is **not mutated**. L-Obs wireup validator
accepts the union of E-B2 codes ∪ this allowlist.

## 6. BP isolation

| Policy | Rule |
|---|---|
| BP-A | Future product formal **candidate**; compat pack alone ≠ faithfulness |
| BP-B | Protocol / scoring integrity only; `product_faithfulness_proven=true` → reject |
| BP-C | Must not enter T2/T3 as `OBSERVED_SLOT` |

Validators: `validate_l_obs_shape` · `validate_l_score_shape` ·
`validate_compose_pair` · `validate_bp_isolation`.
