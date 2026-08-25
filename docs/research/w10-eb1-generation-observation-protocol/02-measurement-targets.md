# 02 — Measurement targets（四靶 · 仅此四项）

> 候选指标的**操作定义**冻结。本窗 **不执行**、不打分、不声称通过率。  
> **禁止**在本文件外再加质量 KPI、Critic EXACT、faithfulness 产品声称。

产品锚点（需求，非测量）：[`docs/PRD.md`](../../PRD.md) §2.1。

四靶与 E-B0 [`02-evaluation-targets.md`](../w10-eb0-generation-boundary/02-evaluation-targets.md) 对齐；本文件把它们钉到 **After 窗** 工件上。

---

## T1 — Final citation scope preservation（终态引用 scope 保全）

| 项 | 内容 |
|---|---|
| **观察什么** | 生成+对齐之后，`state["citations"]` 相对允许 scope / 本次发布用 gated 集合是否仍合法，以及相对 `gen_plan.citations` 的集合关系（shrink / keep-all / refuse_empty） |
| **工件** | **主：** `state["citations"]`（及 `done.citations` 副本）。**对照：** `gen_plan.citations`、`gen_plan.gated_chunks`、case `allowed_kb_ids` / workspace。**不用：** 单独 `gen_plan.citations` 当终态分母 |
| **操作定义** | 对 eligible 案：取 `final_ids` = `{chunk_id}` from `state["citations"]`；`plan_ids` 同理自 `gen_plan`。检查 E-A1 `04` 的 S1–S5 子集关系于 **final** 列表。分桶：`align_bucket ∈ {shrink, keep_all, refuse_empty, fail_closed_empty}`。可选：`preservation_recall = \|final ∩ plan\| / \|plan\|`（仅非空 plan）。**有合法标记桶**可另计非法下标丢弃数 |
| **不声称** | 不声称「引用被正文真正使用」；不声称 grounding；不声称 E-A5 plan scope PASS 已覆盖本靶；keep-all 桶 recall≈1 **不得**当安全/质量 PASS |

---

## T2 — Unsupported claim observation（无依据断言观察）

| 项 | 内容 |
|---|---|
| **观察什么** | `state["content"]` 中被协议声明的**事实性命题**，是否缺乏 gated excerpt 支持（胡编 / 张冠李戴） |
| **工件** | **主：** `state["content"]`。**证据池：** 同次 `gen_plan.gated_chunks`（或发布用 gated 快照）的 excerpt。**不主用：** `state["citations"]` 形状（缺 `chunk_id` 是 E-A2 `unsupported_final_citation_count`，那是 **citation 形状**，本靶是 **命题**） |
| **操作定义** | 须另有 **claim 切分 + 标注规程**（人工或未来冻结金标）：对每条 asserted claim 标 `supported \| unsupported \| unverifiable`。报表：`unsupported_claim_count`、`unsupported_rate = unsupported / asserted_claims`。拒答空/固定「未找到」正文：**不进** asserted 分母。可选观察：正文出现 foreign 文档名（E-A1 F5）——**泄漏观察**，不替代本靶 |
| **不声称** | 不声称已有 faithfulness 产品分数；不把 C03 案名或 E-A5 `scope_compliance_pass` 当成「正文无依据已测」；不把 Critic `REMOVE_UNSUPPORTED_CLAIM` oracle 当成生成金标；本窗 **零** 实测值 |

---

## T3 — Answer grounding observation（答案接地观察）

| 项 | 内容 |
|---|---|
| **观察什么** | 回答中可核验命题能否在 gated excerpt（文档名 + 位置 + 片段）中定位；用户能否指着终态引用证明出处 |
| **工件** | **主：** `state["content"]` + `state["citations"]`（对齐后）。**证据：** gated excerpts。**对照：** `gen_plan` 仅说明「模型被允许看见什么」，不证明「模型只说了那些」 |
| **操作定义** | 命题级：`grounded_rate = grounded_claims / asserted_claims`（拒答分母规则同 T2）。或对齐式：每条 final citation 是否在正文被 `[片段N]` / 等价提及；每条断言是否映射到 ≥1 条 citation。**分桶**须区分 keep-all（无标记却满表 chips）与 shrink |
| **不声称** | 不声称文笔/完整度/多跳「好」；不声称 Hit@3 11/11 ⇒ 接地；不声称 Critic EXACT / eval-L1；不声称 prompt 只含 gated ⇒ 已接地 |

---

## T4 — Refusal behavior observation（拒答行为观察）

| 项 | 内容 |
|---|---|
| **观察什么** | 无依据时是否明确拒答且不以胡编引用列表示人；有依据时是否误走固定拒答话术 |
| **工件** | **主：** `state["content"]`、`state["citations"]`。**闸门对照：** `gen_plan.refusal`（来自 `gate_agent_chunks`：`refusal=not gated`）。话术锚点：`no_context_reply_for` / `stream_no_context_reply`（`generation.py`） |
| **操作定义** | （1）`empty_gate_refuse_ok`：eligible ∧ `gen_plan.refusal=true` → 正文为固定拒答类 ∧ `state["citations"]==[]`（或协议允许的空发布）。（2）`false_refuse_rate`：有非空 gated 仍输出 `no_context_reply_for` 类固定拒答。（3）`refuse_with_citations`：声称无依据却带着非空 citation chips → 协议失败类观察。low-confidence disclaimer（TECH §5.11）与「未找到」**分档**，不得串记 |
| **不声称** | 不声称「拒答率越低越好」；不把 E-A5 全案 `plan_refusal=false` 解释成拒答功能坏/好；不把 C07 Critic oracle `ACCEPT`+`SAFE_INSUFFICIENCY_RESPONSE` 当成 **空检索拒答** 金标；不把 E-A1 `safe_outcome` 在空 citation 下的 ⊆ 真当成「正确拒答」 |

---

## 靶间边界（防串味）

| 混淆 | 正确归属 |
|---|---|
| E-A2 `unsupported_final_citation_count`（缺 chunk_id） | citation **形状** / L0 scorer，≠ T2 命题无依据 |
| E-A5 plan scope 11/11 | T1 的 **Before** 基线，≠ T1 After 已测 |
| W9 Critic expected_action | 控制面 / Critic 能力窗，≠ T2/T3/T4 |
| Hit@3 | 检索，≠ T3 |

## 状态标签

四靶在本协议下统一为：`defined_not_measured`。  
任何进度文案若写「E-B1 绿了」，必须写成「**观察点协议已冻结**」，不得写成「四靶已测过」。
