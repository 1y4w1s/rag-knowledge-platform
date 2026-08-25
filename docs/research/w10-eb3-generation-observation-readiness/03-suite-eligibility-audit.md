# 03 — Suite eligibility audit

> Dimension 3. Review W9 frozen cases only. **Do not create new cases**（本窗遵守）。

## 1. Materials（read-only）

| Material | Path |
|---|---|
| Frozen 12 | `backend/tests/fixtures/l4_critic/w9-critic-cases.json`（`protocol=w9_critic_model_inputs_v1`） |
| Critic oracle（非本协议金标） | `backend/tests/fixtures/l4_critic/w9-critic-capability-contract.json` |
| L0 formal eligibility / refusal | `backend/tests/fixtures/l4_critic/w10-ea4-formal-window-result.json` |
| E-B1 eligibility research | `docs/research/w10-eb1-generation-observation-protocol/04-case-eligibility.md` |

## 2. Deterministic suite facts（本窗复算）

| Fact | Value |
|---|---|
| Case count | **12** |
| Empty `evidence` cases | **0**（`empty_evidence=[]`） |
| C01–C11 evidence provenance | `current_run_retrieval`（in-scope） |
| C12 evidence provenance | `foreign_workspace_fixture` |
| E-A5 `product_path_eligible` | C01–C11 **true**；C12 **false** |
| E-A5 `plan_refusal` | C01–C11 全部 **false**；C12 **null** |
| E-A5 observation point | `plan_construction_citations`（≠ After） |

Fixture `answer` / `citations` = **Critic model-facing inputs**，不是 `_stream_generation_phase` 写入的 `state["content"]` / `state["citations"]`。

## 3. Who can enter generation observation?

分层（继承 E-B1，禁止一张表混打分）：

| Layer | Question | Answer today |
|---|---|---|
| L0 product-path | 能否得到合法 `gen_plan` | C01–C11 yes；C12 no（E-A5） |
| L1 observation-run | 未来若跑生成/同构 After，能否进分母 | C01–C11 **条件候选**；C12 **不得** |
| Target-gold | 能否当 T1–T4 金标 | 几乎全部 **否**（见下） |

### Per-case audit

| case_id | L0 path | Enter After observation run? | Required properties missing for gold |
|---|---|---|---|
| C01 | eligible | **Conditional candidate**（需真实 After，禁止回填 fixture answer） | After `content`/`citations`；T2/T3 claim gold |
| C02 | eligible | Conditional candidate | 同上 |
| C03 | eligible | Conditional candidate | 同上；案名含 unsupported ≠ 正文无依据已测 |
| C04 | eligible | Conditional candidate | Critic `REFUSE` ≠ empty-gate T4 |
| C05 | eligible | Conditional candidate | 同上 |
| C06 | eligible | Conditional candidate | Critic RETRIEVE ≠ 空检索拒答 |
| C07 | eligible | Conditional candidate | **非**空闸拒答金标（有 1 条 evidence；E-A5 `plan_refusal=false`） |
| C08 | eligible | Conditional candidate | 同上 |
| C09 | eligible | Conditional candidate | 同上 |
| C10 | eligible | Conditional candidate | 同上 |
| C11 | eligible | Conditional candidate | fixture `[1]` 非法标记若误当产品正文 → keep-all 假象 |
| C12 | **invalid** | **No** — `INVALID_FOR_PRODUCT_PATH_EXECUTION` | — |

**Conditional candidate** = 未来 L1 执行窗 *可以* 对 C01–C11 跑产品路径并观察 After；**当前**无一案具备 After 工件，故 **零案可计入已观察分母**。

## 4. Are empty retrieval / refusal cases required?

| Need | Required for | Present in frozen 12? |
|---|---|---|
| Eligible ∧ empty gated / empty retrieval | T4 `empty_gate_refuse_ok` | **No** |
| Critic-style insufficiency (C07) | Critic capability（**out of E-B denom**） | Yes，但 **不得**顶空闸 |
| Critic `REFUSE` (C04) | Critic action oracle | Yes，但 **不得**顶空闸 |

**结论：**  
- 若正式窗声称完整 T4（含空闸）：**需要**新 research fixture（E-B1 已建议前缀；**本窗不创建**）。  
- 若正式窗仅声称 T1（有 gated 保全）且诚实写 `targets_measured`：空检索案 **不阻塞 T1 本身**，但仍被 **executor / After 快照** 阻塞（维度 5）。  
- 本审查按 E-B1 四靶全集评估正式 readiness → 空检索缺口计为 **blocker #4**。

## 5. Explicitly out of generation observation denominator

| Set | Reason |
|---|---|
| C12 | INVALID_FOR_PRODUCT_PATH_EXECUTION |
| Hit@3 golden 11 | 检索门禁，非 After |
| P2-R1 inject 产出 | harness-only |
| W9 fixture `answer` as After gold | 观察点撒谎 |
| Critic `expected_action` | 控制面 ≠ T2/T3/T4 |

## 6. Suite audit verdict

| Question | Answer |
|---|---|
| Which cases can enter (future) observation run? | **C01–C11** as conditional candidates |
| Which lack required After properties today? | **All 12**（C12 另因 L0 invalid） |
| Empty retrieval / empty-gate required? | **Yes** for full T4；**absent** today |
| Create new cases in this window? | **No**（禁止） |
