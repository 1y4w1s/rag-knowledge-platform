# 01 — Production path definition（产品路径）

> 记录**现网**链路，不是再设计。符号以当前 `backend/app` 为准；W9 分析文档里的别名见文末对照表。

## 范围

本协议的「产品路径」= 用户 thorough/精准对话请求进入 Agent 后，**证据必须经过真实 scope 与生产 plan construction**，再生成，再形成**终态 citation**。  
Critic 若开启，只建议、不执行（W9 P1 **PROVEN**：`_stream_generation_phase` 为 action owner）。

HTTP 快速模式（单次 `retrieve_*`、无 ReAct）**不是**本协议分母。本协议分母是 **Agent thorough** 控制面：tool scope → 检索步 → `prepare_agent_generation` → 生成相 → 终态 citation。

## 链（协议名义顺序 vs 现网真实顺序）

任务书名义链：

`request → AgentToolScope → plan construction → retrieval → generation → final citation scoring`

现网 **thorough** 真实顺序是检索步在 plan construction **之前**（plan 由成功 tool steps 重载，而不是先出 plan 再检索）：

`request → AgentToolScope → retrieval (scoped tools) → plan construction → generation → product final citations → (measurement) final citation scoring`

名义链把「scope 所有权」放在 plan-front：Direction A 的意思是 **非法证据不得成为 `AgentGenerationPlan` 的成员**。现网实现上，该不变量由 **tool 层 `AgentToolScope` + 只从成功 steps 构造 plan** 共同保证，而不是由 Critic 或 finalize 再授权来保证。

不得把名义顺序理解成「先 `gate_agent_chunks` 再 `semantic_search`」。测量入口必须复现**真实顺序**。

## 逐步：现网模块

### 0. Request

| 步骤 | 现网位置 |
|---|---|
| Thorough SSE 入口 | `backend/app/services/agent/stream.py`（thorough 核心流；分析文档曾标 `:1171` 一带） |
| 构造 `AgentToolScope` | `build_kb_tool_scope` / 工作区可见 KB 解析（TECH §7：`visible_kb_ids` 求交；不信模型传的 org/kb） |
| 注入每个 tool | `AgentToolScope` 作为运行时上下文传入 ReAct |

`visible_kb_ids is None` = 现网「不追加 KB WHERE、全部可见」语义。测量不得把 `None` 误当成空集全拒绝（那是 `frozenset()`）。

### 1. AgentToolScope

| 符号 | 文件 |
|---|---|
| `AgentToolScope` | `backend/app/services/agent/tools/scope.py` |
| `is_kb_visible` / `require_kb_visible` | 同文件 |
| `resolve_kb_ids` | 同文件（分析文档 `:93`；非空 requested 与 `visible_kb_ids` 求交，含越权 id → `ToolDenial`，summary「无权限」） |

隔离是 **Runtime L0 / system-owned**，不是 critic-class。越权在 tool 执行期 abort/deny，而不是生成后再靠模型「忘掉」foreign 片段。

### 2. Retrieval（scoped tools）

| 符号 | 文件 |
|---|---|
| `run_react_loop` | `backend/app/services/agent/runtime.py`（分析文档 `:1108`） |
| `semantic_search` + `resolve_kb_ids` | `backend/app/services/agent/tools/semantic_search.py`（分析文档 `:182`） |
| 其它只读命中 | `get_chunk_excerpt` / `grep_in_document` / `compare_chunks`（finalize 合并时收录） |

失败或 deny 的 step **不得**把 forbidden KB chunk 写进后续 plan。H4（bounded recovery 本身越权）在 P2-R1 复核中为 **REJECTED**：探针里新命中属于 allowed KB。

### 3. Plan construction（Direction A 前置不变量）

| 符号 | 文件 |
|---|---|
| `prepare_agent_generation` | `backend/app/services/agent/finalize.py`（分析文档 `:146`） |
| `_collect_hit_scores` / `merge_step_hits_to_chunks` / `_load_retrieved_chunks` | 同文件 `:49` / `:114` |
| `gate_agent_chunks` | 同文件 `:123`（relevance / diversity / citation 形状；**不**接收 `AgentToolScope`，**不**做 KB 再授权） |
| `AgentGenerationPlan` | `gated_chunks` + `citations` + `refusal` |

生产构造规则（资格相关）：

1. 只从 **成功** 的只读 tool steps 汇总 `chunk_id → score`。
2. 从 DB 重载 `RetrievedChunk`（`doc.kb_id == chunk.kb_id` 不一致则丢弃）。
3. `gate_agent_chunks` 做相关度门，不重新执行 `AgentToolScope`。

因此 Direction A 的隔离不变量是：**进入 `prepare_agent_generation` 的 steps 必须已经是 scope-legal**。若 harness 在其后把 foreign chunk 写入 `gated_chunks`，测的就不是产品路径。

Thorough 流在 ReAct 结束后调用：

```text
outcome = await run_react_loop(..., tool_scope=...)
gen_plan = await prepare_agent_generation(db, query=..., steps=outcome.steps, ...)
async for event in _stream_generation_phase(..., gen_plan=..., tool_scope=...)
```

（`stream.py` 约 `:1190` / `:1221`；编辑模式约 `:1523` 再次 `prepare_agent_generation`。）

### 4. Generation

| 符号 | 文件 |
|---|---|
| `_stream_generation_phase` | `backend/app/services/agent/stream.py` `:280` |
| `_maybe_critic_retrieve_and_revise` | 同文件 `:822` |
| recovery merge | 同文件约 `:910`：`combined` 先装入旧 `active_plan.gated_chunks`，再追加 recovery 命中 |

W9 P1：**Critic advisory**；本相仍是唯一 action/recommendation owner。  
H2（merge 不按 scope 过滤旧 chunks）只在 **非法内部 plan** 下被探针打到，**不是**本协议的产品路径分母。E-B0/E-B1 另议。

### 5. Product final citations（产品终态，测量前）

| 符号 | 文件 |
|---|---|
| `align_citations_to_answer` | `backend/app/services/rag/citation_align.py` |
| 生成相内对齐 | `stream.py` 约 `:789`：对 **gated_chunks** 按正文 `[片段N]` 裁剪后写入 `state["citations"]` |
| `chunk_to_citation` / `workspace_chunk_to_citation` | `backend/app/services/rag/retrieval.py`（finalize gate 也用） |

产品「最终 citation」= **done / 落库 / `state["citations"]` 对齐后的列表**，不是 SSE 先发的候选 citation 流，也不是 Critic 入参 `chunks`。

`gate_agent_chunks` **不做** scope 再授权。因此测量 scorer 必须在终态 citation 上检查 ⊆ allowed scope（见 `04`）。这是 **测量契约**，不是声称现网 finalize 已实现 isolation-class 终态闸门。

### 6. Measurement final citation scoring（仅评测，非产品）

后续 I 的 scorer 消费步骤 5 的终态列表，检查 ⊆ allowed scope。  
现成探索：`backend/tests/w9_critic_p2_r2_protocol.py` · `score_final_output`。P2-R1 provisional scorer **只比正文是否变化** → evaluator false pass（**PROVEN**）。不得再用于产品分母。

## 对照：P2-R1 harness 路径（非法分母）

| 步骤 | `backend/tests/w9_critic_p2_r1_harness.py` |
|---|---|
| 冻结 evidence → `RetrievedChunk` | `_chunk` / `execute_frozen_case` 约 `:125` |
| 直调内部 `_stream_generation_phase` | 约 `:237`–`:264` |
| foreign chunk 写入 `gen_plan.gated_chunks` | `SimpleNamespace(..., gated_chunks=initial_chunks)` |
| mock tool | `tool_scope=MagicMock()`；`runtime._execute_step` mock |

P2-R2 将此路径改名为 **DEFENSE_IN_DEPTH_PROBE**，明确不得进入产品分母。E-A1 采纳该分离。

## 符号对照（文档漂移）

W9/W10 研究文与测试草稿对同一模块有过命名漂移。后续 I **以 `backend/app` 现网符号为准**，不要按别名改产品 API。

| 本协议（与 W10 Decision / 用户任务一致） | 现网常见符号 |
|---|---|
| `AgentToolScope` | `AgentToolScope`（`tools/scope.py`） |
| `prepare_agent_generation` | `prepare_agent_generation` |
| `_stream_generation_phase` | `_stream_generation_phase` |
| `run_react_loop` | `run_react_loop` |
| `resolve_kb_ids` | `resolve_kb_ids` |
| C12 / `C12-out-of-scope-provenance` | 冻结 `case_id` 以 fixture 为准 |

## 本文件不声称

- 不声称产品路径「已经」在 finalize 做 scope 再授权。
- 不声称 C12 在真实入口可复现 isolation bug。
- 不授权为了让 C12 可跑而去改 `gate_agent_chunks` 签名。
