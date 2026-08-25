# 04 — T4 empty retrieval / refusal fixture design

> Construct design only. **Do not create** new case files in this window.

## 1. Problem

E-B1 T4 含三条观察：

| Metric | Needs |
|---|---|
| `empty_gate_refuse_ok` | eligible ∧ 空检索/空 gated ∧ `gen_plan.refusal=true` → 固定拒答正文 ∧ `citations==[]` |
| `false_refuse_rate` | 有非空 gated 的真实 After（C01–C11 候选） |
| `refuse_with_citations` | 声称无依据却非空 citation chips |

E-B3：**冻结 12 案 evidence 均非空；E-A5 C01–C11 全部 `plan_refusal=false`；C07/C04 不顶空闸。**  
→ `empty_gate_refuse_ok` 分母 **缺失** = blocker **B4**。

代码路径已存在：`gate_agent_chunks` → `refusal=not gated`；`_stream_generation_phase` refusal → `stream_no_context_reply` / `no_context_reply_for`。

---

## 2. Are new cases required?

| Formal claim scope | New empty-gate case required? |
|---|---|
| Full T4 including `empty_gate_refuse_ok` | **Yes** |
| Narrow formal window with `targets_measured` **excluding** `empty_gate_refuse_ok` / full T4 | No for that metric；仍建议后续补齐 |
| Only T1 isomorphic | No |

**本构造对「四靶全集正式窗」决议：需要至少 1 条（建议 2 条：中/英拒答话术）新 research fixture。**  
**不**通过改写 C04/C07/C12 或 Hit@3 golden 冒充。

---

## 3. Case eligibility rules（新 fixture 必须满足）

### 3.1 L0 product-path（E-A1）

| Rule | Requirement |
|---|---|
| E1–E5 scope | in-scope `AgentToolScope`；`allowed_kb_ids` 非空且合法 |
| Provenance | steps / hits 不得 `foreign_workspace_fixture` 冒充空闸 |
| C12 类 | **禁止**用 out-of-scope 案当「应拒」——那是 INVALID，不是 empty-gate |
| Entry | 必须能走 `prepare_agent_generation`（与 E-A2 同源），不得 P2-R1 inject |

### 3.2 Empty-gate semantics

| Rule | Requirement |
|---|---|
| Retrieval / merge | scoped steps **零** chunk hits，或 merge 后 `filter_relevant_chunks` 结果为空，使得 **`gen_plan.refusal=true`**、`gated_chunks=()`、`citations=()` |
| Not semantic insufficiency | 不得「有 1 条弱 evidence 但答案不够」——那是 C07 类 Critic 剧本 |
| After expectation | `state["content"]` 对齐 `no_context_reply_for(query)` 语言档；`state["citations"]==[]` |
| Align | 拒答路径 **不**调用「有 gated 的 align keep-all」 |

### 3.3 Suite identity

| Rule | Requirement |
|---|---|
| ID prefix（建议） | `EB4-EMPTY-GATE-`（或 E-B1 曾建议的 `EB1-EMPTY-RETRIEVAL-`；实现窗钉死一种） |
| File | **新** research fixture（例：`w10-eb-empty-gate-cases.json`）；**禁止**塞进 `w9-critic-cases.json` 冒充实例化 Critic 12 |
| Oracle | **无** `expected_action`；可选 `expected_observation: empty_gate_refuse_ok` |
| Denominator | 可进入 generation observation T4 空闸分母；**不**进入 Critic capability 分母；**不**改 E-A5 11/11 分母叙事 |

### 3.4 Suggested minimal cases（设计意图，非本窗落盘）

| Suggested id | Query language | Why |
|---|---|---|
| `EB4-EMPTY-GATE-zh` | 中文 | 触发 `NO_CONTEXT_REPLY` |
| `EB4-EMPTY-GATE-en` | English | 触发 `NO_CONTEXT_REPLY_EN` |

单案也可先开中文一条；双案更覆盖话术分档。

---

## 4. Why existing C04 / C07 cannot substitute

### 4.1 C07-correct-insufficiency-refusal

| Fact | Implication |
|---|---|
| `evidence` 长度 = **1**（非空） | 不是空检索 |
| E-A5 `plan_refusal=false` | L0 闸认为有 gated，走生成而非空闸拒答 |
| Fixture `answer` = 语义不足声明；`citations=[]` | Critic **输入**剧本：已拒答的草稿 |
| Critic oracle | `ACCEPT` + `SAFE_INSUFFICIENCY_RESPONSE` | 接受「正确的不足声明」，**不是**测 `gate_agent_chunks` 空闸 |

若把 C07 当 `empty_gate_refuse_ok` 金标 → **测错层**（Critic 语义拒答 ≠ L0 空闸拒答）。

### 4.2 C04-valid-citation-wrong-evidence

| Fact | Implication |
|---|---|
| `evidence` 非空 | 有可 gate 材料 |
| E-A5 `plan_refusal=false` | 非空闸 |
| Fixture answer 含具体口令式断言 + citation | Critic 应 `REFUSE` 的硬负例 |
| Oracle `expected_action=REFUSE` | **控制面**动作金标，不是 `gen_plan.refusal` |

C04 回答的是「Critic 是否应拒绝错误断言」，不是「无命中时产品是否固定拒答且空 chips」。

### 4.3 Other near-misses（同样不顶）

| Case / set | Why not |
|---|---|
| C06 `required_fact_missing` | 有 evidence；oracle 偏 RETRIEVE |
| C12 | INVALID_FOR_PRODUCT_PATH；禁止解阻叙事 |
| Hit@3 refuse 类检索题 | 检索门禁，非 After 生成观察（E-A1） |
| P2-R1 日志「retrieval 0」 | Critic 实验步，非知识库空检索 |

---

## 5. Interaction with `false_refuse_rate`

补齐 empty-gate fixture **不替代**对 C01–C11 真实 After 的 `false_refuse_rate` 观察：

- Empty fixture → `empty_gate_refuse_ok`  
- Non-empty eligible After → 是否误输出 `no_context_reply_for`  

两者必须分母分离，禁止合成一个「拒答率」。

---

## 6. Implementation window constraints（未来，非本窗）

| Do | Don't |
|---|---|
| 新 fixture + 资格测试（refusal=true） | 改 W9 冻结 12 语义 |
| 经 prepare → stream refusal 分支取 After | 手写 After 却声称产品路径 |
| 保持 E-B2 禁 Critic 键 | 把 empty case 写进 Critic oracle |
| 更新 `targets_measured` / eligibility_summary 叙事 | 静默扩大 `suite_id=w9_critic_frozen_12` 却混入非 12 案而不改 schema 合同 |

若 empty 案进入正式 observation，须在 E-B2 后续合同修订中明确：`suite_id` 扩展 **或** 第二 suite 引用；**本窗不改 schema 常量**。

**合同注意：** 当前 E-B2 `case_count=12` / `suite_id=w9_critic_frozen_12` 冻结。引入 empty 案的正式窗必须先开 **schema/contract 修订原子窗**，或先用 **旁路 research harness** 证明空闸路径，再合并信封。本构造允许两种落地顺序，但 **YES 门禁**须写清采用哪条（见 `05`）。

---

## 7. Verdict

| Question | Answer |
|---|---|
| New cases required for full T4? | **Yes** |
| Eligibility? | in-scope ∧ empty hits → `refusal=true` ∧ After 拒答+空 citations |
| C04/C07 substitute? | **No**（有 evidence + Critic 层语义） |
| Created this window? | **No** |
