# 02 — Measurement target validity

> Dimension 2. Classify each E-B1 target as PROVEN / DEFINED / MISSING.  
> Labels（本目录强制）：

| Label | Meaning |
|---|---|
| **PROVEN** | Implemented **and** observable today（有 After 工件或已测值） |
| **DEFINED** | Protocol / schema 已定义操作语义，但尚未测量 |
| **MISSING** | 需要新 fixture、金标、或 runtime/executor 能力才能测 |

产品需求锚点（非测量）：`docs/PRD.md` §2.1。

---

## T1 — Final citation scope preservation

| 项 | 内容 |
|---|---|
| **Protocol** | E-B1 `02`：对 `state["citations"]` 做 S1–S5 子集；记录 `align_bucket ∈ {shrink, keep_all, refuse_empty, fail_closed_empty}`；对照 `gen_plan` |
| **Runtime mechanism** | `align_citations_to_answer` 已实现；stream 在非拒答路径调用 | 
| **Formal observation today** | 无 After 列表；E-A5 只测 plan |

**Classification: DEFINED**（机制可支撑未来测量；**不是** PROVEN，因为零 After 观测值）

- 子项「align 实现存在」可标机制 **PROVEN**（代码 + TECH §5.12），但 **靶本身未测** → 整靶仍为 DEFINED。  
- 进入正式窗前还缺：After 产出器（维度 5 blocker #1）。

---

## T2 — Unsupported claim observation

| 项 | 内容 |
|---|---|
| **Protocol** | E-B1：对 `state["content"]` 命题标 `supported \| unsupported \| unverifiable` |
| **Not** | E-A2 `unsupported_final_citation_count`（缺 `chunk_id` 形状）；C03 案名；Critic `REMOVE_UNSUPPORTED_CLAIM` |

**Classification: DEFINED + MISSING**

- **DEFINED：** 操作定义冻结。  
- **MISSING：** 独立 claim 切分/金标；真实 After `content`。  
- **不是 PROVEN。**

---

## T3 — Answer grounding observation

| 项 | 内容 |
|---|---|
| **Protocol** | E-B1：`grounded_rate` 或 citation↔正文对齐；须分桶 keep-all vs shrink |
| **Not** | Hit@3；Critic EXACT；「prompt 只含 gated ⇒ 已接地」 |

**Classification: DEFINED + MISSING**

- **DEFINED：** 操作定义冻结。  
- **MISSING：** 命题金标 + After `content`/`citations` 成对快照。  
- **不是 PROVEN。**

---

## T4 — Refusal behavior observation

| 项 | 内容 |
|---|---|
| **Protocol** | E-B1：`empty_gate_refuse_ok` · `false_refuse_rate` · `refuse_with_citations` |
| **Runtime** | `gen_plan.refusal` → `stream_no_context_reply`；fail-closed → `citations=[]` |

| 子指标 | Classification | 理由 |
|---|---|---|
| `empty_gate_refuse_ok` | **DEFINED + MISSING** | 代码路径存在；冻结 12 **无** empty evidence / `plan_refusal=true` 案 |
| `false_refuse_rate` | **DEFINED** | 可对未来 C01–C11 **真实 After** 观察；今日无 After |
| `refuse_with_citations` | **DEFINED** | 同上 |

**Classification（整靶）: DEFINED + MISSING**（空闸分母缺失使 T4 无法完整正式测）

---

## Summary table

| Target | PROVEN | DEFINED | MISSING |
|---|---|---|---|
| T1 final citation scope preservation | —（机制可 PROVEN） | **YES** | After executor / snapshots |
| T2 unsupported claim | — | **YES** | claim gold + After content |
| T3 answer grounding | — | **YES** | claim gold + After pair |
| T4 refusal behavior | — | **YES** | empty-gate eligible case（至少对 `empty_gate_refuse_ok`） |

**没有任何四靶被标为「已测量 PROVEN」。**  
进度文案若写「E-B 绿了」，只允许指「边界/协议/信封冻结」，不得指「四靶已测」。
