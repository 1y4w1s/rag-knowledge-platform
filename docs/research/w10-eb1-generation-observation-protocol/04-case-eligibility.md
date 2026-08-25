# 04 — Case eligibility（W9 冻结案 vs 生成后观察）

> 只做资格分析与**研究建议**。不发明新产品 case 实施，不改冻结 oracle，不执行生成。

## 1. 材料（只读）

| 材料 | 路径 |
|---|---|
| W9 frozen 12 | `backend/tests/fixtures/l4_critic/w9-critic-cases.json`（`protocol=w9_critic_model_inputs_v1`） |
| Critic oracle | `backend/tests/fixtures/l4_critic/w9-critic-capability-contract.json` · `oracle_cases` |
| L0 正式资格/拒答闸记录 | `backend/tests/fixtures/l4_critic/w10-ea4-formal-window-result.json` |
| 资格规则 | [`../w10-ea1-scope-eligibility/02-eligibility-rules.md`](../w10-ea1-scope-eligibility/02-eligibility-rules.md) |
| 检索 Golden | `backend/tests/test_retrieval_golden.py`（**不是** W9 冻结 12） |

`w9-critic-cases.json` 的 `answer` / `citations` 是 **Critic 模型输入**，**不是** `_stream_generation_phase` 写入的 `state["content"]` / `state["citations"]`。

---

## 2. 资格分层（本协议）

对「post-generation observation」必须拆开三层，禁止一张表混打分：

| 层 | 问题 | 谁回答 |
|---|---|---|
| **L0 product-path** | 能否经 `AgentToolScope` + `prepare_agent_generation` 得到合法 `gen_plan` | E-A1/E-A5 已答：C01–C11 yes，C12 no |
| **L1 observation-run** | 未来执行器若跑生成/同构对齐，该案能否进入 **generation observation 分母** | 本文件：仅 L0 eligible **且** 观察点是 After 窗 |
| **Target-gold** | 该案能否当 T1/T2/T3/T4 的 **金标** | 几乎全部 **否**（见下）；冻结 12 是 Critic/claim-status 套件 |

---

## 3. 冻结 12 案逐条

静态：C01–C11 evidence 均为 in-scope `current_run_retrieval`；E-A5：`product_path_eligible=true`，`plan_refusal=false`。C12：`INVALID_FOR_PRODUCT_PATH_EXECUTION`。

| case_id | L0 产品路径 | 作为 **After 窗**观察候选 | T1 金标 | T2/T3 金标 | T4 空检索/空闸拒答金标 |
|---|---|---|---|---|---|
| C01-fully-supported-exact | eligible | **条件候选**：仅当未来产出真实 `state[content/citations]`，不得把 fixture `answer` 当 After | 否（无生成终态） | 否（Critic 输入 ≠ 生成金标） | **否**（有 evidence；非空闸） |
| C02-supported-paraphrase-low-lexical | eligible | 同上 | 否 | 否 | 否 |
| C03-one-unsupported-among-supported | eligible | 同上 | 否 | **否**（名称含 unsupported ≠ 已测正文无依据） | 否 |
| C04-valid-citation-wrong-evidence | eligible | 同上 | 否 | 否 | **否**（oracle `REFUSE` 是 **Critic action**，不是 `gate_agent_chunks` 空闸） |
| C05-known-conflict-overcertain | eligible | 同上 | 否 | 否 | 否 |
| C06-required-fact-missing | eligible | 同上 | 否 | 否 | 否（oracle 是 RETRIEVE，不是空检索拒答） |
| C07-correct-insufficiency-refusal | eligible | 同上 | 否 | 否 | **否**（见 §5） |
| C08-nonassertive-preface-supported-fact | eligible | 同上 | 否 | 否 | 否 |
| C09-supported-plus-unverifiable | eligible | 同上 | 否 | 否 | 否 |
| C10-supported-multiclaim-multicitation | eligible | 同上 | 否 | 否 | 否 |
| C11-citation-format-only-defect | eligible | 同上；fixture 用 `[1]` 非法标记，**若误用 fixture 正文做对齐**会落入 keep-all——那是 Critic 语法案，不是产品生成观察 | 否 | 否 | 否 |
| C12-out-of-scope-provenance | **invalid** | **不得**进入 generation observation **产品**分母 | — | — | — |

**条件候选**含义：未来 L1 执行窗可以 *跑* C01–C11 的产品路径生成，并观察 After 窗；**当前**没有任何 After 工件，故四靶均为 `defined_not_measured`。禁止把 W9 fixture 正文回填成 `state["content"]` 却声称「已观察生成」。

---

## 4. 缺口 A — Missing empty retrieval cases

E-A1 `02` 静态算法的 `both empty` 分支：**协议允许**「无证据拒答类」单独对照；**今天的冻结 12 不存在** `scoped empty ∧ foreign empty`。

| 事实 | Evidence |
|---|---|
| 冻结 12 每案 `evidence` 至少 1 条 | `w9-critic-cases.json` |
| E-A5 C01–C11 全部 `plan_refusal=false` | `w10-ea4-formal-window-result.json` |
| 空 gated 闸在代码中存在 | `gate_agent_chunks`：`refusal=not gated`；`_stream_generation_phase` refusal → `stream_no_context_reply` |

**结论：** 没有 W9 frozen case 合格作为 **eligible ∧ 空检索/空 gated** 的 T4 分母成员。

**研究建议（非实施）：** 另开契约窗设计 **新** research fixture（建议 id 前缀 `EB1-EMPTY-RETRIEVAL-` 或等价），满足：

- in-scope `AgentToolScope`（E1–E5）
- 合成 steps **无** chunk hits → `prepare_agent_generation` → `gen_plan.refusal=true`、`gated_chunks=()`、`citations=()`
- 观察 After：`state["content"]` 对齐 `no_context_reply_for` 语义、`state["citations"]==[]`
- **不要**改写 C07/C12/C04 冻结语义来冒充此案

检索 Golden（Hit@3）即使含「应空/应拒」检索题，**仍不是**本协议 After 窗案（E-A1：Golden 不进 W10 产品路径分母）。

---

## 5. 缺口 B — Missing refusal cases（生成后）

两类拒答不得混用：

| 类型 | 现网 | 冻结 12 |
|---|---|---|
| **L0 空闸拒答** | `gen_plan.refusal=true` → 固定「未找到」类话术 | **0 案**（C01–C11 均 `plan_refusal=false`） |
| **Critic/语义不足拒答** | advisory；C07 fixture 已是不足声明正文 + **仍有 1 条 evidence**、fixture `citations=[]` | C07 oracle = `ACCEPT` + `SAFE_INSUFFICIENCY_RESPONSE`（**接受已拒答的草稿**，不是测空闸） |
| **Critic REFUSE 动作** | C04 `expected_action=REFUSE` | 控制面金标，**不是** empty-gate 观察金标 |

P2-R1 日志里 C11「retrieval 0」指 **Critic 实验步**，不是知识库空检索，**不可**当作缺口 A 已填。

**结论：** T4 的 `empty_gate_refuse_ok` **blocked_on 新 fixture**；`false_refuse_rate` 可在未来对 C01–C11 **真实生成输出**上观察（有 gated 却输出 `no_context_reply_for`），但今天无 After 输出，不得填数。

---

## 6. 明确不进入本协议分母

| 集合 | 原因 |
|---|---|
| C12 | INVALID_FOR_PRODUCT_PATH_EXECUTION；禁止解阻叙事 |
| Hit@3 golden 11 题 | 检索门禁 |
| P2-R1 inject 路径产出 | harness-only（E-A1 H1） |
| W9 fixture `answer` 直接当 generation gold | 观察点撒谎 |

---

## 7. 研究建议摘要（未来 eval 资格，非本窗实施）

1. T1：C01–C11 可作为 **run 候选**（有 gated 的保全/分桶）；须新执行器写 After 快照。  
2. T2/T3：需要 **独立 claim 金标**；禁止复用 Critic `oracle_cases` 当生成命题表。  
3. T4：必须新增 **empty-retrieval / empty-gate** eligible 案；C07/C04 **不顶**。  
4. 不在本窗改 `w9-critic-cases.json`。
