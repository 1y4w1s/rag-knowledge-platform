# 01 — Minimal After-window executor boundary

> Construct design only. No implementation in this window.

## 1. Purpose

E-B3 blocker **B1 / B2**：E-B2 模块只有校验器 / schema example，没有对标 E-A4 `run_formal_window` 的 After 产出器；因此无法诚实写出 `FORMAL_OBSERVATION_RESULT` 的 `final_content_observation` / `final_citations`。

本文件冻结 **最小 After 窗 executor** 的合法边界：走哪条运行时路径、禁止哪些捷径、如何与 E-A5 彻底分离。

---

## 2. Required runtime path（必须）

### 2.1 Canonical product After path

正式 generation observation（凡声称观察「产品生成终态」）必须满足：

```text
W9 case (C01–C11 eligible only)
        │
        ▼
classify eligibility (w10_ea1_scope_eligibility)
        │  C12 → refuse; INELIGIBLE; no After fabricate
        ▼
build AgentToolScope + scoped step records
        │
        ▼
prepare_agent_generation  →  gen_plan   ← BEFORE (对照基线)
        │
        ▼
_stream_generation_phase(..., gen_plan, state, ...)
  · refusal=true  → stream_no_context_reply / 固定拒答话术
  · else          → (可选 critic) → align_citations_to_answer
        │
        ▼
AFTER snapshot
  state["content"]   → per_case.final_content_observation
  state["citations"] → per_case.final_citations
  (+ align_bucket / plan_ids 元数据，非主体)
```

| Step | Code anchor | Role |
|---|---|---|
| Eligibility | `tests.w10_ea1` / E-A2 `classify_case_eligibility` | L0 准入；C12 拒 |
| Plan | `finalize.prepare_agent_generation` → `gate_agent_chunks` | Before 快照 |
| Stream | `stream._stream_generation_phase` | 唯一产品生成相 |
| Align | `citation_align.align_citations_to_answer` | 非拒答路径终态裁剪 |
| Capture | `state["content"]` / `state["citations"]` | E-B2 After 槽 |

### 2.2 Executor surface（未来实现窗必须提供的符号）

对标 E-A4，未来 E-B 合同模块（或其后继）须暴露等价能力，名称可调整但语义不可漂：

| Required capability | E-A5 analogue | E-B requirement |
|---|---|---|
| Suite runner | `run_formal_window` | `run_formal_observation`（或同义） |
| Per-case After produce | *absent*（E-A2 停在 plan） | 必须调用生成相或诚实同构 After 写入 |
| Artifact validate | `validate_reserved_artifact` | **复用 E-B2**；不得换信封 |
| Write formal result | `write_formal_window_result` | 仅写 reserved `w10-eb2-generation-observation-result.json`；**禁止**覆盖 E-A5 文件 |

**最小诚实条件：** 对每个 `targets_measured` 分母案，`final_content_observation` 与 `final_citations` **不得**为「未跑生成却填了假终态」；schema example 的 `null` 不得被静默当成已观察。

### 2.3 Allowed zero-LLM isomorphic After path（窄窗）

在 **owner 书面授权零 LLM** 且 `measurement_validity` / `notes` **诚实声明**时，允许同构路径仅用于：

- **T1**（终态 citation scope / align 分桶）机械观察  
- executor / 信封接线冒烟  

同构路径仍须：

1. 使用真实 `prepare_agent_generation` 得到 `gen_plan`（与 E-A2 同源，**不是** inject foreign gated）  
2. 用 **作者控制** 的 `assistant_content`（可含合法 `[片段N]`）喂入 **真实** `align_citations_to_answer`  
3. 将对齐后列表写入 `state["citations"]` 语义的 After 槽  
4. 在 artifact 中标记：`llm_called=false`；`targets_measured` **不得**包含需要真实模型命题的 T2/T3，除非金标明确绑定该合成正文  

```text
prepare_agent_generation → gen_plan
        │
        ▼
synthetic_content  (author-owned; NOT w9 fixture answer as “product”)
        │
        ▼
align_citations_to_answer(synthetic_content, gated_chunks, ...)
        │
        ▼
AFTER: content=synthetic_content; citations=aligned
```

**同构路径不是产品 faithfulness 证明。** 它只证明：对齐机制 + 信封 + T1 分桶可观测。

---

## 3. Forbidden shortcuts（硬禁止）

| Shortcut | Why forbidden |
|---|---|
| 把 `w9-critic-cases.json` 的 `answer` / `citations` 写入 After | Critic model-facing 输入 ≠ `_stream_generation_phase` 输出（E-B1/E-B3） |
| `artifact_from_execution` 默认 `final_citations = gen_plan.citations` 当 After | E-A2 L0 便利；重犯 E-A3 `SCORED_NON_FINAL` |
| 只复制 E-A5 `per_case_result` / `scope_compliance_pass` | 观察点撒谎；E-B2 validator 已拒 |
| P2-R1 `execute_frozen_case` / 直接 inject `gated_chunks` 进 stream | harness-only；E-A1 H1；不得进产品分母 |
| P2-R3 formal product rerun 身份 / 文件当 E-B 结果 | 栈错误；E-B2 已拒 |
| Critic `expected_action` / `oracle_cases` 填 grounding / refusal 状态 | 控制面 ≠ T2/T3/T4 |
| 空跑却 `measurement_valid=true` | 契约撒谎 |
| 改 `backend/app`「为了好测」放宽拒答 / 对齐 | 本轨评测不得扭曲产品 |

---

## 4. Separation from E-A5（硬隔离）

| Dimension | E-A5（L0） | E-B After executor（L1 观察） |
|---|---|---|
| Observation point | `plan_construction_citations` | `generation_final_content_and_citations` |
| Primary object | `gen_plan.citations` | `state["content"]` + `state["citations"]` |
| Envelope array | `per_case_result` | `per_case_observation` |
| Runner | `w10_ea4_*` / E-A2 adapter | `w10_eb2_generation_observation_*` |
| Allowed claim | `plan-construction citation scope compliance` | `generation observation artifact produced`（正式窗仍禁止三条 quality/grounding/Critic） |
| Stops at | `prepare_agent_generation` | **必须越过** prepare，进入生成相或诚实同构 After |
| Result file | `w10-ea4-formal-window-result.json` | `w10-eb2-generation-observation-result.json` |

一句话：

> **E-A5 解决「计划引用是否 scope-safe」；E-B executor 解决「生成（或诚实同构）之后用户看到什么」。二者可父子引用文件名，禁止算术合并通过率。**

### 4.1 What E-B executor may reuse from E-A2

| Reuse | OK? |
|---|---|
| `load_frozen_suite` / eligibility / `AgentToolScope` / scoped steps | **Yes** |
| `execute_product_path_plan` as **Before** builder | **Yes**（停在 plan） |
| `artifact_from_execution` 的 **默认 final=plan citations** | **No**（必须另写 After） |
| E-A5 pass 布尔 / 11/11 | **No**（不得写入 E-B `asserted` 或冒充 T1） |

---

## 5. Snapshot discipline（消除 B2）

| Rule | Detail |
|---|---|
| Snapshot source | 仅来自 §2 路径结束时的 After 对象 |
| Schema example | After 字段保持 `null` / `NOT_OBSERVED` |
| Formal result | 分母案必须非 null（或显式 `INELIGIBLE` / out-of-target） |
| Diff metadata | `plan_citation_ids` vs `final_citation_ids`、`align_bucket` 可记；**不得**把 plan 列表标成 final |
| Refusal path | `gen_plan.refusal=true` → 期望固定拒答类正文 + 空 citations（以 stream 实现为准）；不对齐满表 chips |

无快照 = 无可测分母。Executor 存在但未写出 After，仍算 B2 未消。

---

## 6. Critic / LLM policy for executor

| Mode | LLM | Critic | Allowed targets |
|---|---|---|---|
| Formal product After（需 owner 授权模型窗） | 产品 chat 路径真实调用 | 保持现网默认（通常关 / rules）；**不得**把 Critic action 当金标 | T1–T4（金标齐时） |
| Zero-LLM isomorphic | **禁止** | **禁止**依赖 | **默认仅 T1**（+ 信封冒烟） |
| This E-B4 window | **禁止** | **禁止** | 仅文档 |

P2-R1 保持 `BLOCKED`。Executor 不得声称解阻。

---

## 7. Minimal DoD for future executor window（非本窗）

未来实现窗验收建议（可复制意图，非本窗执行）：

1. 模块提供 After 产出函数；C12 仍 `INELIGIBLE`  
2. Eligible 案写入非 null After **或** 诚实同构 + `llm_called` 正确  
3. E-A5 JSON 仍被 E-B2 validator 拒绝  
4. 禁止键（Critic / `per_case_result` / `scope_compliance_pass`）仍失败关闭  
5. **零**正式结果文件，除非该窗明确是「formal observation 执行」且门禁已 YES  

---

## 8. Verdict

| Question | Answer |
|---|---|
| Minimal required path? | prepare → stream（或诚实同构 align）→ capture After |
| Forbidden shortcuts? | fixture 回填、plan-as-final、P2-R1 inject、E-A5 reuse、Critic oracle |
| Separation from E-A5? | 不同 observation_point / 信封 / 声称 / 停点 |
| B1/B2 cleared this window? | **No** — 仅定义；实现另窗 |
