# 01 — Claim ledger design

> Normative ground-truth construct. **No gold file created in this window.**

## 0. Role of the ledger

独立 claim ledger 是 T2 / T3 的 **唯一金标权威**。

| May be | Must not be |
|---|---|
| Human-authored proposition labels bound to After / synthetic body hash | Critic `oracle_cases` / `expected_action` |
| Shared segmentation for T2 and T3 | LLM-as-judge / NLI auto-label as formal gold |
| Evidence-id hints inside **same-run gated pool** | Lexical-overlap threshold as sole formal label |
| Input to deterministic scorers | Product runtime dependency (`backend/app`) |

身份常量（实现窗冻结，本窗钉意图）：

| Field | Value |
|---|---|
| Suggested path | `backend/tests/fixtures/l4_critic/w10-eb-generation-claim-gold-v1.json` |
| `protocol_version` | `w10_eb_generation_claim_gold_v1` |
| `parent_observation_protocol` | `w10_eb1_generation_observation_v1` |
| `artifact_kind` | `CLAIM_GOLD_LEDGER`（实现窗钉死字面） |
| Forbidden keys | 同 E-B2 Critic/oracle 禁键列表 |

---

## 1. Unit of judgement

**Unit = one asserted factual claim.**

| Property | Rule |
|---|---|
| Asserted | 正文对该命题持肯定/否定/数值等可核验立场（非纯疑问、非纯元话语） |
| Factual | 相对知识库片段可判定真假或可支持性（数量、期限、权限、配置值、专名断言等） |
| Atomic | 一条 claim 只承载一个可独立判定的事实原子 |
| Bound | 必须能指向 After `content`（或声明的 synthetic body）中的文本跨度或可复述片段 |

**Not a unit:**

| Non-unit | Why |
|---|---|
| Critic `expected_action` | 控制面动作，不是生成命题 |
| 整段 `no_context_reply_for` 拒答话术 | 拒答 boilerplate；进 T4，不进 T2/T3 asserted 分母 |
| 单条 `state["citations"]` 行 | citation 形状 / 指针；属 T1 或 T3-G2，不是命题本身 |
| 任意按标点切出的句子 | 切分可辅助，**标签必须人工（或同写合成金标）** |

---

## 2. Claim granularity

### 2.1 Split rules（必须拆）

| Pattern | Example intent | Claims |
|---|---|---|
| 并列事实 | 「A 限额 1000，B 限额 2000」 | 2 |
| 列表枚举事实 | 「包含 X、Y、Z 三项权限」 | 通常 3（每项一条），除非规程声明「集合命题」并写清判定规则 |
| 带引用标记的事实 | 「……[片段2]」 | 1 条命题；标记属 T1/T3 结构，不另成 claim |

### 2.2 Do not split

| Pattern | Keep as |
|---|---|
| 单一事实的修饰从句 | 1 claim（修饰进入同一命题文本） |
| 纯连接词/寒暄/「根据资料」 | **Exclude**（非 asserted） |
| 残缺半句无法解析 | `unverifiable` **或** 剔除；实现窗规程必须二选一钉死。**本构造推荐：剔除出 asserted 分母，并在 `notes` 记 `excluded_fragment`** |

### 2.3 Language

中英文命题均可；空闸拒答话术分档（中/英）属 T4，不在本 ledger 分母。

---

## 3. Annotation fields

### 3.1 Ledger header

| Field | Type | Rule |
|---|---|---|
| `protocol_version` | string | `w10_eb_generation_claim_gold_v1` |
| `parent_observation_protocol` | string | `w10_eb1_generation_observation_v1` |
| `created_by` | string | human id / role；禁止 `llm_annotator` 作为 formal |
| `notes` | string \| null | 不得声称 `grounding proven` / Critic validated |

### 3.2 Per-case entry

| Field | Type | Rule |
|---|---|---|
| `case_id` | string | W9 id、未来 empty-gate id、或 research synthetic id |
| `content_binding.kind` | enum | `observed_after` \| `synthetic_authored` |
| `content_binding.content_sha256` | string | 绑定 After / 合成正文；**mismatch → 该案 T2/T3 无效** |
| `content_binding.synthetic_body_id` | string \| null | 同构正文稳定 id |
| `gated_pool_binding.evidence_ids[]` | string[] | 标注时声明的 gated 池 id 集合（须 ⊆ 同次观察 gated） |
| `gated_pool_binding.pool_sha256` | string \| null | 可选；对 excerpts 拼接哈希，防池漂移 |
| `denominator_policy` | string | 至少含 `exclude_refusal_boilerplate` |
| `asserted_claims[]` | array | 见下；可为空仅当正文无事实命题且非拒答（极少） |

### 3.3 Per-claim row

| Field | Type | Rule |
|---|---|---|
| `claim_id` | string | 稳定；建议 `{case_id}::c{nn}` |
| `text` | string | 命题原文（可轻微规范化空白） |
| `span_optional` | `{start,end}` \| null | 相对绑定正文的字符跨度 |
| `label` | enum | `supported` \| `unsupported` \| `unverifiable` |
| `supporting_evidence_ids[]` | string[] | **仅**同次 gated 池；`supported` 时至少 1；`unsupported`/`unverifiable` 可为 [] |
| `support_span_notes` | string \| null | 标注者指出 excerpt 内支撑位置（非正式自动对齐） |
| `notes` | string \| null | 标注争议、改述说明 |

### 3.4 Optional T3 assist fields（同 ledger）

| Field | Type | Rule |
|---|---|---|
| `grounding.expected_citation_ids[]` | string[] | 期望终态 citation / evidence id（金标提示） |
| `grounding.expected_fragment_indices[]` | int[] | 期望 `[片段N]` 编号（与产品对齐空间一致） |
| `grounding.g1_required` | bool | 默认 `true` |
| `grounding.g2_required` | bool | 首窗正式 T3 默认 `true` |

**注意：** `grounding.grounded` **不作为人工必填金标布尔**。正式首窗由 scorer **派生**：`G1(from label/support) ∧ G2(from After citations)`。避免标注者同时猜 UI 芯片状态。

---

## 4. Support relationship（T2 语义核）

```text
claim  ──support?──►  same-run gated excerpts
```

| Relation | Operational meaning | Maps to label |
|---|---|---|
| **Supports** | 标注者可在 gated excerpt 中指出唯一可辩护支撑跨度（字面包含 **或** 约定可接受改述，须在 `support_span_notes` 可审计） | `supported` |
| **Conflicts** | excerpt 明确否定该事实，或命题张冠李戴到错误 evidence | `unsupported` |
| **Neither** | 池中无支撑也无明确冲突（笼统评价、池外世界知识、模糊量词且资料无对应） | `unverifiable` |

### 4.1 Evidence pool boundary（硬）

| Allowed | Forbidden |
|---|---|
| 同次 `gen_plan.gated_chunks` / 发布用 gated 快照 excerpts | 检索 Golden 命中当证据 |
| 同案 prepare 后实际 gated 的 evidence/chunk id | foreign workspace / C12 材料 |
| | Critic fixture `answer` 当证据 |
| | 标注者个人世界知识补全「显然对」 |

### 4.2 What support is *not*

| Not support | Belongs to |
|---|---|
| 仅有合法 citation chip 形状 | T1 / citation shape |
| token overlap ≥ θ | **禁止**作 formal 判定 |
| Critic `REMOVE_UNSUPPORTED_CLAIM` | Critic control plane |
| prompt 只含 gated ⇒ 已支持 | E-B1 已禁 |

---

## 5. Citation relationship（T3 指针核）

```text
claim  ──pointer?──►  final citations / [片段N]  ──must resolve──►  supporting chunk
```

| Relation | Meaning |
|---|---|
| **Pointer present** | ≥1 final citation 或合法 `[片段N]` 映射到支撑该 claim 的 chunk/evidence |
| **Pointer absent** | 语义可 `supported`（T2），但用户无法指着终态引用证明 → T3 G2 fail |
| **Pointer wrong** | chip 指向非支撑 chunk（张冠李戴）→ T3 fail；T2 亦常为 `unsupported` |

Citation relationship **不替代** support relationship：  
有芯片 ≠ 有依据；有依据 ≠ 可指着证明。

---

## 6. Unsupported claim definition（跨 T2/T3 共用）

**Unsupported claim** = asserted factual claim 相对 **同次 gated 池** 为：

1. **Conflict**（与池内事实冲突 / 张冠李戴），或  
2. **No defendable support**（池内找不到可辩护支撑跨度）

**不包括：**

| Exclude from unsupported | Why |
|---|---|
| `unverifiable` | 单独桶；不得并入 unsupported 刷高/刷低 |
| Refusal boilerplate | 不进 asserted 分母 |
| Missing `chunk_id` on citation row | E-A2 citation **形状**缺陷，≠ 命题无依据 |
| Critic 应 `REFUSE` 的剧本名 | 控制面 |

---

## 7. Binding & invalidation

| Event | Effect |
|---|---|
| `content_sha256` mismatch vs observation `final_content_observation` | 该案 T2/T3 **measurement invalid** |
| `gated_pool_binding` 与观察 gated 集合冲突 | 该案 T2/T3 **measurement invalid** |
| Ledger 含 Critic oracle 禁键 | 整文件 **reject** |
| `content_binding.kind=synthetic_authored` | 只证明协议可算性；**不得**升格为产品 faithfulness 正式证据（对齐 E-B6/E-B7） |

禁止绑定：未 rebound 的 W9 fixture `answer`；Critic `oracle_cases` 行。

---

## 8. Anti-patterns（硬拒绝）

| Anti-pattern | Verdict |
|---|---|
| Critic oracle 当 claim 标签 | **Forbidden** |
| LLM / NLI judge 当 formal 标签 | **Forbidden**（至少至 E-B formal 首窗） |
| 纯词面 overlap 自动标 | **Forbidden** as sole formal gold |
| 仅确定性切句无标签 | **Forbidden** as sole formal gold |
| C03 案名 = 已有 unsupported 金标 | **Forbidden** |
| 一张表混打 Critic action 与 T2 label | **Forbidden** |

---

## 9. Verdict

| Question | Answer |
|---|---|
| Unit? | Atomic asserted factual claim |
| Gold authority? | Independent manual ledger |
| Support? | Claim ↔ same-run gated excerpt |
| Citation? | Claim ↔ final pointer（T3）；与 support 分离 |
| Created this window? | **No** |
