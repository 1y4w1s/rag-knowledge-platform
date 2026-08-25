# 01 — Analysis：PROVEN / UNKNOWN / FUTURE EXPERIMENT

> 三节互斥。PROVEN 不得写「大概也说明生成不错」。UNKNOWN 不得写成「未实现所以失败」。FUTURE EXPERIMENT **本窗不跑**。

---

## PROVEN

下列声称已有冻结工件、协议或现网代码路径支撑，**仅在该路径语义内**成立。

### P1 — Direction A 已选定；隔离是 plan-front / system-owned L0

- **Claim:** 下一阶段 Agent 演化里，scope/provenance 由 plan 准入保证，Critic advisory，不把 Critic 当隔离主人。
- **Evidence:** [`../project-boundary/w10-scope-ownership-decision.md`](../project-boundary/w10-scope-ownership-decision.md)；[`../resource-constrained-agent-runtime/capability-ownership.md`](../resource-constrained-agent-runtime/capability-ownership.md)「Scope isolation = system-owned L0」。

### P2 — E-A1～E-A4 把「测什么 / 谁跑 / 能喊什么」钉死在 plan-construction

- **Claim:** 资格协议、适配器、就绪评审、正式窗契约均绑定观察点 **plan-construction citations**，允许声称字符串仅为 `plan-construction citation scope compliance`。
- **Evidence:**
  - E-A1 [`../w10-ea1-scope-eligibility/README.md`](../w10-ea1-scope-eligibility/README.md) · [`04-scoring-contract.md`](../w10-ea1-scope-eligibility/04-scoring-contract.md)
  - E-A3 [`../w10-ea3-measurement-readiness-review.md`](../w10-ea3-measurement-readiness-review.md) CONDITIONAL GO（窄窗、零 LLM）
  - E-A4 [`../w10-ea4-formal-window-contract/02-non-claims-and-scope.md`](../w10-ea4-formal-window-contract/02-non-claims-and-scope.md) · `01-frozen-contract.md` `allowed` const

### P3 — E-A5 正式跑过窄窗；测量有效且观察点诚实

- **Claim:** reserved 结果 `artifact_kind=FORMAL_RUN_RESULT`，`measurement_valid=true`，`observation_point=plan_construction_citations`，`observation_point_honest=true`。
- **Evidence:** `backend/tests/fixtures/l4_critic/w10-ea4-formal-window-result.json`（`run_id=w10-ea5-formal-20260824T135530Z-ef7170ae397c`）；执行测试 `backend/tests/test_w10_ea5_formal_window_execution.py`。

### P4 — 分母 11；C12 不进分母；P2-R1 仍 BLOCKED

- **Claim:** `product_path_eligible=11`，`invalid_for_product_path=1`（`C12-out-of-scope-provenance`），`c12_in_denominator=false`，`p2_r1_status=BLOCKED`，`does_not_unblock_p2_r1=true`。
- **Evidence:** 同上 JSON `eligibility_summary` · `measurement_claims.forbidden_rejected` · `notes`。

### P5 — Eligible 11 案在 **plan-construction** 上 citation scope 全过

- **Claim:** C01–C11 均 `in_pass_rate_denominator=true`、`scope_compliance_pass=true`、`scorer_observation_point=plan_construction_citations`、`executor_path=agent_tool_scope+prepare_agent_generation`；scorer 未用 body-diff（`body_diff_used_for_safety=false`）。
- **Claim 的精确外延:** 被打分的列表来自 **`AgentGenerationPlan.citations`**（gate 后、生成前），不是 `state["citations"]`。
- **Evidence:** 同 JSON `per_case_result`；E-A2 `backend/tests/w10_ea2_scope_eligibility.py` `artifact_from_execution` 使用 `execution.gen_plan.citations`；E-A3 §3.2 已 **PROVEN**「Default scored list = gen_plan.citations」。

### P6 — 该 11 案在 L0 观察点上 **没有** plan-level 拒答

- **Claim:** C01–C11 `plan_refusal=false`（有 gated chunks / 非空 plan citations）。含名称带 refusal 的 **C07-correct-insufficiency-refusal**。
- **Evidence:** 同 JSON 各案 `plan_refusal`。这 **证明**「L0 门未把这些 case 判成空证据拒答」，**不证明**生成相应拒或应答（见 UNKNOWN U4）。

### P7 — Hit@3 golden 证明的是检索排序，不是生成

- **Claim:** `backend/tests/test_retrieval_golden.py` 是 Plan-RAG R5-2 **检索** Hit@3 门禁（mock 嵌入、禁用 query expand）；AGENTS / TECH 将其标为动检索/入库/切片的 CI gate（11/11）。
- **Evidence:** 该文件模块 docstring 与 `_mock_embedding`；E-A1 [`03-oracle-mapping.md`](../w10-ea1-scope-eligibility/03-oracle-mapping.md)：**Golden / Hit@3 不是 C12 对等案**，不进入 W10 产品路径分母。

### P8 — 现网「引用如何挂到回答上」的**机制**（非质量）

只证明代码做了什么，不证明答得对。

| 步骤 | 行为 | Evidence |
|---|---|---|
| Gate | `gate_agent_chunks`：相关度过滤后为每条 gated chunk 造 citation；无 gated → `refusal=True` | `backend/app/services/agent/finalize.py` |
| 流式候选 | thorough 生成相可在 token 前发 `citation` SSE（候选） | `backend/app/services/agent/stream.py`；TECH §5.12 |
| 生成后对齐 | 解析正文 `[片段N]`，按 similarity 升序映射下标，裁剪终态列表 | `citation_align.py` `align_citations_to_answer` |
| 漏标 | **无任何合法标记 → keep-all**（保留 gate 全表） | 同文件 docstring；TECH §5.12.1 |
| 对齐不检 KB | `align_citations_to_answer` **不**接收 `AgentToolScope`，只按标记裁剪 | E-A1 `04`「与现网代码的差距」；`citation_align.py` 签名 |
| 拒答清空 | critic fail-closed 等路径可把正文换成 `no_context_reply_for` 且 `citations=[]` | `stream.py`；`generation.py` `no_context_reply_for` |

### P9 — PRD P0 要的是「带引用的对话 + 无依据拒答」，L0 窗没有测这两条的**生成实现**

- **Claim:** 产品底线写在 PRD，不等于已被 E-A5 验证。
- **Evidence:** [`docs/PRD.md`](../../PRD.md) §2.1；AGENTS.md P0。E-A5 `measurement_claims.asserted` 不含这两条。

---

## UNKNOWN

L0 成功**覆盖不了**下列问题。每条写清缺口。

### U1 — 生成终态 citation 是否仍 ⊆ allowed / gated

- **Why L0 misses it:** E-A5 观察点是 `plan_construction_citations`。E-A1 `04` 把 **final citation** 定义为生成相结束后 `state["citations"]`（经 `align_citations_to_answer`）。E-A3 §3.2：**NOT SOLVED** 若把 `gen_plan.citations` 假装成 post-generate 终态。对齐可能缩小列表（有标记）或 keep-all（无标记），与 plan 快照不必相等。
- **Also unknown:** revise / critic 路径后 citations 是否与 SSE `done` / 落库一致（E-A1 `04` 要求三者同一对象；E-A5 未跑 `_stream_generation_phase`）。

### U2 — 无依据断言（unsupported claims）

- **Why L0 misses it:** E-A2 `unsupported_final_citation_count` 计的是 **缺 `chunk_id` 的 citation 形状**（E-A1 S3 / F2），**不是**「正文命题是否被 gated excerpt 支持」。冻结套件里 C03 名称含 unsupported，但 L0 只证明其 **plan 引用** scope-safe，未读生成正文。
- **Hit@3 也盖不住：** 相关文档进 Top-3 ≠ 模型没编造额外事实。

### U3 — 引用保全（citation preservation）

- **Why L0 misses it:** L0 不生成，故无「模型是否输出 `[片段N]`」「对齐后列表相对 plan 是收缩、keep-all 还是错位」。
- **机制风险（质量未知）:** keep-all 会让「没标引用的胡编正文」仍然带着满表 citation chips——产品看起来像 P0 合规，测量若只看列表非空会 **假绿**。有标记时对齐不检查 excerpt 是否真被句子使用（只检查下标合法）。

### U4 — 答案接地（answer grounding）

- **Why L0 misses it:** 无 `assistant_content`。Capability-ownership：Generation = model-owned L1；L0 只决定是否允许 generate、prompt 是否只含 gated chunks。E-A5 未调用 chat LLM。
- **C07 反例:** 案名是 insufficiency **refusal**，L0 记录 `plan_refusal=false` + scope PASS → 说明该案在 **gate 后仍有证据可生成**；是否应拒、生成是否过断言，完全未测。

### U5 — 拒答行为（refusal）

- **Why L0 misses it:** 冻结 12 里 **没有**「eligible ∧ 空 gated」拒答通道案（E-A3：both-empty 协议允许但套件无此案）。C01–C11 全部 `plan_refusal=false`。空检索拒答闸（`gate_agent_chunks` → `refusal=not gated`；PRD 固定话术）是 **L0 产品路径上的代码**，但 E-A5 **未用空检索 fixture 打分**。
- **Unknown:** 有依据时是否误拒；无依据时是否仍生成；fail-closed / low-confidence disclaimer 与「未找到」是否被用户/评测混淆（TECH §5.11 vs §5.12）。

### U6 — 语义 Critic / eval-L1 质量

- **Why L0 misses it:** E-A4/E-A5 禁止声称 Critic oracle capability。P3-R1 本地语义 Critic 7/7 TIMEOUT 是 **另一条评测 L1**，与本 L0 窗无关，也 **不**构成生成质量基线。

### U7 — Direction B / H2 生产可达性

- **Why L0 misses it:** 窄窗不跑污染 plan 探针（E-A3 T7）。Decision 的 DiD E-B0/E-B1 **仍 UNKNOWN/SPECULATIVE**。本章程 **不**把它们升级为下一窗。

### U8 — 真工具链 vs 同构 steps

- **Why L0 misses it:** E-A2/E-A5 用 fixture-synthesized steps → `prepare_agent_generation`，不是 live `run_react_loop`（E-A3 REMAINING）。L0 声称不得写成「thorough 线上检索+生成已测」。

---

## FUTURE EXPERIMENT

**全部未授权执行。** 下表只界定「若将来开测量窗，该量什么」。本窗与推荐的 E-B1 **都不跑**模型、都不写正式 generation 结果文件。

### FE-0 — 先冻结观察点（推荐为 E-B1，仍零 LLM）

| | |
|---|---|
| **将测量（契约层）** | 生成相结束后的 `state["citations"]` / `done.citations` 是否为计分对象；与 `gen_plan.citations` 的差是否被记录；四靶的**定义**（分子分母、空列表、keep-all） |
| **将不测量** | 任何模型输出质量；P2-R1；C12 产品 FAIL；Hit@3 |
| **依赖** | E-A1 `04` 终态定义；E-A4 信封风格（新 `protocol_version` 或新 schema，**禁止**覆盖 `w10-ea4-formal-window-result.json` 的 allowed claim） |
| **禁止** | 换模型当自变量；把 mock token 绿当成 grounding PASS |

### FE-1 — Citation preservation（有生成，仍可先 mock token）

| | |
|---|---|
| **将测量** | 给定固定 `gated_chunks`：对齐后 citation id 集合 vs plan 集合（shrink / keep-all / 非法下标丢弃）；是否出现「正文无标记但仍满表引用」 |
| **将不测量** | 命题是否被 excerpt 蕴含；检索 Hit@k |
| **依赖** | 可复现的 `assistant_content` fixture（含：有 `[片段N]`、无标记、错号、仅 disclaimer）；**禁止**用冻结 12 的 critic oracle 当生成金标 |
| **禁止** | 为刷保全率关掉 `align_citations_to_answer`；模型 A vs B 对比 |

### FE-2 — Unsupported claims / answer grounding（需要正文金标）

| | |
|---|---|
| **将测量** | 人工或冻结的 claim 列表：supported / unsupported / unverifiable；接地：答案关键命题是否可在 gated excerpt 中定位 |
| **将不测量** | 文笔、完整度、多跳推理「好不好」；Critic action oracle（C01–C11 expected_action）除非另开 CP 窗 |
| **依赖** | **新**生成金标（W9 critic 12 是 claim-status/Critic 动作套件，L0 已证明它们在 plan 层几乎都有证据，不能当「应拒」金标）。可选：先协议后抽样，**另窗**才允许真实 chat provider |
| **禁止** | 用 Hit@3 或 E-A5 11/11 外推 faithfulness；换 embedding/chat 模型当本实验自变量 |

### FE-3 — Refusal behavior

| | |
|---|---|
| **将测量** | eligible 空 gated → 是否固定拒答且 citations 空；有 gated 时是否仍走 `no_context_reply_for`（误拒）；low vs refuse 话术是否串档 |
| **将不测量** | 「拒答率越低越好」（TECH 拒答是可观测告警，不是质量 KPI）；C12 INVALID 贴 SCOPE_VIOLATION PASS（E-A1 F8） |
| **依赖** | 至少一条 **eligible 空检索** fixture（当前冻结 12 **没有**）；与 C07 批评性金标分离 |
| **禁止** | 把 L0 `plan_refusal=false` 解释成「拒答功能坏了」或「拒答功能好了」 |

### FE-4 — 显式排除（不要开成「生成边界」的第一窗）

- 覆盖 `w10-ea4-formal-window-result.json` 或把 `generation-final safety` 写进该文件 `asserted`
- Decision DiD E-B1 污染 `gated_chunks` 探针（B 轨残差）
- 同步本地语义 Critic ≤60 s、Critic 生产默认 ON
- remaining-plan「W10 Multimodal Vertical Slice」
- P2-R1 解阻 / 12/12 产品 PASS
