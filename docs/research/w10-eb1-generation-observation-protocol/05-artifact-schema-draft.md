# 05 — Artifact schema draft（未来观测工件 · 不实施）

> **DRAFT ONLY.** 定义将来正式 observation 结果应有的字段。  
> 本窗 **不** 在 `backend/tests/fixtures` 写结果文件，**不** 实现 pydantic/pytest 模块（留给推荐的 E-B2）。  
> JSON Schema 镜像见 [`reserved-observation-artifact.schema.json`](reserved-observation-artifact.schema.json)（同样非正式结果）。

## 0. 身份常量（草案 · 待 E-B2 冻结）

| Constant | Draft value | 规则 |
|---|---|---|
| `protocol_version` | `w10_eb1_generation_observation_v1` | **不得**等于 E-A4 的 `1.0.0` 而不改 schema 名 |
| `artifact_schema_version` | `w10-eb1-generation-observation-v1` | 新信封 |
| `observation_point` | `generation_final_content_and_citations` | **const**；禁止 `plan_construction_citations` |
| `artifact_kind` | `SCHEMA_EXAMPLE_NOT_A_RUN` \| `FORMAL_OBSERVATION_RESULT` | 本窗不得出现后者实体文件 |
| `p2_r1_status` | `BLOCKED` | const |
| `does_not_unblock_p2_r1` | `true` | const |
| 预留结果文件名 | `w10-eb1-generation-observation-result.json` | **本窗不得创建**；**不得**覆盖 `w10-ea4-formal-window-result.json` |

### 禁止的 runner / 观察点身份

| Forbidden | Why |
|---|---|
| `observation_point=plan_construction_citations` | 那是 E-A5 |
| `execute_frozen_case` / P2-R3 formal runner | 错栈 |
| 把 generation claims 写入 E-A5 `measurement_claims.asserted` | 合并禁止 |

---

## 1. 顶层字段

| Field | Type | When populated | Meaning |
|---|---|---|---|
| `protocol_version` | string | 任何合法信封 | 本观测协议版本 |
| `artifact_schema_version` | string | 同上 | 字段形状版本 |
| `run_id` | string | 正式跑时 | 非空；schema 示例须前缀 `SCHEMA_EXAMPLE_` |
| `base_sha` | string | 正式跑时 | git SHA ≥7 |
| `suite_id` | string | 总是 | 所用套件 id；**不得**默示等于 `w9_critic_frozen_12` 已覆盖四靶金标 |
| `case_count` | integer | 总是 | 本信封条数 |
| `runner_id` | string | 正式跑时 | 未来 E-B2+ 冻结的 generation observation runner；≠ E-A4 runner |
| `observation_point` | string | 总是 | const `generation_final_content_and_citations` |
| `eligibility_protocol_id` | string | 总是 | 仍引用 `w10_ea1_scope_eligibility`（产品路径资格），不另起隔离理论 |
| `parent_l0_artifact` | string \| null | 可选 | 若对照 L0，只读引用 E-A5 文件名；**禁止 copy 其 pass 率当本结果** |
| `eligibility_summary` | object | 总是 | 见 §2 |
| `per_case_observation` | array | 总是 | 长度 = `case_count` |
| `measurement_validity` | object | 正式跑时 | 观察点是否诚实、是否零 LLM 声明等 |
| `measurement_claims` | object | 总是 | §4 |
| `p2_r1_status` | string | 总是 | `BLOCKED` |
| `does_not_unblock_p2_r1` | boolean | 总是 | `true` |
| `artifact_kind` | string | 总是 | 见上枚举 |
| `timestamp` | string | 可选 | ISO-8601 |
| `notes` | string | 可选 | 不得含 forbidden 声称子串 |

---

## 2. `eligibility_summary`

| Field | Type | Meaning |
|---|---|---|
| `frozen_w9_cases_considered` | integer | 通常 12 |
| `product_path_eligible` | integer | L0 资格（E-A5：11） |
| `invalid_for_product_path` | integer | C12 = 1 |
| `empty_retrieval_eligible_count` | integer | **当前研究值 = 0** |
| `refusal_gold_empty_gate_count` | integer | **当前研究值 = 0** |
| `c12_in_denominator` | boolean | `false` |
| `targets_measured` | string[] | 正式跑前列空数组；本窗协议冻结阶段必须 `[]` |

---

## 3. `per_case_observation[]`

每条是 **一次 After 窗快照槽**。未跑生成时只允许 `artifact_kind=SCHEMA_EXAMPLE_NOT_A_RUN` 且下列观测值为 null。

### 3.1 身份与资格

| Field | Type | When | Meaning |
|---|---|---|---|
| `case_id` | string | 总是 | 套件 id |
| `product_path_eligible` | boolean | 总是 | E-A1；C12=false |
| `classification` | string \| null | 总是 | C12：`INVALID_FOR_PRODUCT_PATH_EXECUTION` |
| `in_generation_observation_denominator` | boolean | 总是 | C12=false；空闸案未加入前 C01–C11 对 T4 空闸分母亦为 false |
| `executor_path` | string | 正式跑 | 须含生成相或「假正文→align」同构；禁止仅 `prepare_agent_generation` 就当 After |

### 3.2 Before 快照（对照，非主分母）

| Field | Type | When | Meaning |
|---|---|---|---|
| `gen_plan_refusal` | boolean \| null | 有 plan | `AgentGenerationPlan.refusal` |
| `plan_citation_ids` | string[] \| null | 有 plan | `gen_plan.citations[*].chunk_id` |
| `gated_chunk_ids` | string[] \| null | 有 plan | `gen_plan.gated_chunks` ids |
| `scorer_observation_point_l0` | string \| null | 可选对照 | 若填写，只能是 `plan_construction_citations` 且 **不得**用于本信封四靶 pass |

### 3.3 After 快照（主对象）

| Field | Type | When | Meaning |
|---|---|---|---|
| `content` | string \| null | 生成后 | `state["content"]` 副本 |
| `final_citations` | object[] \| null | 生成后 | `state["citations"]` 副本（对齐后） |
| `final_citation_ids` | string[] \| null | 生成后 | 从 final_citations 抽出 |
| `align_bucket` | string \| null | 生成后 | `shrink` \| `keep_all` \| `refuse_empty` \| `fail_closed_empty` \| `not_aligned` |
| `done_citations_identical` | boolean \| null | 若记录 SSE | `done.citations` 是否与 `state["citations"]` 同一内容 |

### 3.4 四靶观察槽（值可空；协议要求键存在于正式结果）

| Field | Type | Target | When populated | Meaning |
|---|---|---|---|---|
| `t1_final_citation_scope_valid` | boolean \| null | T1 | 有 final_citations + allowed_scope | E-A1 S1–S5 打在 **final** 上 |
| `t1_preservation_recall` | number \| null | T1 | 非空 plan_ids | \|final ∩ plan\| / \|plan\| |
| `t1_keep_all` | boolean \| null | T1 | 已分桶 | 无合法 `[片段N]` 且沿用全表 |
| `t2_unsupported_claim_count` | integer \| null | T2 | **仅当**存在 claim 金标+标注 | 无金标必须保持 null（禁止用 E-A2 缺 chunk_id 冒充） |
| `t2_unsupported_rate` | number \| null | T2 | 同上 | unsupported / asserted |
| `t3_grounded_rate` | number \| null | T3 | 仅当接地规程+金标 | 否则 null |
| `t4_empty_gate_refuse_ok` | boolean \| null | T4 | 仅 empty-gate eligible 案 | 当前套件无案 → 全体 null 或不出分母 |
| `t4_false_refuse` | boolean \| null | T4 | 有 gated 的生成案 | 是否误用 `no_context_reply_for` |
| `t4_refuse_with_citations` | boolean \| null | T4 | 拒答通道 | 无依据却非空 citations |

**本窗所有 t\* 字段在真实世界中均未填充**（无 run）。

---

## 4. `measurement_claims`（信封级）

| Field | Type | Draft |
|---|---|---|
| `allowed` | string[] | 正式跑之前仅允许协议态声称，例如 `generation observation protocol frozen`。**正式观测执行窗**另列 allowed；**不得**加入 `plan-construction citation scope compliance` 当作本信封 asserted（那是 E-A5） |
| `asserted` | string[] | 本窗文档级：`generation observation protocol frozen`。禁止 `generation-final safety PASS`、`Critic oracle capability`、`P2-R1 unblocked` |
| `forbidden_rejected` | string[] | 至少含：`generation quality PASS`、`Critic oracle capability`、`merged with E-A5 plan-construction results`、`P2-R1 unblocked` |

---

## 5. `measurement_validity`（正式跑时）

| Field | Type | Meaning |
|---|---|---|
| `observation_point_honest` | boolean | After 对象确为 `state["content"]`/`citations`，未用 `gen_plan.citations` 冒充 |
| `llm_called` | boolean | 本协议推荐后续契约窗仍可先零 LLM；若 true 必须声明 provider，且 **不得**把结果写进 E-A5 文件 |
| `critic_invoked_for_score` | boolean | 若 true，本信封 **不得**声称 Critic 能力；四靶仍只填 T1–T4 |
| `w9_fixture_answer_used_as_content` | boolean | 若 true → `observation_point_honest` 必须 false 或整信封 INVALID |

---

## 6. 与 E-A4/E-A5 信封隔离

| 规则 | |
|---|---|
| 文件名 | 新 reserved 名；不覆盖 `w10-ea4-formal-window-result.json` |
| `observation_point` | 不同 const |
| 通过率 | 禁止算术合并 11/11 与未来 T1–T4 |
| 本窗 | 只允许 docs 草案；`FORMAL_OBSERVATION_RESULT` 实体 = 未来窗 |
