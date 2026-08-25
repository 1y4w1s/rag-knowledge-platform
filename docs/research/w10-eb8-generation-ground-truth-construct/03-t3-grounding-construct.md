# 03 — T3 grounding construct

> Defines excerpt support + citation pointer requirements. **No scoring run in this window.**

## 1. Target inheritance

来自 E-B1 T3：回答中可核验命题能否在 gated excerpt（文档名 + 位置 + 片段）中定位；用户能否指着终态引用证明出处。

首窗冻结：

```text
grounded(claim) ⇔ G1 ∧ G2
```

---

## 2. Excerpt support requirement（G1）

### 2.1 Definition

**G1 = true** 当且仅当：

1. claim 在 ledger 中标记为可支持语义（正式首窗：`label == supported`），**且**  
2. `supporting_evidence_ids` 指向的 excerpt 在 **同次观察 gated 池** 内仍存在，**且**  
3. 支撑关系可审计（`support_span_notes` 或等价规程指出跨度）

**G1 = false** 当：

| Condition | Notes |
|---|---|
| `label == unsupported` | 无辩护支撑或冲突 |
| `label == unverifiable` | 不满足「可定位支撑」 |
| evidence id 漂移出 gated 池 | 金标失效 → 案级 invalidate，而非假 G1 |

### 2.2 What G1 does *not* require

| Not required for G1 | Home |
|---|---|
| 终态 citation chip 存在 | **G2** |
| 正文含 `[片段N]` | **G2**（可作 pointer 形态之一） |
| Critic ACCEPT | Forbidden |
| Lexical overlap ≥ θ alone | Forbidden as sole rule |

---

## 3. Citation pointer requirement（G2）

### 3.1 Definition

**G2 = true** 当且仅当至少一条 **可解析指针** 成立：

| Pointer form | Operational rule |
|---|---|
| **Final citation row** | `state["citations"]` 中存在条目，其 `chunk_id` / evidence id ∈ claim 的支撑集合（或 ledger `grounding.expected_citation_ids` 与观察一致） |
| **In-body fragment mark** | 正文合法 `[片段N]`（与 `align_citations_to_answer` **同一编号空间**）映射到支撑该 claim 的 chunk |

两者满足其一即可；正式首窗 **不要求** 两者同时存在，但报表可记录形态。

### 3.2 Pointer integrity

指针必须 **解析到支撑 chunk**，不是「有任意芯片」：

| Bad pointer | G2 |
|---|---|
| 空 `citations` 且无合法标记 | false |
| chip 指向无关 chunk（张冠李戴） | false |
| 非法标记被丢弃后落到 keep-all 满表 chips | **不得**仅因满表 chips 判 G2 true（E-B0/E-B1：keep-all ≠ grounded） |
| citation 缺关键 id 无法解析 | false（形状失败；可与 E-A2 交叉记录，但不算 grounded） |

### 3.3 Optional research field（非正式首窗必报）

```text
grounded_semantic_only = G1 ∧ ¬G2
```

允许研究窗观察「资料里有、界面指不出」。**正式首窗默认不把该项算作 grounded。**

---

## 4. Primary metric

```text
grounded_rate = |{claims: grounded}| / |{claims: asserted}|
```

| Rule | Detail |
|---|---|
| Asserted denominator | 与 T2 同一 ledger / 同一 exclude 政策 |
| `unverifiable` | 进分母；**不进** grounded 分子 |
| `unsupported` | 进分母；不进 grounded 分子 |
| Refusal boilerplate | 不进分母 |
| Denom 0 | `NOT_APPLICABLE`，不得当 1.0 |

必须 **分桶** 报表：`align_bucket ∈ {shrink, keep_all, refuse_empty, fail_closed_empty}`。  
keep-all 桶的 grounded_rate **不得**单独写成产品 grounding PASS。

---

## 5. Failure cases（穷尽常用病）

| ID | Situation | T2 label (typical) | G1 | G2 | grounded |
|---|---|---|---|---|---|
| F1 | 胡编，无 citation | unsupported | F | F | F |
| F2 | 胡编，却挂合法形状 citation | unsupported | F | F* | F |
| F3 | excerpt 可支撑，但无 final citation 且无标记 | supported | T | F | F |
| F4 | excerpt 可支撑，chip 指错 chunk | supported or unsupported† | ? | F | F |
| F5 | 语义模糊 / 池外知识 | unverifiable | F | — | F |
| F6 | 拒答固定话术 | （不分母） | — | — | N/A |
| F7 | keep-all 满表 chips，命题无支撑 | unsupported | F | F | F |
| F8 | hash/pool 漂移 | — | invalidate case | invalidate | invalid |

\* F2：即便 chip「形状合法」，支撑关系不成立 → G2 按 **pointer integrity** 为 false。  
† F4：若命题本身张冠李戴则 T2=`unsupported`；若命题对但指针错，T2 可 `supported` 而 G2 false。

**成功态 S1：** `supported` ∧ G1 ∧ 正确 pointer → grounded。

---

## 6. Structural signals（二级，禁止冒充）

| Signal | Allowed use | Forbidden claim |
|---|---|---|
| 每条 final citation 是否在正文被提及 | 过引 / 漏标观察；与 T1 交叉 | 「答案已接地」 |
| `overcite_rate`（有合法标记桶） | TECH §5.12 过引 | faithfulness |
| keep-all 满表 | 记录 bucket | grounding PASS |

---

## 7. Critic / oracle isolation

| Artifact | Allowed | Forbidden |
|---|---|---|
| Independent claim ledger | Yes | — |
| Critic `expected_action` / EXACT | No | Any grounded label source |
| W9 fixture `answer` unrebound | No | After gold |
| W9 evidence excerpts via product gate | As gated pool material only | Skip gate →「已接地」 |
| Hit@3 | No | Grounding proof |

---

## 8. Observation procedure（未来执行窗，非本窗）

1. 取 After：`content` + `citations` + 同次 gated 快照 + `align_bucket`  
2. 绑定 ledger（content + pool hash）  
3. 每条 asserted claim：G1（ledger/support）∧ G2（指针完整性）  
4. 汇总 `grounded_rate`；分桶  
5. `grounding_observation_status=OBSERVED_SLOT`（≠ proven）  

零 LLM 同构：仅当 ledger 绑定合成正文时允许 **协议可算性**；禁止 `grounding proven`。

---

## 9. Minimal clearance for C3（T3 部分）

1. 与 T2 共用 ledger 规程（`01`+`02`+本文件）  
2. G1∧G2 派生规则冻结  
3. After 成对快照可得（E-B7 B2′）  
4. 零 Critic oracle  

---

## 10. Verdict

| Question | Answer |
|---|---|
| Excerpt requirement? | G1 via supported claim + auditable gated span |
| Citation requirement? | G2 via resolvable final citation or legal `[片段N]` to supporting chunk |
| Failure cases? | F1–F8 above；首窗 grounded = G1∧G2 only |
| Implemented this window? | **No** |
