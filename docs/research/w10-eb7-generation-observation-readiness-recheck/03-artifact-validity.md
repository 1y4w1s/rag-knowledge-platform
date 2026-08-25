# 03 — Artifact validity

> Confirm E-B2 envelope compatibility and isolation from E-A5 / P2-R3 / Critic oracle.

## Verdict

| Check | Result |
|---|---|
| E-B2 schema compatibility | **PASS** |
| E-A5 isolation | **PASS** |
| P2-R3 isolation | **PASS** |
| Critic oracle isolation | **PASS** |
| Reserved formal result absent | **PASS**（expected pre-formal） |

---

## 1. E-B2 schema compatibility

E-B6 builds envelopes via constants from `tests.w10_eb2_generation_observation_contract` and calls `validate_reserved_artifact`.

| Field / rule | Smoke artifact behavior |
|---|---|
| `protocol_version` | `w10_eb2_generation_observation_v1` |
| `artifact_schema_version` | `w10-eb2-generation-observation-v1` |
| `observation_point` | `generation_final_content_and_citations` |
| `suite_id` / `case_count` | `w9_critic_frozen_12` / `12` |
| `runner_id` / `runner_module` | E-B2 frozen identity（非 P2-R3 / 非 E-A4） |
| `per_case_observation` | Present（not `per_case_result`） |
| `measurement_claims.asserted` | ⊆ `{generation observation artifact produced}` |
| `p2_r1_status` | `BLOCKED` |
| Validator | `validate_observation_artifact` → `validate_reserved_artifact` |

Tests assert schema acceptance for smoke payload and rejection of foreign shapes.

**Note:** Smoke uses `artifact_kind=FORMAL_OBSERVATION_RESULT` with `measurement_valid=false`。这是信封 kind 兼容，**不是**正式测量通过。

---

## 2. E-A5 isolation

| Rule | Evidence |
|---|---|
| E-A5 file not overwritten | `write_observation_artifact` protects `w10-ea4-formal-window-result.json` |
| E-A5 payload rejected by E-B validator | Test `test_ea5_artifact_cannot_be_accepted` |
| Observation point distinct | E-A5 = `plan_construction_citations`；E-B = `generation_final_content_and_citations` |
| Array key distinct | E-B uses `per_case_observation`；`per_case_result` rejected |
| Parent pointer only | `parent_l0_artifact` names E-A5 file；does not reuse its scores |

一句话：**plan-construction citation scope ≠ generation observation。**

---

## 3. P2-R3 isolation

| Rule | Evidence |
|---|---|
| Forbidden runner ids | E-B2 `FORBIDDEN_RUNNER_IDS` includes P2-R3 formal/batch runners |
| Foreign key `per_case_result` | Rejected by E-B6 `validate_observation_artifact` |
| Protected P2-R3 result filenames | Write guard list includes `w9-critic-p2-r3-full-product-rerun.json` |
| No `execute_frozen_case` | E-B6 suite path uses E-A2 prepare only |

---

## 4. Critic oracle isolation

| Forbidden key / practice | Status |
|---|---|
| `expected_action` / `oracle_cases` / critic score keys | E-B2 + E-B6 reject |
| Using Critic capability contract as generation gold | Still forbidden |
| Claiming「Critic validated」 | In `FORBIDDEN_CLAIMS` |

T2/T3 仍要求 **独立 claim ledger**；Critic oracle **不能**填补 B3。

---

## 5. Reserved result hygiene

| Path | Exists? |
|---|---|
| `backend/tests/fixtures/l4_critic/w10-eb2-generation-observation-result.json` | **No** |
| E-B6 write to reserved path | **Refused** |
| `assert_reserved_result_absent` | Still required by smoke write path |

本复核 **未** 创建 reserved formal result（符合本窗禁令）。
