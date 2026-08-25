# 04 — Artifact contract review

> Dimension 4. Verify E-B2 envelope: identity, runner separation, claims, no E-A5 contamination, no Critic oracle leakage.

## 1. Schema identity

| Constant | Frozen value | Verified |
|---|---|---|
| `protocol_version` | `w10_eb2_generation_observation_v1` | Yes（module + docs） |
| `artifact_schema_version` | `w10-eb2-generation-observation-v1` | Yes |
| `observation_point` | `generation_final_content_and_citations` | Yes ≠ E-A5 `plan_construction_citations` |
| `suite_id` | `w9_critic_frozen_12` | Yes（槽位套件 id，≠ 四靶金标已齐） |
| `parent_protocol_id` | `w10_eb1_generation_observation_v1` | Yes |
| `eligibility_protocol_id` | `w10_ea1_scope_eligibility` | Yes |
| Reserved result filename | `w10-eb2-generation-observation-result.json` | **Absent**（正确） |

## 2. Runner separation

| Check | Status |
|---|---|
| `runner_id=w10_eb2_generation_observation_runner` | Frozen |
| `runner_module=tests.w10_eb2_generation_observation_contract` | Frozen |
| Forbidden: E-A4/E-A5 / P2-R1 / P2-R3 runner tokens | Rejected by validator |
| Module imports LLM / `execute_frozen_case` / E-A5 execution | **False**（`contract_module_imports_are_llm_free()`） |
| Analogue of E-A4 `run_formal_window` inside E-B2 module | **Absent** |

**Implication:** 信封身份与 runner **隔离正确**，但 runner 目前只承载 **契约冻结**，不承载正式观测执行。这是 **合同健康**，同时是正式门禁的 **能力缺口**（见 `05` blocker #1）。

对比：E-A4 合同模块内含 `run_formal_window` → E-A5 可诚实落 `FORMAL_RUN_RESULT`。E-B2 **没有**对等函数。

## 3. Claim restrictions

| Allowed | Forbidden（asserted / notes） |
|---|---|
| `generation observation artifact produced` | `generation quality proven` |
| | `grounding proven` |
| | `Critic validated` |

Schema example：`measurement_valid=false`，`artifact_kind=SCHEMA_EXAMPLE_NOT_A_RUN`，`llm_called=false`，`targets_measured=[]`。

`p2_r1_status=BLOCKED` ∧ `does_not_unblock_p2_r1=true` 仍强制。

## 4. No E-A5 artifact contamination

| Rule | Evidence |
|---|---|
| Must not overwrite `w10-ea4-formal-window-result.json` | Untouched this window |
| Reject `artifact_schema_version=w10-ea4-formal-window-v1` | Validator |
| Reject `observation_point=plan_construction_citations` | Validator |
| Reject keys `per_case_result` / `scorer_observation_point` / `scope_compliance_pass` / `adapter_protocol_version` | Validator |
| Live check: feed E-A5 JSON into E-B2 validator | **Rejected**（本窗） |

`parent_l0_artifact` 允许只读文件名引用；**禁止**拷贝 pass 率进 generation 声称。

## 5. No Critic oracle leakage

Forbidden keys（top-level or per-case）：`expected_action`、`oracle_cases` / `oracle_case`、`critic_score`、`critic_capability`、`capability_label`、`w9_critic_oracle`、`critic_actions`。

Schema example 与 contract tests **不含**上述字段。  
`w9-critic-capability-contract.json` 仍仅为 Critic research；**不是** generation gold。

## 6. Pytest freeze health

```powershell
cd D:\MyPrograms\rag-knowledge-platform\backend
$env:JWT_SECRET='<non-default>'
$env:ENVIRONMENT='test'
.\.venv\Scripts\python.exe -m pytest tests/test_w10_eb2_generation_observation_contract.py -q
```

本窗结果：**20 passed**。

## 7. Artifact contract verdict

| Check | Verdict |
|---|---|
| Schema identity frozen | **PASS** |
| Runner identity separated from E-A5 / P2-R* | **PASS** |
| Claim boundary locked | **PASS** |
| E-A5 contamination prevented | **PASS** |
| Critic oracle leakage prevented | **PASS** |
| Formal observation result producible today | **FAIL**（无执行路径；reserved 文件故意不存在） |

契约层 **已就绪作为冻结信封**；**未就绪作为可写正式结果管线**。
