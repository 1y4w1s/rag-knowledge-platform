# 01 — Frozen Formal Window Contract

> Normative freeze. Not a brainstorm.  
> Protocol version below is **immutable** for this contract revision.

## 0. Identity constants (copy / assert)

| Constant | Frozen value |
|---|---|
| `protocol_version` | `1.0.0` |
| `artifact_schema_version` | `w10-ea4-formal-window-v1` |
| `suite_id` | `w9_critic_frozen_12` |
| `runner_id` | `w10_ea4_formal_window_runner` |
| `runner_module` | `tests.w10_ea4_formal_window_contract` |
| `adapter_protocol_version` | `w10_ea2_scope_eligibility_v1` |
| `eligibility_protocol_id` | `w10_ea1_scope_eligibility` |
| Reserved **result** filename (must not exist until a later formal-run window) | `w10-ea4-formal-window-result.json` |
| Frozen case count | `12` |
| Expected product-path eligible | `11` |
| Expected invalid (C12) | `1` |

### Forbidden runner identities (reject)

Any of the following as `runner_id` / `runner_module` / `executor_path` identity for this window is a **hard schema / identity failure**:

| Forbidden string | Why |
|---|---|
| `execute_frozen_case` | P2-R1 inject harness entry |
| `w9_critic_p2_r1_harness` | P2-R1 harness module |
| `w9_critic_p2_r1_harness.execute_frozen_case` | Fully qualified inject path |
| `w9_critic_p2_r3_formal_runner` | P2-R3 formal product rerun |
| `w9_critic_p2_r3_batch_runner` | P2-R3 batch / dry-run stack |
| `FORMAL_FROZEN_ELIGIBLE_PRODUCT_PATH_RERUN` | P2-R3 measurement mode label |
| `w9_critic_p2_r3_formal_product_rerun_v1` | P2-R3 formal protocol version |

**Binding rule:** future formal-run writers (not this window) must set `runner_id` + `runner_module` to the frozen E-A4 constants above. Tests assert identity on the artifact; substitution of a P2-R1/P2-R3 payload under this schema fails validation.

---

## 1. Reserved suite artifact — top-level schema

Type: JSON object. `additionalProperties` allowed only for explicitly listed optional keys below; unknown *measurement claim* keys are rejected via the claims allowlist.

### Required top-level fields

| Field | Type | Rules |
|---|---|---|
| `protocol_version` | string | **const** `1.0.0` |
| `artifact_schema_version` | string | **const** `w10-ea4-formal-window-v1` |
| `run_id` | string | non-empty; schema examples **must** prefix `SCHEMA_EXAMPLE_` |
| `base_sha` | string | length ≥ 7 (git SHA); examples may use placeholder `0`×40 |
| `suite_id` | string | **const** `w9_critic_frozen_12` |
| `case_count` | integer | **const** `12` |
| `runner_id` | string | **const** `w10_ea4_formal_window_runner` |
| `runner_module` | string | **const** `tests.w10_ea4_formal_window_contract` |
| `adapter_protocol_version` | string | **const** `w10_ea2_scope_eligibility_v1` |
| `eligibility_protocol_id` | string | **const** `w10_ea1_scope_eligibility` |
| `eligibility_summary` | object | see §2 |
| `per_case_result` | array | length **must** equal `case_count` (12); see §3 |
| `measurement_validity` | object | see §4 |
| `measurement_claims` | object | see §5 |
| `p2_r1_status` | string | **const** `BLOCKED` |
| `does_not_unblock_p2_r1` | boolean | **const** `true` |
| `observation_point` | string | **const** `plan_construction_citations` |
| `artifact_kind` | string | enum: `SCHEMA_EXAMPLE_NOT_A_RUN` \| `FORMAL_RUN_RESULT` |

### Optional top-level fields

| Field | Type | Rules |
|---|---|---|
| `timestamp` | string | ISO-8601 if present |
| `notes` | string | free text; must not assert forbidden claims (substring check in tests) |

### Reserved filename discipline

- Schema / contract docs may live under `docs/research/w10-ea4-formal-window-contract/`.
- The reserved **result** path name is `w10-ea4-formal-window-result.json`.
- **E-A4 must not create** that result file.
- Must **not** overwrite: `w9-critic-p2-r1-independent-review.json`, `w9-critic-p2-r3-full-product-rerun.json`, or P3 reserved semantic result names.

---

## 2. `eligibility_summary`

References **E-A1** eligibility protocol + **E-A2** `aggregate_pass_rate` / `enumerate_frozen_eligibility` semantics. Does **not** invent a new eligibility system.

| Field | Type | Rules |
|---|---|---|
| `frozen_cases` | integer | `12` |
| `product_path_eligible` | integer | `11` |
| `invalid_for_product_path` | integer | `1` |
| `c12_in_denominator` | boolean | `false` |
| `invalid_case_ids` | string[] | must include `C12-out-of-scope-provenance` |
| `denominator_case_count` | integer | `11` |
| `classification_vocabulary` | string | **const** `INVALID_FOR_PRODUCT_PATH_EXECUTION` (E-A1/E-A2 string; **not** P2-R3 `DEFENSE_IN_DEPTH_PROBE`) |

---

## 3. `per_case_result[]` (per-case slot)

Each element is a **slot** for an E-A2-shaped case record. E-A4 freezes the *envelope*; it does not require live executor output in this window.

### Required per-case fields

| Field | Type | Rules |
|---|---|---|
| `case_id` | string | non-empty; suite ids from W9 frozen 12 |
| `product_path_eligible` | boolean | C12 must be `false` |
| `classification` | string \| null | C12: `INVALID_FOR_PRODUCT_PATH_EXECUTION`; eligible: `null` |
| `executor_path` | string | allowlist only (below) |
| `in_pass_rate_denominator` | boolean | C12: `false` |
| `scorer_observation_point` | string | **const** `plan_construction_citations` |

### `executor_path` allowlist

| Value | Meaning |
|---|---|
| `agent_tool_scope+prepare_agent_generation` | E-A2 product-path isomorphic executor |
| `refused_ineligible` | E-A2 refusal before plan (C12) |
| `not_executed_schema_example` | E-A4 schema example only |

### Forbidden as `executor_path`

`execute_frozen_case`, any string containing `p2_r1` inject markers, `w9_critic_p2_r3_formal_runner`.

### Optional per-case fields (for future formal run)

`final_citations`, `allowed_scope`, `scorer_result`, `plan_refusal`, `gated_chunk_ids` — shapes must match E-A2 `MeasurementArtifact` when present. Schema examples may omit them.

---

## 4. `measurement_validity`

A file can be **structurally valid** under §1–§3 and still be **measurement-invalid**.

### Required fields

| Field | Type | Rules |
|---|---|---|
| `measurement_valid` | boolean | see consistency rules |
| `invalid_reasons` | string[] | empty iff `measurement_valid=true` |
| `structurally_schema_ok` | boolean | must be `true` for any payload that passed schema validation |
| `runner_identity_ok` | boolean | must be `true` only if runner fields match §0 |
| `eligibility_bound_to_ea1` | boolean | must be `true` |
| `adapter_bound_to_ea2` | boolean | must be `true` |
| `observation_point_honest` | boolean | must be `true` only if observation is plan-construction |
| `p2_r1_remains_blocked` | boolean | **const** `true` |

### Consistency rules (normative)

1. If `artifact_kind == SCHEMA_EXAMPLE_NOT_A_RUN` → `measurement_valid` **must** be `false`, and `invalid_reasons` **must** include `SCHEMA_EXAMPLE_NOT_A_FORMAL_RUN`.
2. If `runner_identity_ok` is `false` → `measurement_valid` **must** be `false`; reasons must include `WRONG_RUNNER_IDENTITY`.
3. If any forbidden claim appears in `measurement_claims.asserted` → schema validation **fails** (not merely measurement-invalid).
4. If `does_not_unblock_p2_r1` is not `true` or `p2_r1_status != BLOCKED` → schema validation **fails**.
5. If `measurement_valid == true`, all of the following must hold: correct runner · EA1/EA2 binds · `artifact_kind == FORMAL_RUN_RESULT` · `case_count==12` · eligibility summary counts · `observation_point_honest` · `p2_r1_remains_blocked` · no forbidden claims · `invalid_reasons == []`.
6. **E-A4 does not authorize** producing `measurement_valid=true` artifacts. That remains for a later formal-run window.

### Invalid reason codes (enum)

`SCHEMA_EXAMPLE_NOT_A_FORMAL_RUN` · `WRONG_RUNNER_IDENTITY` · `RUNNER_SUBSTITUTION_P2_R1` · `RUNNER_SUBSTITUTION_P2_R3` · `ELIGIBILITY_NOT_BOUND_TO_EA1` · `ADAPTER_NOT_BOUND_TO_EA2` · `INELIGIBLE_CASE_IN_DENOMINATOR` · `OBSERVATION_POINT_MISLABEL` · `FORBIDDEN_CLAIM_PRESENT` · `P2_R1_UNBLOCK_ASSERTED` · `INCOMPLETE_SUITE` · `OTHER_PROTOCOL_BREAK`

---

## 5. Measurement claim boundary

### Allowed claim (only)

```text
plan-construction citation scope compliance
```

### Forbidden claims (any appearance fails validation)

```text
generation-final safety
Critic oracle capability
P2-R1 unblocked
```

### `measurement_claims` object

| Field | Type | Rules |
|---|---|---|
| `allowed` | string[] | **const** exactly `["plan-construction citation scope compliance"]` |
| `asserted` | string[] | each item ∈ `allowed`; must not intersect forbidden set |
| `forbidden_rejected` | string[] | **const** the three forbidden strings above (documentation lock) |

---

## 6. What this freeze closes (E-A3 §10 blockers 1, 3–5 partial)

| E-A3 blocker | E-A4 action |
|---|---|
| 1. No reserved suite-level formal artifact schema | **Closed** — schema frozen here + tests module |
| 2. No E-A2 batch/formal runner writing the reserved file | **Still open** — out of E-A4 (no formal execution) |
| 3. Protocol binding vs P2-R1 inject / P2-R3 SSOT | **Closed** — runner identity + forbidden list |
| 4. Honesty: plan citations ≠ generation-final | **Closed** — `observation_point` + claim boundary |
| 5. P2-R1 BLOCKED in envelope | **Closed** — `p2_r1_status` + `does_not_unblock_p2_r1` |

---

## 7. Implementation pointer

Deterministic validators live only in:

- `backend/tests/w10_ea4_formal_window_contract.py`
- `backend/tests/test_w10_ea4_formal_window_contract.py`

No `backend/app` imports of LLM clients. No call to `execute_frozen_case`. No network.
