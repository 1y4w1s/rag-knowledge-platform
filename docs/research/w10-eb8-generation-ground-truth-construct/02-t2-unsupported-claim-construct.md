# 02 — T2 unsupported claim construct

> Defines what T2 measures. **No scoring run in this window.**

## 1. Target inheritance

来自 E-B1 T2：观察 `state["content"]` 中事实性命题相对同次 gated excerpt 是否缺乏支持（胡编 / 张冠李戴）。

本文件钉死：**测什么、不测什么、计分边界**。金标形态见 [`01-claim-ledger-design.md`](01-claim-ledger-design.md)。

---

## 2. What is measured

对每个 **eligible ∧ 进入 T2 分母** 的案：

| Measured quantity | Definition |
|---|---|
| `asserted_claims` | ledger 中进入分母的命题集合（已排除拒答 boilerplate / 剔除残片） |
| `unsupported_claim_count` | `label == unsupported` 的条数 |
| `unsupported_rate` | `unsupported_claim_count / |asserted_claims|`（分母为 0 则该案 T2 **undefined**，记 `NOT_APPLICABLE`，不得当 0.0 PASS） |
| Optional: `supported_count` / `unverifiable_count` | 分桶报表；**不得**把 unverifiable 并入 unsupported |

**判定依据：** 仅 ledger `label`（人工或同写合成金标）相对 **同次 gated 池**。  
Scorer 可校验：`supported` ⇒ `supporting_evidence_ids` 非空且 ⊆ 观察 gated；失败则 **invalidate** 该案而非静默改标签。

---

## 3. What is not measured

| Not measured | Correct home |
|---|---|
| 终态 citation 是否仍在 scope / align_bucket | **T1** |
| 用户能否指着 chip / `[片段N]` 证明出处 | **T3 G2** |
| 空闸是否固定拒答 | **T4** `empty_gate_refuse_ok` |
| 有 gated 却误输出固定拒答 | **T4** `false_refuse_rate` |
| Citation 缺 `chunk_id` | E-A2 `unsupported_final_citation_count`（形状） |
| Critic 是否该 `REMOVE_UNSUPPORTED_CLAIM` | W9 Critic capability |
| 文笔、完整度、多跳推理「好不好」 | Out of E-B scope |
| Hit@3 / 检索召回 | Retrieval gate |
| E-A5 plan scope 11/11 | Before L0；≠ T2 |

一句话：**T2 只回答「命题相对 gated 资料有没有依据」，不回答「引用列表漂不漂亮」。**

---

## 4. Scoring boundary

### 4.1 Denominator inclusion

| Include in asserted denominator | Exclude |
|---|---|
| 可真假事实句（含带 `[片段N]` 的事实） | `no_context_reply_for` / `NO_CONTEXT_REPLY(_EN)` 整段 |
| 并列事实拆开后的每条 | 纯寒暄、元话语（「根据资料」「如下」） |
| | 按规程剔除的残缺半句 |
| | C12 / `INELIGIBLE` 案 |

### 4.2 Label → score contribution

| Label | Counts in denominator? | Counts in unsupported numerator? |
|---|---|---|
| `supported` | Yes | No |
| `unsupported` | Yes | Yes |
| `unverifiable` | Yes（默认） | No |

**冻结脚注：** unverifiable **进分母、不进 unsupported 分子**。若未来研究窗改政策，必须升 `protocol_version`，禁止静默改语义。

### 4.3 Case-level validity gates

案级 T2 仅当全部成立：

1. L0/L1 eligible（非 C12）  
2. After（或声明 synthetic）正文存在且 hash 绑定 ledger  
3. Ledger 行存在且无 Critic 禁键  
4. `targets_measured` 含 `T2`（否则应 `NOT_OBSERVED`，不得填假分数）  
5. `|asserted_claims| > 0` 或显式 `NOT_APPLICABLE`  

### 4.4 Suite aggregation

| Rule | Detail |
|---|---|
| Micro | 全套件合计 unsupported / 合计 asserted |
| Macro | 各案 `unsupported_rate` 再平均（仅对有定义的案） |
| Reporting | 必须同时给出 micro + 分母案数；禁止只报「好看」的一个 |

合成正文路径：允许协议接线分数；`measurement_claims` **不得**断言产品无依据已测通。

---

## 5. Failure / success readings（观察语义，非产品 PASS 口号）

| Observation | Reading |
|---|---|
| High `unsupported_rate` on real After | 生成胡编 / 张冠李戴风险信号 |
| Low rate on synthetic authored body | **仅**协议可算；非模型质量 |
| `NOT_APPLICABLE` on pure refusal body | 期望；转 T4 |
| Hash mismatch | 测量无效，不是「0 unsupported」 |

---

## 6. Relationship to T3

| Shared | Split |
|---|---|
| 同一 claim 切分与 ledger | T2 不要求 G2 citation pointer |
| `unsupported` 标签对齐 | T3 `grounded` 另需 G1∧G2 |
| | T2 `supported` + G2 fail ⇒ T3 不 grounded（见 `03`） |

---

## 7. Minimal clearance for C3（T2 部分）

消除 E-B7 **B3** 中 T2 侧，须：

1. 本构造 + `01` 字段规程已实现为可校验 ledger 文件  
2. 每个 `targets_measured∋T2` 的分母案有绑定 hash 的标注行  
3. Validator 拒绝 Critic oracle 键与 lexical-only 伪金标  

若正式窗不含 T2，须在 artifact 诚实排除，不阻塞窄窗。

---

## 8. Verdict

| Question | Answer |
|---|---|
| Measured? | Unsupported rate of asserted claims vs gated excerpts |
| Not measured? | Citation UX, Critic, T4 refusal, retrieval, prose quality |
| Scoring boundary? | Exclude refusal boilerplate；unverifiable in denom, not in unsupported num |
| Implemented this window? | **No** |
