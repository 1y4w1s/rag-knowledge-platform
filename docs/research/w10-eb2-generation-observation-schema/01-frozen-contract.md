# 01 — Frozen Generation Observation Artifact Contract

> Normative freeze. Not a brainstorm.  
> Protocol version below is **immutable** for this contract revision.  
> Upstream observation semantics: E-B1. This window freezes the **envelope** only.

## 0. Identity constants (copy / assert)

| Constant | Frozen value |
|---|---|
| `protocol_version` | `w10_eb2_generation_observation_v1` |
| `artifact_schema_version` | `w10-eb2-generation-observation-v1` |
| `suite_id` | `w9_critic_frozen_12`（槽位套件 id；**不**等于四靶金标已齐） |
| `runner_id` | `w10_eb2_generation_observation_runner` |
| `runner_module` | `tests.w10_eb2_generation_observation_contract` |
| `observation_point` | `generation_final_content_and_citations` |
| `eligibility_protocol_id` | `w10_ea1_scope_eligibility` |
| `parent_protocol_id` | `w10_eb1_generation_observation_v1` |
| Reserved **result** filename（本窗不得创建） | `w10-eb2-generation-observation-result.json` |
| Frozen case count（schema example 槽） | `12` |
| Expected product-path eligible (L0) | `11` |
| Expected invalid (C12) | `1` |

### Forbidden observation / runner identities (reject)

| Forbidden string / shape | Why |
|---|---|
| `observation_point=plan_construction_citations` | E-A5 / L0 identity |
| `artifact_schema_version=w10-ea4-formal-window-v1` | E-A5 envelope reuse |
| `protocol_version=1.0.0` under this validator as EA4 alias | E-A4/E-A5 protocol |
| `execute_frozen_case` / `w9_critic_p2_r1_harness*` | P2-R1 inject harness |
| `w9_critic_p2_r3_*` / `FORMAL_FROZEN_ELIGIBLE_PRODUCT_PATH_RERUN` | P2-R3 formal stack |
| Critic oracle keys（见 §6） | oracle ≠ generation observation |

**Binding rule:** future formal-observation writers must use the frozen E-B2 constants. Passing an E-A5 or P2-R3 payload through this validator is a **hard failure**.

---

## 1. Reserved suite artifact — top-level schema

### Required top-level fields

| Field | Type | Rules |
|---|---|---|
| `protocol_version` | string | **const** `w10_eb2_generation_observation_v1` |
| `artifact_schema_version` | string | **const** `w10-eb2-generation-observation-v1` |
| `run_id` | string | non-empty; schema examples **must** prefix `SCHEMA_EXAMPLE_` |
| `base_sha` | string | length ≥ 7 (git SHA); examples may use placeholder `0`×40 |
| `suite_id` | string | **const** `w9_critic_frozen_12` |
| `observation_point` | string | **const** `generation_final_content_and_citations` |
| `case_count` | integer | **const** `12` |
| `runner_id` | string | **const** `w10_eb2_generation_observation_runner` |
| `runner_module` | string | **const** `tests.w10_eb2_generation_observation_contract` |
| `eligibility_protocol_id` | string | **const** `w10_ea1_scope_eligibility` |
| `parent_protocol_id` | string | **const** `w10_eb1_generation_observation_v1` |
| `eligibility_summary` | object | see §2 |
| `per_case_observation` | array | length **must** equal `case_count`；见 §3 |
| `measurement_validity` | object | see §4 |
| `measurement_claims` | object | see §5 |
| `p2_r1_status` | string | **const** `BLOCKED` |
| `does_not_unblock_p2_r1` | boolean | **const** `true` |
| `artifact_kind` | string | enum: `SCHEMA_EXAMPLE_NOT_A_RUN` \| `FORMAL_OBSERVATION_RESULT` |

### Optional top-level fields

| Field | Type | Rules |
|---|---|---|
| `parent_l0_artifact` | string \| null | 只读引用 E-A5 文件名；**禁止** copy 其 pass 率 |
| `timestamp` | string | ISO-8601 if present |
| `notes` | string | must not assert forbidden claims (substring check) |

### Reserved filename discipline

- Docs live under `docs/research/w10-eb2-generation-observation-schema/`.
- Reserved result name: `w10-eb2-generation-observation-result.json`.
- **E-B2 must not create** that result file.
- Must **not** overwrite: `w10-ea4-formal-window-result.json`, `w9-critic-p2-r1-independent-review.json`, `w9-critic-p2-r3-full-product-rerun.json`, or Critic oracle fixtures.

---

## 2. `eligibility_summary`

| Field | Type | Rules |
|---|---|---|
| `frozen_cases` | integer | `12` |
| `product_path_eligible` | integer | `11` |
| `invalid_for_product_path` | integer | `1` |
| `c12_in_denominator` | boolean | `false` |
| `invalid_case_ids` | string[] | must include `C12-out-of-scope-provenance` |
| `targets_measured` | string[] | schema example / freeze stage must be `[]` |

---

## 3. `per_case_observation[]` (required per-case fields)

Each element is an **After-window observation slot**. Schema examples leave observation values null / unpopulated status.

| Field | Type | Rules |
|---|---|---|
| `case_id` | string | non-empty; W9 frozen 12 ids |
| `eligibility` | boolean | C12 must be `false`（产品路径资格；对齐 E-A1） |
| `classification` | string \| null | C12: `INVALID_FOR_PRODUCT_PATH_EXECUTION`；eligible: `null` |
| `input_hash` | string | non-empty；schema example 可用固定占位 hash |
| `gen_plan_reference` | string \| null | 对照引用（plan id / hash）；**不是** After 主体 |
| `final_content_observation` | string \| null | 正式跑时 = `state["content"]` 副本；schema example = `null` |
| `final_citations` | array \| null | 正式跑时 = 对齐后 `state["citations"]`；schema example = `null` |
| `scope_compliance_result` | object \| null | 终态 scope 观察槽；schema example = `null`（**禁止**填 E-A5 `scope_compliance_pass` 冒充） |
| `grounding_observation_status` | string | enum 见下；freeze/schema example = `NOT_OBSERVED` |
| `refusal_observation_status` | string | enum 见下；freeze/schema example = `NOT_OBSERVED` |

### Status enums

`grounding_observation_status` / `refusal_observation_status`:

| Value | Meaning |
|---|---|
| `NOT_OBSERVED` | 槽位存在，未执行观测（本窗全部如此） |
| `OBSERVED_SLOT` | 未来正式窗已写入观测（仍**不**等于 proven） |
| `INELIGIBLE` | 案不进该靶分母（如 C12） |

C12：`grounding_observation_status` 与 `refusal_observation_status` 必须为 `INELIGIBLE`。

---

## 4. `measurement_validity`

| Field | Type | Rules |
|---|---|---|
| `measurement_valid` | boolean | schema example **must** be `false` |
| `invalid_reasons` | string[] | schema example must include `SCHEMA_EXAMPLE_NOT_A_FORMAL_RUN` |
| `structurally_schema_ok` | boolean | `true` when envelope validates |
| `observation_point_honest` | boolean | `true`（身份为 generation-final，非 plan-construction） |
| `ea5_artifact_not_reused` | boolean | `true` |
| `p2_r3_artifact_not_reused` | boolean | `true` |
| `critic_oracle_fields_absent` | boolean | `true` |
| `p2_r1_remains_blocked` | boolean | `true` |
| `llm_called` | boolean | schema freeze / example **must** be `false` |

`FORMAL_OBSERVATION_RESULT` + `measurement_valid=true` 留给未来执行窗；**本窗不得**写出该实体文件。

---

## 5. `measurement_claims`

| Field | Type | Frozen |
|---|---|---|
| `allowed` | string[] | 恰好 `["generation observation artifact produced"]` |
| `asserted` | string[] | 子集 of `allowed`；schema example 断言 allowed claim |
| `forbidden_rejected` | string[] | 恰好锁定三条 forbidden（§5.1） |

### 5.1 Allowed / forbidden claim strings

**Allowed（唯一）：**

```text
generation observation artifact produced
```

**Forbidden（必须拒绝出现在 `asserted` / `notes`）：**

```text
generation quality proven
grounding proven
Critic validated
```

说明：本窗「artifact produced」指 **schema example / 契约冻结**语义下的声称槽；**不**表示正式观测结果文件已落盘。正式执行窗若断言同一 allowed 字符串，仍不得外推三条 forbidden。

---

## 6. Critic oracle fields（hard reject if present）

Any of the following keys at **top-level** or inside any `per_case_observation[]` element fails validation:

| Forbidden key |
|---|
| `expected_action` |
| `oracle_cases` |
| `oracle_case` |
| `critic_score` |
| `critic_capability` |
| `capability_label` |
| `w9_critic_oracle` |
| `critic_actions` |

Also reject foreign envelope keys that mark E-A5 / P2-R3 reuse:

| Forbidden key | Why |
|---|---|
| `per_case_result` | E-A4/E-A5 envelope array name |
| `scorer_observation_point` | E-A5 per-case identity |
| `scope_compliance_pass` | E-A5 boolean claim field（≠ `scope_compliance_result` 槽） |
| `adapter_protocol_version` | E-A4/E-A5 adapter bind（本信封不使用） |

---

## 7. Authority pointers

| Role | Path / symbol |
|---|---|
| Contract module | `backend/tests/w10_eb2_generation_observation_contract.py` |
| Schema tests | `backend/tests/test_w10_eb2_generation_observation_contract.py` |
| E-B1 protocol | `docs/research/w10-eb1-generation-observation-protocol/` |
| E-A5 result（只读对照，禁止 reuse） | `backend/tests/fixtures/l4_critic/w10-ea4-formal-window-result.json` |
