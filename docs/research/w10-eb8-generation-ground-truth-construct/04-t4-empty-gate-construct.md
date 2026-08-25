# 04 — T4 empty-gate construct

> Defines empty retrieval fixture + refusal gold. **No fixture file created in this window.**

## 1. Target inheritance

E-B1 T4 三条观察中，本构造重点钉死 **分母缺失** 的那条：

| Metric | Status in frozen W9×12 | This construct |
|---|---|---|
| `empty_gate_refuse_ok` | **MISSING denominator** | Design new fixture + gold |
| `false_refuse_rate` | Needs non-empty gated After | Not solved by empty fixture |
| `refuse_with_citations` | Needs After that claims refuse yet has chips | Separate observation |

Empty-gate fixture **只**服务 `empty_gate_refuse_ok`（及拒答路径接线）。  
**不**替代 `false_refuse_rate`；两者分母必须分离。

---

## 2. What is measured（empty-gate slice）

对每个 empty-gate eligible 案：

```text
empty_gate_refuse_ok = true ⇔
  eligible
  ∧ gen_plan.refusal == true
  ∧ gated_chunks empty
  ∧ state["content"] matches refusal gold
  ∧ state["citations"] == []
```

| Field | Rule |
|---|---|
| `gen_plan.refusal` | 来自产品 `gate_agent_chunks`（`refusal=not gated`），经 `prepare_agent_generation` |
| Refusal gold | 精确对齐 `no_context_reply_for(query)` 语言档（见 §4） |
| Citations | 必须 `[]`；非空 chips ⇒ fail（亦可能记 `refuse_with_citations` 交叉） |
| Align | 拒答路径 **不**走「有 gated 的 keep-all」成功叙事 |

---

## 3. Empty retrieval fixture requirements

### 3.1 Must create new research cases

| Requirement | Detail |
|---|---|
| New file | 例：`backend/tests/fixtures/l4_critic/w10-eb-empty-gate-cases.json` |
| New ids | 前缀钉死一种：`EB8-EMPTY-GATE-`（推荐）或历史别名 `EB4-EMPTY-GATE-` / `EB1-EMPTY-RETRIEVAL-`；**实现窗只选一种** |
| Count | Full T4 至少 **1** 条；建议 **2** 条（中/英） |
| Suite membership | **不得**塞进 `w9-critic-cases.json` 冒充第 13 个 Critic 案而不改合同 |

### 3.2 Retrieval / gate shape

| Rule | Requirement |
|---|---|
| Scope | in-scope `AgentToolScope`；`allowed_kb_ids` 非空合法（E-A1 E1–E5） |
| Hits | scoped steps **零** chunk hits，或 merge + `filter_relevant_chunks` 后为空 |
| Plan | `prepare_agent_generation` ⇒ `gen_plan.refusal=true`、`gated_chunks=()`、`citations=()` |
| Provenance | 不得用 `foreign_workspace_fixture` 冒充空闸 |
| Not insufficiency | 不得「有 1 条弱 evidence」——那是 C07 语义不足剧本 |

### 3.3 Suggested minimal cases（设计意图，非落盘）

| Suggested id | Query language | Refusal gold target |
|---|---|---|
| `EB8-EMPTY-GATE-zh` | 中文为主 | `NO_CONTEXT_REPLY` = `知识库中未找到相关内容。` |
| `EB8-EMPTY-GATE-en` | English 为主 | `NO_CONTEXT_REPLY_EN` = `No relevant content was found in the knowledge base.` |

语言档判定必须调用与产品相同的 `no_context_reply_for` 规则（ASCII 字母数 vs CJK 字数），禁止测试侧另写启发式。

---

## 4. Refusal gold

### 4.1 Authority

| Source | Role |
|---|---|
| `app.services.rag.generation.no_context_reply_for` | **唯一**拒答正文金标函数 |
| `NO_CONTEXT_REPLY` / `NO_CONTEXT_REPLY_EN` | 常量字面 |
| Fixture 内 `expected_content` | 可选镜像；必须以函数输出为准做断言 |

### 4.2 Pass / fail

| Outcome | Condition |
|---|---|
| PASS `empty_gate_refuse_ok` | `content == no_context_reply_for(query)` ∧ `citations == []` ∧ `refusal=true` |
| FAIL | 胡编正文、部分改写拒答、附加「建议」段落、非空 citations、或 `refusal=false` 却假装空闸 |
| Invalid | 案本身未真正空闸（有 gated）却标 empty-gate |

### 4.3 Explicit non-gold

| Not refusal gold | Why |
|---|---|
| C07 fixture `answer`（语义不足声明） | Critic 输入；且 evidence 非空 |
| C04 oracle `REFUSE` | Critic action |
| low-confidence disclaimer（TECH §5.11） | 与「未找到」分档，不得串记 |
| E-B6 同构作者 empty 模板正文 | 非正式产品 After；可作接线，不作 Full formal 唯一证据 |

---

## 5. Eligibility rules

### 5.1 L0 product-path

| Rule | Must |
|---|---|
| E1–E5 | in-scope；非 C12 类 out-of-scope |
| Entry | `prepare_agent_generation`（与 E-A2 同源） |
| Forbidden entry | P2-R1 `execute_frozen_case` inject |
| Denominator homes | 可进 generation observation T4 空闸分母；**不**进 Critic capability 分母；**不**改写 E-A5 11/11 叙事 |

### 5.2 Why C04 / C07 cannot substitute

| Case | Blocking fact |
|---|---|
| **C07** | evidence 长度 ≥1；E-A5 `plan_refusal=false`；测的是 Critic 对「正确不足声明」的 ACCEPT，不是 L0 空闸 |
| **C04** | evidence 非空；oracle `REFUSE` 是控制面；测错误断言是否被 Critic 拒绝 |
| **C12** | INVALID_FOR_PRODUCT_PATH；禁止解阻叙事 |
| Hit@3 refuse 题 | 检索门禁，非 After 生成观察 |

### 5.3 Interaction with claim ledger

Empty-gate 成功拒答案：

- T2/T3 asserted 分母 = **空**（boilerplate excluded）→ `NOT_APPLICABLE`  
- **不要求**为 empty-gate 案写事实 claim 行  
- Ledger 可省略该 `case_id`，或显式 `asserted_claims=[]` + `denominator_policy=exclude_refusal_boilerplate`

---

## 6. Scoring boundary（T4 empty slice only）

| In scope | Out of scope for this fixture |
|---|---|
| `empty_gate_refuse_ok` per empty case | `false_refuse_rate` on C01–C11 |
| Citations must be empty | Grounding rates |
| Refusal path wiring | Critic EXACT |

聚合时：空闸分母与非空闸分母 **分列**；禁止合成单一「拒答率」。

---

## 7. Contract coupling（预告；细节见 `05`）

引入 empty-gate 案后，E-B2 冻结的：

```text
suite_id = w9_critic_frozen_12
case_count = 12
```

**不能**在不修订合同的情况下假装分母已含空闸。  
本构造要求实现窗采用 `05` 的决议之一（新 suite 或升版合成 suite），否则 T4 空闸不得写入 `targets_measured` 的正式 Full 窗。

---

## 8. Verdict

| Question | Answer |
|---|---|
| New fixture required? | **Yes**（≥1，建议 2） |
| Refusal gold? | `no_context_reply_for(query)` exact |
| C04/C07 substitute? | **No** |
| Created this window? | **No** |
