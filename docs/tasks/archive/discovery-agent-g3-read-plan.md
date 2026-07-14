# G-3 · 只读 RAG Agent · Plan

> **状态**：✅ **L 关**（2026-07-09）→ 下一窗 **I** 从 **G3-0.1** 起 · WIP=1  
> **依据**：`discovery-agent-g3-read-research.md`（R ✅）· `discovery-agent-platform-plan.md` §0.3/§2/§5 · `preview-agent-platform.html` **v4.1**（V2 冻结）· HA **1-A / 2-A / 3-C / 4-A**  
> **边界**：**只写 Plan** · **不写** Implement 代码 · **不**改现网 `stream_workspace_chat_events` / `stream_chat_events` 行为（`mode=fast` 复用）

---

## §0 问题陈述（G2 之上 · 用户要什么）

| 现象 | 根因 | 用户感受 |
|------|------|----------|
| 跨库复杂题一次检索不够 | G1 固定 **1 次** `retrieve_*` | 「它没查透就答了」 |
| 不知道 Agent 干了啥 | 无 tool 过程展示 | 「黑盒，不像企业 Agent」 |
| 预览 v4.1 已演示两档 | Implement 仍只有 G1 单路径 | 「快速/精准切换是假的」 |
| 简历要讲 Agent | 只有 RAG golden | 缺 **多步只读 + 评测集** 故事 |

**结论**：G1/G2 完成了「单次检索 + thread 历史」；**G3 = 在 thread 上叠加手动两档**：**快速**（现网）与 **精准**（最多 5 步只读 tool + 时间线），且 **citation 仍先于 token**（R4-4）。

---

## §1 企业级目标（TO-BE · 一句话）

> 用户在 `/ask` 与库内 chat 可 **手动切「快速 / 精准」**；**快速** = 现网单次检索、无时间线；**精准** = 最多 5 步只读 tool、SSE 展示过程、步数触顶仍基于已有片段作答；**有依据必 citation、无依据必拒答**；OrgScope 截断越权库；限流 **1 次发送 = 1 次 chat**（HA-1-A）。

### §1.1 与 G1/G2 / PRD / 预览对齐

| 文档 | G2 态 | G3 调整 |
|------|-------|---------|
| G1 检索 | 单次 retrieve → gate → SSE | **快速模式原样复用** |
| G2 thread | `POST .../threads/{id}/chat` | body 增 **`mode`** · 精准走 Agent 路径 |
| 预览 v4.1 | 快速/精准 + tool 时间线 | **Implement 对齐** S3～S5 · E-budget |
| TECH | 无 Agent 表 | **TECH-7**：`agent_runs` / `agent_steps` |
| HA-4-A | 手动切模式 | **不**自动升精准 |

---

## §2 产品范围 · 做 & 不做

| 做 | 不做 |
|----|------|
| **`mode=fast\|thorough`**（UI：**快速 / 精准**） | `get_document_metadata` tool（**H3-1-B** 延后） |
| 4 个首版只读 tool + `semantic_search` 等 **§2.1 四 tool**（见 R §2.1，不含 metadata） | G4 写 tool · `approval_*` · `document_status` |
| `tool_start` / `tool_result` / `agent_budget` SSE（仅 thorough） | 联网搜索 · G7 Webhook |
| `agent_runs` / `agent_steps` 落库 · audit 元数据 | audit / Admin **存用户问题全文** |
| 前端 `AgentModeSwitcher` + `ToolTimeline` + budget meter | 历史消息 **还原 tool 时间线**（**H3-2-B**） |
| `test_agent_*.py` + **`golden_agent_qa.json` ≥15 题** | 动 RRF/rerank 参数（golden 12/12 仍挡） |
| pytest 覆盖 G3-E1～E10 + 预览 E 继承 | Member **编辑/采纳**（G4 愿景 · UI 灰钮） |
| TECH-7 + PRD G-3 节 + `G3_AGENT_ACCEPTANCE.md` | 对话内多轮记忆（另立项） |

---

## §3 拍板记录（H3-1～H3-6 · ✅ L 窗确认 2026-07-09）

> 来源：`discovery-agent-g3-read-research.md` §5 · R 窗建议 · **L 窗全部采纳**（与 v4.1 预览一致）。

| 假设 | 选定 | 状态 | 后果（白话） |
|------|------|------|--------------|
| **H3-1** `get_document_metadata` 首版 | **B 延后** | ✅ | 首版 4 tool（非 5）· 与预览演示一致 · G4 前可补 |
| **H3-2** 历史是否存 tool_trace | **B 仅 `agent_steps` 表** | ✅ | 刷新后 **不**还原时间线 · message 只存 citations+正文 · 将来 P2 可 join |
| **H3-3** `agent_budget` 发帧时机 | **B 每步后发** | ✅ | SSE 略多 · budget-chip / meter **实时** · 对齐预览 |
| **H3-4** 并行发送同 thread | **A 409** | ✅ | 连点发送 →「上一条仍在生成」· 实现简单 |
| **H3-5** `mode` 传参位置 | **A body** · 默认 `fast` | ✅ | 与 `message` 同体 · OpenAPI 清晰 |
| **H3-6** golden_agent 题量 | **A 15 题** | ✅ | 含多步 + 拒答 + 越权 3 类 · 与 platform-plan §3 合同一致 |

<details><summary>若改选时的页面后果（归档）</summary>

| 假设 | 若改 A 的后果 |
|------|---------------|
| H3-1-A | 多 1 个 tool 文件 + 测试 · 预览未演示需补 V 或文档说明 |
| H3-2-A | GET messages 膨胀 · 前端历史需渲染 trace JSON |
| H3-3-A | budget-chip 仅触顶变红 · 中间步 UI 静态 |
| H3-4-B | 需队列/锁 · I 窗 +1～2 天 |
| H3-5-B | query 与 message 分离 · 易漏传 mode |
| H3-6-B | CI 略慢 · 答辩素材更厚 |

</details>

### §3.1 大白话（L 关出口）

**一句话**：对话页顶栏多一个 **快速 / 精准** 开关；默认 **快速**（和现在一样快）；切 **精准** 后 AI 最多 **查 5 步**（列库、语义搜、文件名搜、读片段），中间过程折叠展示；**引用 chip 仍然在文字前面**；步数满了就停查、用已有资料答；**不会**因为 Agent 多走几步就多扣 30 次/小时。

| 名词 | 人话 |
|------|------|
| 快速 | 搜一次、答一次 · **无** tool 时间线（工程 `mode=fast`） |
| 精准 | 最多 5 步只读查询 · 有 tool 时间线（工程 `mode=thorough`） |
| tool 时间线 | 精准模式下折叠条：「列库 → 跨库检索 → …」 |
| budget-chip | 「2/5 步」进度 · 满 5 步变红警告 |
| agent_run | 一次精准提问在库里的执行记录（Admin 也 **看不到** 你的问题原文） |

**你怎么验（最小集 · Implement 后）**

1. `/ask` 默认 **快速** · 问「年假」→ **无** 时间线 · 有 citation  
2. 切 **精准** · 问跨库对比题 → 展开时间线 · 见 2～5 步 · 仍有 citation  
3. **E-budget**：复杂题触顶 5/5 → chip 变 warn · 仍返回答  
4. 快速/精准 **连问 31 次/h** → 第 31 次 **429**（与 G1 相同计数）  
5. 终端：`test_agent_*.py` 绿 · `golden_agent_qa.json` **15/15** · `test_retrieval_golden` **12/12** · `npm run build` 绿  

**这回不做**：`get_document_metadata` · 历史回放 tool 时间线 · 编辑/采纳 · 自动升精准 · 改检索算法。

---

## §4 数据模型（L 关确认 · Implement 写 TECH-7）

### 4.1 新表 `agent_runs`

| 字段 | 说明 |
|------|------|
| `id` | UUID PK |
| `thread_id` | FK → `chat_threads.id` |
| `user_id` | 所有者（H2-1-A · Admin 不可读他人正文） |
| `mode` | `thorough`（fast 模式 **不创建** run） |
| `status` | `running` \| `completed` \| `failed` \| `capped` |
| `steps_used` | 0～5 |
| `max_steps` | 默认 5 |
| `assistant_message_id` | 关联落库 assistant message |
| `created_at` / `finished_at` | 审计/列表 |

### 4.2 新表 `agent_steps`

| 字段 | 说明 |
|------|------|
| `id` | UUID PK |
| `run_id` | FK → `agent_runs.id` |
| `step_index` | 1-based |
| `tool_name` | §2.1 四 tool 名 |
| `args_json` | 模型入参（摘要级 · 不含 secrets） |
| `result_summary` | tool_result `summary` |
| `ok` | bool |
| `latency_ms` | int |
| `status` | `running` \| `done` \| `error` |

### 4.3 Schema 增量

| 变更 | 说明 |
|------|------|
| `ChatRequest.mode` | `Literal["fast","thorough"]` · 默认 **`fast`**（H3-5-A） |
| `ChatStreamDone` | 可选 `agent_run_id`（仅 thorough） |
| **不**改 `chat_messages` 列 | 无 `tool_trace` JSON（H3-2-B） |

---

## §5 API · SSE（L 关确认）

### 5.1 HTTP

| 方法 | 路径 | Body 增量 | 行为 |
|------|------|-----------|------|
| POST | `/ask/threads/{id}/chat` | `{ message, mode? }` | `fast` → 现网 `stream_workspace_chat_events` |
| POST | `/knowledge-bases/{kb_id}/threads/{id}/chat` | 同上 | `fast` → `stream_chat_events` |
| — | 同上 | `mode=thorough` | `stream_agent_workspace_events` / `stream_agent_kb_events` |

**Query 不变**：`workspace` · `department_id`（G2）。

**并发**：同 thread 生成中再 POST → **409**（H3-4-A · G3-E7）。

### 5.2 SSE 事件（SSOT = R §3 · L 采纳）

| 事件 | 模式 | 顺序 |
|------|------|------|
| `tool_start` / `tool_result` | thorough only | 全部在 **首条 citation 前** |
| `agent_budget` | thorough · **每步后**（H3-3-B） | tool 块内 · 最后一步可 `capped=true` |
| `citation` | 两模式 | **全部在首条 token 前**（R4-4） |
| `token` | 两模式 | citation 后 |
| `done` | 两模式 | 末帧 · 含 `message_id` · thorough 含 `agent_run_id?` |

**快速模式序列**（字节级兼容 G1/G2）：

```
citation* → token* → done
```

**精准模式序列**：

```
(tool_start → tool_result → agent_budget)* → citation* → token* → done
```

### 5.3 只读 Tool 清单（Implement 包装层 · R §2 SSOT）

| Tool | 现网映射 | 首版 |
|------|----------|------|
| `list_knowledge_bases` | `listing.list_knowledge_bases` | ✅ G3-1.2 |
| `semantic_search` | `retrieve_workspace_chunks` / `retrieve_chunks` | ✅ G3-1.3 |
| `search_documents` | `search_documents_by_filename` / `_by_content` | ✅ G3-1.4 |
| `get_chunk_excerpt` | `DocumentChunk` + `_excerpt` | ✅ G3-1.5 |
| `get_document_metadata` | `listing.get_document` | ❌ **Defer**（H3-1-B） |

---

## §6 UI/UX（对齐 preview v4.1）

### 6.1 布局增量

```
┌─ Thread 列表 ─┬─ Toolbar + AgentModeSwitcher + budget-chip ─┐
│  (G2 260px)   │  ToolTimeline（thorough · 折叠 trace-panel）   │
│               │  消息 + citation chips（R4-4 顺序不变）         │
│               │  Sticky 输入（G2 UX-1）                       │
└───────────────┴──────────────────────────────────────────────┘
```

### 6.2 组件

| 组件 | 职责 | 预览对标 |
|------|------|----------|
| `AgentModeSwitcher` | 快速/精准 · 编辑灰钮 disabled | `.mode-switcher` |
| `ToolTimeline` | 解析 `tool_*` SSE | `.trace-panel` |
| `AgentBudgetChip` | `agent_budget` → chip + meter | `.budget-chip` / `.budget-meter` |
| `use-thread-session.ts` | 扩展 handlers · Abort（G3-E1） | 预览 S5 |

### 6.3 关键交互

| 操作 | 行为 | E |
|------|------|---|
| 默认进 `/ask` | mode=**快速** | S3 · HA-1-A |
| 切精准再问 | 出现时间线 | S4 · S5 |
| 发送中切模式 | Abort SSE · 输入恢复 | **G3-E1** |
| 步数 5/5 | budget warn · 停止新 tool | **E-budget** |
| Member 点编辑 | disabled · 无 POST | **E-M** |
| 刷新页面 | 正文+citation 在 · **无** tool 时间线 | **H3-2-B** |

---

## §7 审计（衔接 G2 §7 · H2-1-A）

| 事件 | action | metadata |
|------|--------|----------|
| 精准 run 开始 | `agent.run_started` | run_id, thread_id, mode, max_steps |
| tool 执行 | `agent.tool_executed` | run_id, step, tool, ok, latency_ms · **无** query 全文 |
| 越权 kb | `agent.tool_denied` | run_id, tool, reason=forbidden_kb |
| run 结束 | `agent.run_completed` | run_id, steps_used, capped, citation_count |

---

## §8 乱操作 · S/E 映射（Implement 验收 SSOT）

> 完整表见 `discovery-agent-g3-read-research.md` §4 · Implement 关单写 `G3_AGENT_ACCEPTANCE.md`。

### 8.1 预览 S（G3 主线）

| ID | 场景 | 挂任务 |
|----|------|--------|
| S3 | 快速 · 无时间线 | G3-3.4 |
| S4 | 精准 · tool 时间线 | G3-3.2 · G3-3.4 |
| S5 | 手动切模式 | G3-3.1 · G3-3.4 |
| S1/S2/S6/S7/S8 | G2 回归 | G3-3.4 不得破坏 |
| S-agent | golden 15 题抽检 | G3-4.2 |

### 8.2 边界 E

| ID | 场景 | Tool | SSE | 挂任务 |
|----|------|------|-----|--------|
| **E-budget** | 5 步触顶 | 全 tool | `agent_budget.capped` | G3-2.2 · G3-4.1 |
| **E-M** | Member 编辑 | — | — | G3-3.1 |
| **E-empty** | 空消息 | — | — | G3-0.3 |
| **G3-E1** | 发送中切模式 | — | Abort | G3-3.5 |
| **G3-E2** | 越权 kb_id | semantic_search 等 | tool_result ok=false | G3-1.1 · G3-4.1 |
| **G3-E3** | 无可见库 | — | 400 | G3-2.4 |
| **G3-E4** | 30/h 限流 | — | 429 | G3-2.4 |
| **G3-E5** | 快速无 tool SSE | — | 无 tool_* | G3-2.4 |
| **G3-E6** | 全无命中拒答 | semantic_search | 无 citation | G3-2.2 · G3-4.1 |
| **G3-E7** | 并行 POST | — | 409 | G3-2.6 |
| **G3-E8** | 硬闯 edit mode | 白名单 | 400 | G3-0.3 · G3-2.4 |
| **G3-E9** | 库内精准 | semantic_search 默认 kb | tool_* 同显 | G3-2.3 · G3-3.4 |
| **G3-E10** | Admin 不看他人正文 | — | 无泄露 API | G3-0.1 · G3-2.1 |

---

## §9 原子任务（Implement 顺序 · WIP=1）

> **列说明**：**§2 Tool** = R research §2 · **§3 SSE** = R §3 · **§4 E** = R §4 / 上表。

### Wave 0 · 模型 + 契约

| # | 任务 | §2 Tool | §3 SSE | §4 E | 验收 |
|---|------|---------|--------|------|------|
| **G3-0.1** | Alembic：`agent_runs` + `agent_steps` | — | — | G3-E10 | upgrade 绿 · FK thread/user |
| **G3-0.2** | `AgentMode` enum · SQLAlchemy models | — | — | — | import 无环 |
| **G3-0.3** | `ChatRequest.mode` 默认 `fast` · OpenAPI | — | — | E-empty · G3-E8 | schema 422/400 测 · **不动** fast 现网路径 |
| **G3-0.4** | `services/agent/runs.py` CRUD | — | — | G3-E10 | 创建 run/step · 按 user_id 隔离 |

### Wave 1 · Tool 包装层（H3-1-B：4 tool）

| # | 任务 | §2 Tool | §3 SSE | §4 E | 验收 |
|---|------|---------|--------|------|------|
| **G3-1.1** | `tools/registry.py` + scope 基类 · `visible_kb_ids` 求交 | §2.4 规则 | — | G3-E2 · G3-E8 | 单元测 deny 越权 kb |
| **G3-1.2** | `list_knowledge_bases` | §2.2 | tool_* payload | — | 返回 ≤24 · scope_label |
| **G3-1.3** | `semantic_search` | §2.2 | tool_* | G3-E9 | **只调** retrieve_* · golden 12/12 仍绿 |
| **G3-1.4** | `search_documents` | §2.2 | tool_* | — | filename 默认 · content 分支 |
| **G3-1.5** | `get_chunk_excerpt` | §2.2 | tool_* | G3-E2 | forbidden 不 500 |

### Wave 2 · Runtime + SSE

| # | 任务 | §2 Tool | §3 SSE | §4 E | 验收 |
|---|------|---------|--------|------|------|
| **G3-2.1** | `agent/runtime.py` ReAct 循环 · max 5 · 超时 | §2.4 | tool_start/result | E-budget | 每文件 ≤300 行 |
| **G3-2.2** | 步数触顶 · 合并 hits → gate → 生成 | semantic_search | agent_budget **每步** | E-budget · G3-E6 | capped run status |
| **G3-2.3** | `stream_agent_workspace_events` + `stream_agent_kb_events` | 全 tool | §3.3 顺序 | G3-E9 · R4-4 | `test_r4_4_streaming` 扩展或 sibling |
| **G3-2.4** | `ask_threads` / `kb_threads` dispatch · fast 复用现网 | — | §3.3 fast 路径 | G3-E3～E5 | fast 零回归 · thorough 新路径 |
| **G3-2.5** | thread 生成锁 · 409 | — | — | G3-E7 | 并发 POST 测 |
| **G3-2.6** | audit §7 钩子 | 全 tool | — | G3-E10 | `test_agent_audit.py` |

### Wave 3 · 前端

| # | 任务 | §2 Tool | §3 SSE | §4 E | 验收 |
|---|------|---------|--------|------|------|
| **G3-3.1** | `AgentModeSwitcher` · 编辑 vision disabled | — | — | E-M · S5 | build 绿 |
| **G3-3.2** | `ToolTimeline` + SSE handlers | — | tool_start/result | S4 | 折叠条 · 失败红色 |
| **G3-3.3** | `AgentBudgetChip` | — | agent_budget | E-budget | meter 随步更新 |
| **G3-3.4** | `AskPage` + `ChatPage` 接入 mode | — | 全序列 | S3～S8 | G2 回归 smoke |
| **G3-3.5** | 发送中切模式 AbortController | — | — | G3-E1 | 无双 SSE |

### Wave 4 · 评测 + 验收表

| # | 任务 | §2 Tool | §3 SSE | §4 E | 验收 |
|---|------|---------|--------|------|------|
| **G3-4.1** | `tests/test_agent_*.py`（budget/deny/409/SSE 序） | §2.1 | §3.3 | G3-E1～E8 · E-budget | pytest 绿 |
| **G3-4.2** | `docs/golden_agent_qa.json` **15 题** + runner | semantic_search 等 | — | H3-6-A | CI 15/15 · 含 3 类 |
| **G3-4.3** | `G3_AGENT_ACCEPTANCE.md` S/E 可勾选 | — | — | §8 全表 | 对齐 preview S3～S5 + E |

### Wave 5 · 文档关单

| # | 任务 | §2 Tool | §3 SSE | §4 E | 验收 |
|---|------|---------|--------|------|------|
| **G3-5.1** | TECH **TECH-7** Agent 数据流 | §2 SSOT | §3 SSOT | — | TECH 索引更新 |
| **G3-5.2** | PRD **G-3-x** 节 | §2 | §3 · §4 | — | PRD §12 索引 |
| **G3-5.3** | cockpit · platform-plan §7 指 G3 Implement | — | — | — | SSOT 一致 |

**Golden gate**：任何 Wave 若改 `retrieve_*` 实现 → 必跑 `test_retrieval_golden` **12/12**；Agent 独立 **`golden_agent_qa.json` 15/15**。

---

## §10 门禁三题（Implement 前自答）

1. **触发点**：`/ask` → 选 thread →（可选）切 **精准** → `POST .../threads/{id}/chat` `{ message, mode }`  
2. **数据流**：解析 scope →（thorough）runtime 循环 tool → SSE tool_* → 合并 chunk → gate → citation → token → done → `agent_runs/steps` + message 落库  
3. **怎么验**：§3.1 五步法 + §8 S/E + `test_agent_*` + golden 15 + retrieval golden 12/12 + build  

---

## §11 L 关 DoD

| # | 条件 | 状态 |
|---|------|------|
| L1 | 本文落盘 `discovery-agent-g3-read-plan.md` | ✅ 2026-07-09 |
| L2 | §2 做/不做 + §3 **H3-1～H3-6 确认** | ✅ 2026-07-09 |
| L3 | §3.1 大白话 + 最小验收集 | ✅ |
| L4 | §5 SSE 顺序 + §6 UI 对齐 v4.1 | ✅ |
| L5 | §9 原子任务 G3-0～G3-5 · 每条挂 §2/§3/§4 | ✅ |
| L6 | cockpit · platform-plan §7 同步 | ✅ 2026-07-09 |

---

## §12 面试 30 秒（L 窗）

「G3 在 G2 thread 上加 **快速/精准** 两档：快速就是现网一次检索；精准是最多 5 步 **只读 tool**，SSE 多 tool 时间线和步数 meter，但 **citation 仍然在 token 前面**。四个 tool 全是现网 API 的包装，模型传的 kb_id 会被 OrgScope 截断。我们刻意不做 metadata tool 和历史 trace 回放，控制首版范围；评测用 15 题 golden，检索 golden 12 题继续挡 CI。」

---

## §13 下一窗交接（Implement · G3-0.1）

```
@rag-knowledge-platform/docs/tasks/discovery-agent-g3-read-plan.md
@rag-knowledge-platform/docs/tasks/discovery-agent-g3-read-research.md
@rag-knowledge-platform/docs/preview-agent-platform.html
@rag-knowledge-platform/docs/cockpit.html
@rag-knowledge-platform/AGENTS.md

【背景】G3 L ✅ · H3-1～H3-6 已拍板 · V v4.1 冻结 · R §2/§3/§4 SSOT

【要求】严格只做 plan §9 **G3-0.1**（Alembic agent 表）· 不写 G3-1+ · WIP=1

【验收】alembic upgrade head 绿 · models 可导入 · pytest 基线仍绿 · 不动 stream_chat_events
```
