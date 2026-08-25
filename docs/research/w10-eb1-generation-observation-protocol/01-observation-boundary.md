# 01 — Observation boundary（观察窗口）

> Normative. 本文件只定义**何时看什么**。不改产品控制面，不重写 Direction A / Critic advisory 所有权。

## 0. 与控制面的关系（不得重定义）

下列已在 W10 Decision / E-A1～E-A5 / E-B0 钉死，**本协议原样继承**：

| 已冻结命题 | 含义 |
|---|---|
| Direction A | scope / provenance = **plan-front · system-owned L0** |
| Critic | **advisory**；不得当隔离主人 |
| E-A5 允许声称 | 仅 `plan-construction citation scope compliance` |
| E-A5 观察点 | `observation_point=plan_construction_citations`（`gen_plan.citations`） |
| P2-R1 | 仍 `BLOCKED`；本协议不解阻 |

本协议**新增**的是 L1 生成后观察窗口，**不是**新的隔离闸门设计。

---

## 1. 时间切分（Before / After）

```text
  … tool steps …
        │
        ▼
  prepare_agent_generation / gate_agent_chunks
        │
        ▼
  ┌─────────────────────────────────────┐
  │  BEFORE（观察窗口左边界，含）        │
  │  gen_plan: AgentGenerationPlan      │
  │  · gated_chunks                     │
  │  · citations   ← E-A5 打分对象      │
  │  · refusal                          │
  └─────────────────────────────────────┘
        │
        ▼
  _stream_generation_phase(…, gen_plan, state, …)
  · （可选）token / critic revise
  · align_citations_to_answer（非拒答且有 gated）
        │
        ▼
  ┌─────────────────────────────────────┐
  │  AFTER（观察窗口右边界，含）         │
  │  state["content"]                   │
  │  state["citations"]  ← 本协议主对象 │
  │  （与 done.citations / 落库同对象）   │
  └─────────────────────────────────────┘
```

| 侧 | 名称 | 现网符号 | 本协议角色 |
|---|---|---|---|
| **Before** | generation plan | `AgentGenerationPlan` 实例，调用侧常名 `gen_plan` | **基线快照**（plan citations / refusal / gated ids）；**不是**本协议四靶的主打分对象 |
| **After** | generation outputs | `state["content"]`、`state["citations"]` | **主观察对象** |

### 代码锚点

| 概念 | 路径 · 符号 |
|---|---|
| Plan 类型 | `backend/app/services/agent/finalize.py` · `class AgentGenerationPlan`（`gated_chunks` / `citations` / `refusal` / `external_context`） |
| Plan 入口 | 同文件 · `prepare_agent_generation` → `gate_agent_chunks` |
| 生成相 | `backend/app/services/agent/stream.py` · `async def _stream_generation_phase`（参数 `gen_plan`、`state`） |
| 对齐 | `backend/app/services/rag/citation_align.py` · `align_citations_to_answer`（漏标 → keep-all） |
| 写入终态 | `stream.py`：`state["content"] = assistant_content`；`state["citations"] = citations`；随后 `done` 事件携带同一 `citations` |

E-A2/E-A5 适配器对 eligible 案取 `execution.gen_plan.citations` 并标为 `scorer_observation_point=plan_construction_citations`（见 `backend/tests/w10_ea2_scope_eligibility.py`）。那是 **L0 Before 窗**。本协议 **After 窗** 必须改看生成相结束后的 `state["citations"]`，否则重犯 E-A3「错观察点」（`SCORED_NON_FINAL` / F4）。

---

## 2. 窗口内（IN）

下列属于 **post-generation observation**，允许进入本协议四靶的输入集：

| 工件 | 含义 |
|---|---|
| `state["content"]` | 生成相结束后的助手正文（含拒答固定话术、fail-closed 替换后的正文） |
| `state["citations"]` | 发布用终态引用列表：默认已经过 `align_citations_to_answer`；拒答 / critic fail-closed 路径可为 `[]` |
| SSE `done.citations` | 须与 `state["citations"]` **同一对象语义**（E-A1 `04`）；记录时应拷贝 `scored_citations` |
| 相对 `gen_plan` 的 **diff 字段** | 例如 `plan_citation_ids` vs `final_citation_ids`、`align_bucket=keep_all\|shrink\|refuse_empty`——**仅作观测元数据**，不把 plan 列表重新标成「终态」 |
| 同一次 run 的 `gen_plan.refusal` / `gen_plan.gated_chunks` 快照 | 用于分桶与拒答通道判定（空 gated vs 有 gated） |

---

## 3. 窗口外（OUT）

下列 **不在**本观察窗口内；可引用为对照，但不得当作本协议「已观察生成」：

| 排除项 | 原因 |
|---|---|
| **Plan-construction 本身**（E-A5） | 那是 L0；观察的是 plan citations ⊆ scope，不是生成输出 |
| 首 token 前流出的候选 `citation` SSE | 可被对齐覆盖；E-A1：不是 final |
| Critic 输入 `chunks` / `kb_ids` / action oracle | advisory；非 `state["citations"]` |
| `AgentGenerationPlan.citations` **单独**当终态分母 | F4：`SCORED_NON_FINAL` |
| W9 fixture 里的 `answer` / `citations` 字段 | 那是 **Critic model-facing 输入**（`w9-critic-cases.json`），不是产品 `_stream_generation_phase` 输出 |
| Hit@3 / `test_retrieval_golden.py` | 检索排序门禁，非生成观察 |
| Direction B merge 再过滤 / H2 污染探针 | Decision 残差；本协议不打开 |
| 控制面「是否应 ACCEPT/REVISE/REFUSE」 | W9 Critic 控制面评测；≠ 本四靶 |

---

## 4. 对齐与拒答对「After」的影响（机制，非质量）

| 路径 | 对 `state["citations"]` 的影响 | Evidence |
|---|---|---|
| 正常生成 + 有合法 `[片段N]` | 按标记裁剪（shrink） | `align_citations_to_answer` |
| 生成但无合法标记 | **keep-all**（保留当时 gated 全表） | `citation_align.py` docstring；TECH §5.12.1 |
| `gen_plan.refusal`（无 gated） | 走 `stream_no_context_reply`；不对齐；终态应为拒答正文 + 空/未发布满表引用（实现以 stream 为准） | `stream.py` refusal 分支 |
| critic fail-closed | 可替换为 `no_context_reply_for` 且 `citations=[]` | `stream.py` |

本协议要求后续测量：**记录对齐分桶**，禁止把 keep-all 的「引用列表非空」解释为 grounding PASS（E-B0 U3）。

---

## 5. 一句话边界

> **E-B1 观察的是 generation outputs（`content` + 对齐后 `citations`），不是 plan-construction（那是 E-A5），也不是 Critic 能力或控制面裁决。**
