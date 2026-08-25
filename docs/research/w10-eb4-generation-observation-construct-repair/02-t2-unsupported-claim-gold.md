# 02 — T2 unsupported claim gold strategy

> Construct design only. No gold file, no annotation run, no LLM in this window.

## 1. Problem

E-B1 已定义 T2：**对 `state["content"]` 中事实性命题标 `supported | unsupported | unverifiable`**。  
E-B3 判定：**操作定义 DEFINED，但独立 claim 金标 MISSING**。  
Critic `oracle_cases` / `expected_action=REVISE…REMOVE_UNSUPPORTED_CLAIM`（如 C03）**禁止**当生成命题金标。

无金标 → 正式窗不能诚实声称测了 T2。

---

## 2. Options compared

| Option | How it would work | Pros | Cons | Verdict |
|---|---|---|---|---|
| **A. Manual annotation** | 对 After `content`（或绑定的合成正文）人工切分命题并标注；冻结独立 ledger | 可审计、可复现、与 Critic 解耦；中文事实句可控 | 成本高；标注者需规程；真实模型 After 需等执行窗 | **主选** |
| **B. Deterministic claim extraction only** | 标点/规则切句，无标签或弱启发标签 | 便宜、可脚本化 | 无「是否有依据」真值；切分噪声大；易假绿 | **拒绝作唯一金标** |
| **C. Rule-based gold on designed bodies** | 作者写死合成正文 + 同步写死 claim 表（同构零 LLM） | 零模型、可测协议接线 | 不证明真实模型 faithfulness；正文必须作者拥有 | **辅选**（协议/接线；不得外推产品质量） |
| **D. Critic oracle reuse** | 用 `expected_action` / reason code | 已有文件 | E-B2 硬拒；控制面 ≠ 生成命题；C03 案名 ≠ 已测 | **禁止** |
| **E. NLI / LLM-as-judge** | 模型判 entailment | 可扩展 | 本轨禁止未授权 LLM；引入第二 oracle；不稳定 | **禁止**（至少在 E-B formal 首窗前） |
| **F. Lexical overlap auto-label** | token overlap(excerpt, claim) 阈值 | 全自动 | 改述假阴、共现假阳；与 PRD「可指着引用证明」不对齐 | **禁止作正式金标** |

---

## 3. Chosen approach（决议）

### 3.1 Primary: Independent manual claim ledger

**金标形态：** 独立文件（未来窗创建，建议名）：

```text
backend/tests/fixtures/l4_critic/w10-eb-generation-claim-gold-v1.json
```

**身份常量（建议冻结）：**

| Field | Value |
|---|---|
| `protocol_version` | `w10_eb_generation_claim_gold_v1` |
| `parent_observation_protocol` | `w10_eb1_generation_observation_v1` |
| `binds_to` | After `content` hash **或** `synthetic_body_id`（同构） |
| Forbidden keys | 一切 Critic oracle 键（同 E-B2 列表） |

**每案结构（规范意图）：**

```text
case_id
content_binding: { kind: observed_after | synthetic_authored, content_sha256, ... }
asserted_claims[]:
  claim_id
  text
  span_optional
  label: supported | unsupported | unverifiable
  supporting_evidence_ids[]   # 仅 gated 池内 evidence_id / chunk_id
  notes
denominator_policy: exclude_refusal_boilerplate
```

### 3.2 Secondary: Construction-time labels for isomorphic bodies

当 After 来自 **作者控制合成正文**（见 `01` §2.3）：

- claim 表与正文 **同窗编写、同 hash 绑定**  
- 允许规则校验：「标注为 supported 的 claim 必须能在 gated excerpt 中定位字面或约定改述」  
- **不得**把该测量写成「模型无依据断言已测」

### 3.3 Explicitly not chosen as primary

- 仅确定性切分（B）  
- Critic oracle（D）  
- LLM judge（E）  
- 纯词面重叠（F）  

---

## 4. Annotation protocol（操作规程草案）

### 4.1 What counts as an asserted claim

| Include | Exclude |
|---|---|
| 可真假的事实句（数量、期限、权限、配置值等） | 纯寒暄、元话语（「根据资料」「如下」） |
| 并列事实拆成多条（C10 风格：两条限额 = 两条 claim） | 固定拒答话术整段（`no_context_reply_for` 类）→ **不进 asserted 分母** |
| 带 `[片段N]` 的事实仍计为命题（标记另属 T1/T3 结构） | 无法解析的残缺半句 → `unverifiable` 或剔除（规程须固定一种） |

### 4.2 Label definitions（T2）

| Label | Meaning |
|---|---|
| `supported` | 该命题可被 **同次** `gen_plan.gated_chunks` excerpt（文档名+位置+片段）支持：字面包含或标注者可指出唯一支撑跨度 |
| `unsupported` | 命题与 gated 池冲突，或 gated 池明确不支持该事实（胡编 / 张冠李戴） |
| `unverifiable` | 既非明确支持也非明确否定（笼统评价、池外世界知识、模糊量词且资料无对应） |

**证据池边界：** 只用同次 gated excerpts。  
**禁止：** 用检索 Golden、用 foreign workspace、用 Critic 草稿答案当证据。

### 4.3 Metrics（继承 E-B1，仍未测）

- `unsupported_claim_count`  
- `unsupported_rate = unsupported / asserted_claims`  
- 拒答空/固定「未找到」正文：**不进** asserted 分母  

### 4.4 Anti-patterns

| Anti-pattern | Why |
|---|---|
| 用 C03 案名当「已有 unsupported 金标」 | 案名描述 Critic 输入剧本，不是 After 金标 |
| 把 E-A2 `unsupported_final_citation_count` 当 T2 | 那是缺 `chunk_id` 的 **citation 形状** |
| 一张表混打 Critic `REMOVE_UNSUPPORTED_CLAIM` 与 T2 | 控制面 vs 生成观察 |

---

## 5. Binding to After snapshots

| Content source | Gold allowed? | What it proves |
|---|---|---|
| Real `_stream_generation_phase` After | Yes（人工标） | T2 on product path（授权模型窗后） |
| Author synthetic After | Yes（同写金标） | Protocol / scorability only |
| W9 fixture `answer` without rebinding as synthetic | **No** | 观察点撒谎 |
| Critic oracle row | **No** | — |

`content_sha256` 必须匹配观察 artifact 中的 `final_content_observation`。哈希漂移 → 该案 T2 **无效**，不得静默沿用旧金标。

---

## 6. Minimal readiness contribution（对门禁）

消除 E-B3 **B3** 中 T2 部分，须同时满足：

1. Claim gold 规程已冻结（本文件 + 未来 fixture 头字段）  
2. 对每个将列入 `targets_measured` 含 `T2` 的分母案，存在绑定 After 正文的标注行  
3. Validator / 评审清单确认 **无** Critic oracle 键  

若正式窗 `targets_measured` **不含** T2，则 T2 金标不阻塞该窄窗（须在 artifact 诚实声明）。

---

## 7. Verdict

| Question | Answer |
|---|---|
| Chosen strategy? | **Independent manual claim ledger** (+ construction-time labels for isomorphic bodies) |
| Rejected? | Critic oracle · LLM judge · extraction-only · lexical auto-label as formal gold |
| Implemented this window? | **No** |
