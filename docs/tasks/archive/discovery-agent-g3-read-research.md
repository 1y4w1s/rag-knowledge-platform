# G-3 · 只读 RAG Agent · Research

> **状态**：✅ **R 关**（2026-07-09）→ **L ✅** `discovery-agent-g3-read-plan.md` → 下一窗 **I** `G3-0.1`  
> **依据**：`discovery-agent-platform-plan.md` §0.3/§2/§5 · `preview-agent-platform.html` **v4.1**（V2 冻结）· HA **1-A / 2-A / 3-C / 4-A**  
> **边界**：**只调研** · **不写** Implement 代码 · **不**改现网 `stream_workspace_chat_events` 行为（快速模式复用）

---

## §1 三句话摘要（门禁用）

1. **触发点**：用户在 `/ask` 或库内 chat 手动切 **快速 / 精准**（HA-4-A）；发 `POST .../threads/{id}/chat` 时 body 带 `mode`（工程名 `fast|thorough`，UI 文案见 plan §5.1）。**快速** = 现网 G1 单次 `retrieve_*`；**精准** = 服务端 ReAct 循环，最多 **5 步只读 tool**，UI 展示 Tool 时间线。  
2. **数据流**：解析 workspace + OrgScope →（精准）`agent/runtime` 调 tool 包装层 → 每步 `tool_start`/`tool_result` SSE → 汇总 chunk → gate → **citation 仍严格先于 token**（R4-4）→ `done` 落库；`agent_runs`/`agent_steps` 记元数据，**审计不写用户原文**（H2-1-A）。  
3. **怎么验**：本 R 窗交付 **§2 对照表 + §3 SSE 映射 + §4 乱操作**；L 窗拆原子任务；Implement 后 `test_agent_*.py` + `golden_agent_qa.json` ≥15 题 · 动 `retrieve_*` 仍须 golden 12/12。

---

## §2 只读 Tool 对照表（SSOT · Implement 前必对）

### §2.1 总览：G3 五 tool × 现网 × EagleRAG（R6-7）

| G3 Tool | 类型 | 预览 v4.1 | Plan §2.3 | EagleRAG MCP（借鉴形状） | 知岸现网能力 | G3 实现策略 |
|---------|------|-----------|-----------|--------------------------|--------------|-------------|
| `list_knowledge_bases` | 读 | ✅ 时间线第 1 步 | ✅ | 无同名 · 近似「列库」 | `GET /knowledge-bases` · `listing.list_knowledge_bases` + OrgScope | **包装列表服务** · 返回摘要字段 · 不信模型传的 org/workspace |
| `semantic_search` | 读 | ✅ | ✅ | `query` / `retrieve_text` | `retrieve_workspace_chunks` · `retrieve_chunks` | **包装检索** · 工作区/库内两路径 · `kb_ids` 与 `visible_kb_ids` **求交** |
| `search_documents` | 读 | ✅ | ✅ | 文件名/元数据检索侧面 | `GET /search/documents` · `search_documents_by_filename` / `_by_content` | **包装跨库搜** · 默认 `mode=filename` · 正文搜走 `content` |
| `get_chunk_excerpt` | 读 | ✅ | ✅ | `retrieve_text`（按 chunk） | `DocumentChunk` + `require_kb_access` · `_excerpt()` | **按 chunk_id 读库** · 校验 chunk.kb_id ∈ visible |
| `get_document_metadata` | 读 | ❌ 预览未演示 | ✅ Plan 有 | ingest 元数据读侧面 | `GET .../documents/{doc_id}` · `listing.get_document` | **L 窗拍板是否首版必做** · 建议 G3-1 与 `get_chunk_excerpt` 同波 |

**明确不做（G3 范围外）**：`retrieve_visual`（EagleRAG 视觉路）· 一切写 tool（G4）· 联网搜索 · G7 Webhook。

### §2.2 逐 Tool 契约（OpenAPI 草案级 · 供 L/TECH-7）

#### `list_knowledge_bases`

| 项 | 内容 |
|----|------|
| **人话** | Agent 先看「我能搜哪些库」，避免瞎猜库名。 |
| **入参（模型 → 服务端）** | `{ "q": string?, "limit": int? }` · 默认 `limit=24` · **无** `workspace`/`department_id`（从请求上下文注入） |
| **出参（tool_result 摘要）** | `{ "items": [{ "kb_id", "name", "document_count", "updated_at" }], "total", "scope_label" }` |
| **现网映射** | `backend/app/services/knowledge_base/listing.py` → `list_knowledge_bases(db, scope, org_scope, ...)` |
| **权限** | 与 `GET /knowledge-bases` 相同 · `WorkspaceScope` + `OrgScope.visible_kb_ids` |
| **安全** | 忽略模型传的 `owner_org_id` / 任意 UUID · 仅以 JWT + query `workspace`/`department_id` 解析 scope |

#### `semantic_search`

| 项 | 内容 |
|----|------|
| **人话** | 跨库（或指定库）语义+关键词 hybrid 检索，和现网对话底层同一路。 |
| **入参** | `{ "query": string, "kb_ids": uuid[]?, "top_k": int? }` · `top_k` 默认 5 · 上限 5 |
| **出参** | `{ "hits": [{ "chunk_id", "kb_id", "kb_name", "doc_name", "page", "section_title", "excerpt", "score" }], "retrieval_ms" }` |
| **现网映射（工作区）** | `retrieve_workspace_chunks` — 向量 Top-20 + FTS Top-20 → RRF → rerank → diversity → Top-K |
| **现网映射（库内）** | `retrieve_chunks(kb_id=validated_kb, visible_kb_ids=...)` — 单库 SQL |
| **权限** | `kb_ids` 非空时 **`frozenset(kb_ids) ∩ visible_kb_ids`**；空则搜全部 visible |
| **与快速模式关系** | **快速模式 = 本 tool 隐式调用 1 次**（不暴露 tool SSE） |

#### `search_documents`

| 项 | 内容 |
|----|------|
| **人话** | 按文件名（或正文）找文档，适合「知道文件名不知道在哪个库」。 |
| **入参** | `{ "query": string, "mode": "filename" \| "content", "limit": int? }` · `query` 1～200 字 |
| **出参** | `{ "items": [{ "document_id", "kb_id", "kb_name", "filename", "snippet?" }], "total" }` |
| **现网映射** | `GET /api/v1/search/documents` → `search.py` · `validate_search_query` |
| **权限** | 同 EW-E1/R1-2 · `kb_scope_clause(scope, org_scope)` |
| **与 semantic_search 分工** | 文件名/清单类 → 本 tool；语义问答类 → `semantic_search` |

#### `get_chunk_excerpt`

| 项 | 内容 |
|----|------|
| **人话** | 精准模式第 N 步「展开某条命中」给模型读全文摘录。 |
| **入参** | `{ "chunk_id": uuid }` |
| **出参** | 与 `CitationPayload` 对齐：`chunk_id, document_id, doc_name, page, section_title, excerpt` + `kb_id, kb_name` |
| **现网映射** | `DocumentChunk` 查询 + `require_kb_access(kb_id, read)` · excerpt 用 `retrieval._excerpt` |
| **权限** | chunk 所属 `kb_id` 必须在 visible；否则 tool_result `error: "forbidden"` **不** 抛 500 |

#### `get_document_metadata`（首版可选 · L 窗确认）

| 项 | 内容 |
|----|------|
| **人话** | 查文档状态（整理中/失败）、上传时间，避免对未完成文档作答。 |
| **入参** | `{ "kb_id": uuid, "document_id": uuid }` |
| **出参** | `{ "filename", "status", "file_type", "chunk_count", "uploaded_at" }` |
| **现网映射** | `documents/listing.get_document` |
| **权限** | `require_kb_access` read |

### §2.3 EagleRAG 四 tool 形状对照（R6-7 · 只借接口语义）

| EagleRAG MCP | 知岸 G3 对应 | 备注 |
|--------------|--------------|------|
| `query` | `semantic_search` + 最终 LLM 生成 | 知岸 **拆开**：检索 tool ≠ 生成答案 |
| `retrieve_text` | `semantic_search` + `get_chunk_excerpt` | 文本路 · pgvector+tsvector · **不** 引入 Milvus |
| `retrieve_visual` | — | **Defer** · F5/多模态单线 · G3 不做 |
| ingest / write 类 | — | **G4-min** · G3 只读 |

### §2.4 Tool 注册与包装层（Implement 方向 · 本窗只定边界）

```
POST .../chat (mode=thorough)
  → services/agent/runtime.py
      → for step in 1..MAX_STEPS:
            LLM 选 tool + args
            → services/agent/tools/<name>.py
                → 校验 scope · 调现网 service（§2.2 映射）
            → yield tool_start / tool_result
      → 合并 hits → filter_relevant_chunks → stream 答案
```

| 规则 | 说明 |
|------|------|
| **不信模型 kb_id** | 所有 tool 的 `kb_id`/`kb_ids` 与 `visible_kb_ids` 求交（plan §2.3） |
| **步数上限** | 精准 **5** · 快速 **1**（预览 `MODES.*.maxSteps`） |
| **单文件** | 每 tool ≤200 行 · `runtime.py` ≤300 行（plan §2.1） |
| **golden 隔离** | tool 包装 **只调** 现有 `retrieve_*` · 不改 RRF/rerank 参数 · golden 12/12 仍挡 CI |

---

## §3 SSE 事件映射

### §3.1 现网事件（G1/G2 · 保持不变）

| 事件 | `data` 形状 | 顺序约束 | 前端解析 | 落库 |
|------|-------------|----------|----------|------|
| `citation` | `CitationPayload`（库内含六字段；工作区 +`kb_id`/`kb_name`） | **全部 citation 在任意 token 之前**（R4-4） | `thread-api.ts` / `chat-api.ts` → `onCitation` | `chat_messages.citations` JSON |
| `token` | `{ "text": string }` | citation 之后 · 多条 | `onToken` | 拼入 assistant `content` |
| `done` | `{ "message_id", "citations" }` | 流末尾 | `onDone` | — |

**帧格式**（`chat.py` `_sse_event`）：`event: …\ndata: {json}\n\n` · pytest `test_r4_4_streaming.py` 校验。

### §3.2 G3 新增事件（仅 `mode=thorough`）

| 事件 | `data` 形状（草案） | 何时发 | UI（预览 v4.1） | 落库 |
|------|---------------------|--------|-----------------|------|
| `tool_start` | `{ "step": int, "tool": string, "args_summary": string }` | 每步 tool 执行前 | Tool 时间线新增一行 · 转圈/序号 | `agent_steps`：`tool_name`, `args_json`, `status=running` |
| `tool_result` | `{ "step", "tool", "ok": bool, "summary": string, "latency_ms": int, "capped"?: bool }` | 每步结束后 | 折叠条展示摘要 · 失败显红 | `agent_steps.result_summary`, `latency_ms` |
| `agent_budget` | `{ "steps_used": int, "max_steps": int, "capped": bool }` | 触顶或每步后（二选一 · L 窗定） | `budget-chip` 变 warn · 「已达 5 步上限」 | `agent_runs.steps_used` |

**不发（G3）**：`approval_required` / `approval_resolved` / `document_status` → **G4-min**。

### §3.3 按模式的事件序列

#### 快速（`mode=fast` · 用户见「快速」）

与现网 **字节级兼容**（推荐 L 窗采纳）：

```
（无 tool_*）
→ citation × N
→ token × M
→ done
```

实现：`mode=fast` 时直接 `stream_workspace_chat_events` / `stream_chat_events` · **不** 创建 `agent_run`。

#### 精准（`mode=thorough` · 用户见「精准」）

```
→ (tool_start → tool_result) × 1..5
→ [agent_budget capped=true]  （可选 · 第 5 步后）
→ citation × N
→ token × M
→ done { message_id, citations, agent_run_id? }
```

**顺序硬约束**：

1. 所有 `tool_*` 在 **第一条 `citation` 之前**（用户先看到过程再看到引用块）。  
2. `citation` 仍在 **第一条 `token` 之前**（继承 R4-4）。  
3. `done` 最后 · 含与流中一致的 `citations` 快照。

### §3.4 请求 / 响应入口映射

| 场景 | HTTP | Body 增量 | SSE 生产者 |
|------|------|-----------|------------|
| 工作区 + thread | `POST /api/v1/ask/threads/{id}/chat` | `{ "message", "mode"?: "fast"\|"thorough" }` · 默认 `fast` | `stream_workspace_chat_events` 或 `stream_agent_workspace_events` |
| 库内 + thread | `POST /api/v1/knowledge-bases/{kb_id}/threads/{id}/chat` | 同上 | `stream_chat_events` 或 `stream_agent_kb_events` |
| Legacy | `POST /api/v1/ask/chat` | 同上 · 无 thread | 建议 **deprecated** · G3 以 thread 路径为准 |

**Query 不变**：`workspace` · `department_id`（与 G2 一致）。

### §3.5 前端处理器映射（Implement 清单）

| 事件 | 新增/改 | 组件 |
|------|---------|------|
| `tool_start` / `tool_result` / `agent_budget` | 新增 handler | `ToolTimeline.tsx`（对标预览 `trace-panel`） |
| `citation` / `token` / `done` | 复用 | `use-thread-session.ts` · 扩展 `ChatStreamHandlers` |
| 模式切换 | 新增 | `AgentModeSwitcher` · prop `fast\|thorough` · UI 文案「快速/精准」 |
| 历史回放 | 待定 H6 | GET messages **是否** 带 `tool_trace` JSON · 预览静态 · L 窗拍板 |

---

## §4 乱操作边界（S/E · G3 验收 SSOT）

> 继承 G2 `G2_THREADS_ACCEPTANCE.md` · G1 `G1_ASK_ACCEPTANCE.md` · 预览 v4.1 试玩轨 **E** · **只读 Agent 不加写能力**。

### §4.1 预览 v4.1 已冻结 E → 系统行为

| ID | 用户操作 | 期望行为 | API/实现要点 | pytest 方向 |
|----|----------|----------|--------------|-------------|
| **E1** | 删除会话 | 列表移除 · 无法再选中 | `DELETE /ask/threads/{id}` → archived · 再 chat → **404** | 复用 G2 E2 |
| **E6** | 切部门 | toast「已切换部门…」· thread 列表按 scope 过滤 | 前端 `departmentGeneration` · 列表 refetch | 复用 ORG-3.4 |
| **E14** | 源文档/grant 失效 | 历史 chip **灰态** · 不可点预览 | `source_status: source_inaccessible` | 复用 G1 E14 |
| **E-budget** | 精准模式连问复杂题 | **5 步后停止扩检索** · 基于已有片段作答 · budget-chip warn | `agent_budget.capped=true` · runtime 不再调新 tool | **新** `test_agent_budget_cap` |
| **E-M** | Member 点「编辑」 | 灰钮 · 无交互（G4 愿景） | `mode=edit` **拒绝** · 400 或前端 disabled | 首版仅 UI 占位 |
| **E-empty** | 空消息发送 | 发送钮 disabled · 不 POST | `ChatRequest` min_length=1 → **422** | 复用 schema |

### §4.2 G3 新增边界（R 窗定义 · L 窗转用例）

| ID | 场景 | 期望 | 默认拍板 |
|----|------|------|----------|
| **G3-E1** | 精准模式中 **切换快速/精准**（发送中） | 当前流 **Abort** · 不双开 SSE · 输入框恢复 | 前端 `AbortController` · 与现网停止生成同构 |
| **G3-E2** | 模型 tool args 传 **越权 kb_id** | tool_result `ok=false` · summary「无权限」· **不** 500 | `visible_kb_ids` 求交 · audit 记 `agent.tool_denied` |
| **G3-E3** | 精准模式 **无可见库** | **400** `无可用资料库` · 不开 Agent | 复用 `assert_has_visible_knowledge_bases` |
| **G3-E4** | 精准模式 **30/h 限流** | 第 31 次 **429** · 与快速共用 `ApiRateLimitKind.chat` | **1 次用户发送 = 1 次 chat 计数**（HA-1-A · 防多步打满） |
| **G3-E5** | 快速模式问法 | **无** tool 时间线 · 1 步等价 | `mode=fast` 无 `tool_*` 事件 |
| **G3-E6** | 精准 **全步无命中** | 走 R4-2 **拒答话术** · **无** citation | 与现网 AC-4 一致 |
| **G3-E7** | 连点发送 / 并行 POST 同 thread | 第二次 **409 或** 忽略（L 窗二选一） | 建议 **409「上一条仍在生成」** |
| **G3-E8** | 硬闯 `mode=edit` / `mode=thorough` + member 写意图 | 只读 tool **永不** 调 G4 写接口 | runtime 白名单仅 §2.1 五 tool |
| **G3-E9** | 库内精准模式 | tool 时间线同显 · `semantic_search` 默认 **当前 kb** | `kb_id` 来自路径 · 仍过 `visible_kb_ids` |
| **G3-E10** | Admin **不看** 他人 agent 正文 | 无新 API 泄露 · audit 仅 metadata | 继承 H2-1-A · `agent_runs` 按 `user_id` 过滤 |

### §4.3 继承不变式（Implement 不得破坏）

| 来源 | 规则 |
|------|------|
| 北极星 | 有依据 **必须** citation · 无依据 **必须** 拒答 |
| OrgScope | 检索/tool 结果 **不得** 含不可见库 chunk |
| M5 限流 | chat 30/h · 精准 **不** 按步数倍乘 |
| R4-4 | citation 先于 token |
| HA-4-A | **不** 自动升精准 · 意图识别进 backlog |
| HA-2-A | Member **无** 采纳/写库（G4 前仅 UI 灰钮） |

---

## §5 待 L 窗拍板假设（含后果白话）

| 假设 | 选项 | 后果（白话） | R 窗建议 |
|------|------|--------------|----------|
| **H3-1** `get_document_metadata` 首版 | A 必做 / B 延后 | A：Agent 可跳过 processing 文档；B：少 1 tool · -preview 未演示 | **B 延后** · 与 v4.1 对齐 |
| **H3-2** 历史是否存 tool_trace | A 存入 message JSON / B 仅 `agent_steps` 表 | A：刷新可还原时间线；B：表归一 · GET messages 要 join | **B** · message 只存 citations+正文 |
| **H3-3** `agent_budget` 发帧时机 | A 仅触顶 / B 每步后发 | A：SSE 少；B：UI _meter 实时 | **B** · 对齐预览 meter |
| **H3-4** 并行发送 | A 409 / B 队列 | A：实现简单；B：体验好但复杂 | **A 409** |
| **H3-5** `mode` 传参位置 | A body / B query | A：与 message 同体 · OpenAPI 清晰 | **A body** · 默认 `fast` |
| **H3-6** golden_agent 题量 | A 15 / B 20 | A：plan 合同；B：答辩更厚 | **A 15** · 含多步+拒答+越权 3 类 |

---

## §6 R 关 DoD

| # | 条件 | 状态 |
|---|------|------|
| R1 | §2 只读 tool 对照表（含现网映射 + EagleRAG） | ✅ |
| R2 | §3 SSE 事件映射（快速/精准两路径） | ✅ |
| R3 | §4 乱操作边界（预览 E + G3-E） | ✅ |
| R4 | 不写 Implement 代码 | ✅ |
| R5 | cockpit + plan §7 同步 | ✅ 本窗 |

---

## §7 面试 30 秒（R 窗）

「G3 是在现有 G1 检索和 G2 thread 上加了 **手动两档**：快速还是一次检索；精准是最多 5 步 **只读 tool**，SSE 多 `tool_start/result`，但 **citation 仍然先于 token**。五个 tool 全是现网能力的包装——跨库检索、文件名搜、列库、读 chunk——模型传的 kb_id 我们会用 OrgScope 截断。乱操作重点：步数触顶、越权库、限流仍按 **一次对话** 算，不因为 Agent 多步就放大配额。」

---

## §8 下一窗交接词（L）

```
@rag-knowledge-platform/docs/tasks/discovery-agent-g3-read-research.md
@rag-knowledge-platform/docs/tasks/discovery-agent-platform-plan.md
@rag-knowledge-platform/docs/preview-agent-platform.html
@rag-knowledge-platform/docs/cockpit.html

【背景】G3 R ✅ · V v4.1 快速+精准 · HA 1-A/2-A/3-C/4-A

【要求】严格只做 L 窗 · 产出 discovery-agent-g3-read-plan.md 原子任务 · 不写 Implement

【验收】plan 含 G3-0～N 清单 · 每条对应 §2 tool / §3 SSE / §4 E 用例 · H3-1～H3-6 用户确认
```
