# 03 — T3 grounding observation strategy

> Construct design only. No scoring, no Critic, no LLM in this window.

## 1. Problem

E-B1 T3：**回答中可核验命题能否在 gated excerpt（文档名 + 位置 + 片段）中定位；用户能否指着终态引用证明出处。**  
E-B3：**DEFINED + MISSING**（缺命题金标 + After 成对快照）。  
禁止：Hit@3、Critic EXACT、`prompt 只含 gated ⇒ 已接地`、keep-all 满表 chips 当 grounding PASS。

---

## 2. What counts as grounded

对每条 **asserted claim**（切分规则与 T2 共用 ledger）：

| Verdict | Operational rule |
|---|---|
| **grounded** | （G1）claim 在同次 gated excerpt 中可定位支撑跨度；**且**（G2）协议要求的引用可指性成立：至少一条 **final** citation（`state["citations"]`）对应该支撑 chunk / evidence，**或**正文合法 `[片段N]` 映射到该 chunk（与 `align_citations_to_answer` 同一编号空间） |
| **unsupported** | claim 与 gated 池冲突，或池中无任何可辩护支撑（与 T2 `unsupported` 对齐） |
| **unverifiable** | 无法判定支持/不支持（与 T2 对齐）；**不计入** `grounded_rate` 分子，分母策略须在报表脚注固定（建议：unverifiable 进分母但不进 grounded） |

### 2.1 Preferred primary metric

```text
grounded_rate = |{claims: grounded}| / |{claims: asserted}|
```

拒答固定话术：**不进** asserted 分母（同 T2）。

### 2.2 Structural alignment signals（二级，不得冒充语义接地）

| Signal | Use | Must not claim |
|---|---|---|
| 每条 final citation 是否在正文被 `[片段N]` / 等价提及 | 过引 / 漏标观察；与 T1 分桶交叉 | 「答案已接地」 |
| 有合法标记桶的 `overcite_rate` | TECH §5.12 过引目标 | faithfulness |
| keep-all 桶满表 chips | 记录 `align_bucket=keep_all` | grounding PASS（E-B0 U3） |

报表必须 **分桶**：`keep_all` vs `shrink` vs `refuse_empty` / `fail_closed_empty`。

---

## 3. What counts as unsupported（T3 视角）

与 T2 标签一致，但 T3 额外强调 **用户可追责**：

| Case | T3 reading |
|---|---|
| 命题胡编且无 citation | unsupported；亦可能触发 T4 `refuse_with_citations` 的对偶病（无依据却有 chips）时分项记录 |
| 命题胡编但挂了「合法形状」citation（张冠李戴） | unsupported（语义）；T1 仍可能 scope-safe → **证明 T1≠T3** |
| 命题有 excerpt 支撑但无 final citation 且无标记 | 语义可 `supported`（T2），T3 **G2 失败** → 不得标 grounded（可单列 `grounded_semantic_only` 研究字段，正式首窗可不启用） |

**正式首窗建议：** grounded 采用 **G1∧G2**，避免「资料里有、用户界面却指不出」假绿。

---

## 4. Avoiding Critic oracle dependency

| Critic artifact | Allowed use in T3 | Forbidden use |
|---|---|---|
| `w9-critic-capability-contract.json` `oracle_cases` | 无 | 任何 grounded/unsupported 标签来源 |
| `expected_action` / reason codes | 无 | 映射为 grounding 分数 |
| Fixture `answer` as Critic input | 无（除非作者显式 rebase 为 synthetic + 新金标） | 直接当 After gold |
| W9 case **evidence excerpts** | 可作为 **gated 池材料**（经产品 prepare/gate 后） | 跳过 gate 直接当「已生成并接地」 |

**独立金标：** 与 T2 **同一 claim ledger**（`02`）。  
T3 不另造 Critic 旁路；只在 ledger 上增加可选字段：

```text
grounding:
  grounded: bool
  citation_ids[] | fragment_indices[]
  align_bucket_at_observation
```

或由观察器在金标 + After 对上 **派生** grounded 布尔（金标提供 supported + 映射提示；观察器检查 final citations）。派生逻辑必须确定性、零 LLM。

---

## 5. Relationship to T1 / T2 / E-A5

| Confusion | Correct split |
|---|---|
| E-A5 plan scope 11/11 | Before；≠ grounding |
| T1 preservation / align_bucket | 列表合法性与裁剪；≠ 命题真值 |
| T2 unsupported_rate | 命题 vs excerpt；可与 T3 共用切分 |
| T3 grounded_rate | 命题可定位 **且**（首窗）可指终态引用 |
| Hit@3 | 检索；禁止 |

---

## 6. Observation procedure（未来执行窗）

1. 取得 After：`content` + `citations` + 同次 `gated_chunks` 快照 + `align_bucket`  
2. 绑定 claim ledger（hash 校验）  
3. 对每条 asserted claim：查 G1（金标/规程）与 G2（final citations / 标记）  
4. 汇总 `grounded_rate`；分桶输出  
5. `grounding_observation_status=OBSERVED_SLOT`（仍 ≠ proven 产品声称）  

零 LLM 同构窗：仅当 ledger 绑定合成正文时允许观察 **协议可算性**；`measurement_claims` 不得断言 `grounding proven`（E-B2 已禁）。

---

## 7. Minimal readiness contribution（对门禁）

消除 B3 中 T3 部分须：

1. T2/T3 共用 claim 规程已冻（`02`+本文件）  
2. 金标含 grounding 判定所需字段或派生规则  
3. After 成对快照存在（B2）  
4. 无 Critic oracle 依赖  

`targets_measured` 不含 T3 → 不阻塞窄窗。

---

## 8. Verdict

| Question | Answer |
|---|---|
| Grounded? | G1 excerpt 可定位 ∧ G2 终态引用可指性（首窗） |
| Unsupported? | 与 T2 对齐的无支撑/冲突命题；G2 失败不得标 grounded |
| Critic dependency? | **None** — independent ledger only |
| Implemented this window? | **No** |
