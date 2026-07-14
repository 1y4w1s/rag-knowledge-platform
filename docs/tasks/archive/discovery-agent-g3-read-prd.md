# 发现层 · 只读 RAG Agent PRD（G-3）

> **状态**：✅ **G-3 整线**（2026-07-10）· P/R/L/I ✅ · G3-5.1～G3-5.3 ✅ · pytest **523** 绿  
> **背景**：G-2 thread 交付后，跨库复杂题一次检索不够、用户看不到 Agent 过程；预览 v4.1 已演示 **快速 / 精准** 两档，Implement 对齐  
> **依赖**：G-1 ✅ · G-2 ✅ · ORG OrgScope · Plan：`discovery-agent-g3-read-plan.md` · Research §2/§3 SSOT

---

## 索引

| 节 | 内容 | 状态 |
|----|------|------|
| **G-3-1** | 定位 · 快速/精准两档 · 与 G1/G2 关系 | ✅ 2026-07-09 H3 拍板 |
| **G-3-2** | 只读 Tool 清单（4 tool） | ✅ H3-1-B 延后 metadata |
| **G-3-3** | SSE 序列 · UI 组件 | ✅ 对齐 preview v4.1 |
| **G-3-4** | 权限 · 限流 · 审计 · 乱操作 | ✅ H2-1-A · H3-4～H3-6 |
| **G-3-5** | 验收口径（S/E 摘要） | ✅ `G3_AGENT_ACCEPTANCE.md` · G3-4.3 |

**关联文档**：主 PRD `docs/PRD.md` §5.6 · TECH `docs/TECH.md` **TECH-7** · 验收 [`G3_AGENT_ACCEPTANCE.md`](../G3_AGENT_ACCEPTANCE.md) · Plan `discovery-agent-g3-read-plan.md`

---

## G-3-1 定位 · 快速/精准两档 · 与 G1/G2 关系 ✅

**这节定什么**：在 G-2 **thread 会话** 上叠加 **手动两档**——用户顶栏切 **快速 / 精准**（工程 `mode=fast|thorough`）；**快速** = 现网 G1 **单次检索**、**无** tool 时间线；**精准** = 最多 **5 步只读 tool**、SSE 展示折叠时间线与步数 meter，**引用 chip 仍在文字前面**（R4-4）。

### 与 G1/G2 对比

| | G-1 跨库检索 | G-2 thread | G-3（本交付） |
|--|--------------|------------|---------------|
| 检索次数 | 固定 **1 次** | 同 G1 | **快速** = 1 次 · **精准** = 最多 5 步 |
| 过程可见性 | 黑盒 | 同 G1 | **精准** 有 tool 时间线 + budget-chip |
| 发消息 API | `POST .../threads/{id}/chat` | 同左 | body 增 **`mode`** · 默认 **`fast`** |
| 历史回放 | 正文 + citation | 同左 | **不**还原 tool 时间线（H3-2-B） |
| 限流 | 30 次/h | 同左 | **1 次发送 = 1 次计数**（不按步数倍乘） |

### 名词（人话）

| 名词 | 含义 |
|------|------|
| **快速** | 搜一次、答一次 · **无** tool 时间线（`mode=fast`） |
| **精准** | 最多 5 步只读查询 · 有折叠时间线（`mode=thorough`） |
| **tool 时间线** | 精准模式下：「列库 → 跨库检索 → …」折叠条 |
| **budget-chip** | 「2/5 步」进度 · 满 5 步变红警告 |
| **agent_run** | 一次精准提问在库里的执行记录（Admin **看不到**问题原文） |

### 正常流程（S · 摘要）

| # | 用户做什么 | 看见什么 |
|---|------------|----------|
| S3 | 进 `/ask` · **默认快速** · 问「年假」 | **无** 时间线 · 有 citation chip |
| S4 | 切 **精准** · 问跨库对比题 | 展开时间线 · 2～5 步 · citation **先于** 正文流式 |
| S5 | 快速 ↔ 精准 **手动**切换再问 | 模式即时生效 · **不**自动升精准（HA-4-A） |
| — | 库内 chat 同样顶栏 | 精准默认当前库 scope（G3-E9） |
| — | F5 刷新 | 正文 + citation **在** · tool 时间线 **不在** |

### 明确不做

- `get_document_metadata` tool（**H3-1-B** 延后至 G4 前可补）  
- 历史消息 **还原** tool 时间线（仅 `agent_steps` 表记元数据）  
- **写** tool · `approval_*` · 联网搜索 · G7 Webhook（G4 愿景）  
- Member **编辑/采纳** 模式（UI 灰钮 disabled · E-M）  
- 对话内 **多轮上下文记忆**（另立项）  
- 自动升精准（必须用户手动切）  
- 改动 RRF/rerank 参数（检索 golden 12/12 仍挡 CI）

---

## G-3-2 只读 Tool 清单（4 tool）✅

**这节定什么**：精准模式下 Agent 可调用的 **只读** 能力；全部为现网 API **包装层**，不信模型传的 org/kb，与 `OrgScope.visible_kb_ids` **求交**。

### 首版 4 tool（Research §2 SSOT）

| Tool | 人话 | 现网能力 | 首版 |
|------|------|----------|------|
| `list_knowledge_bases` | 列「我能搜哪些库」 | `GET /knowledge-bases` 同权限 | ✅ |
| `semantic_search` | 跨库/指定库 hybrid 检索 | `retrieve_workspace_chunks` / `retrieve_chunks` | ✅ |
| `search_documents` | 按文件名或正文找文档 | 跨库 `search_documents_by_*` | ✅ |
| `get_chunk_excerpt` | 展开某条命中读摘录 | `DocumentChunk` + excerpt | ✅ |
| `get_document_metadata` | 读文档元数据 | `listing.get_document` | ❌ **Defer** |

### 与快速模式关系

**快速** = `semantic_search` **隐式 1 次**（不暴露 tool SSE · G3-E5）· 字节级兼容 G1/G2 SSE 序列。

### 权限原则

- 模型传入的 `kb_ids` 与 **可见库列表求交**；越权 → tool 返回「无权限」· **不** 500（G3-E2）  
- 库内精准：默认 **当前路径 kb** 为检索 scope（G3-E9）  
- 非法 tool 名 / `mode=edit` → **422**（G3-E8）

---

## G-3-3 SSE 序列 · UI 组件 ✅

**这节定什么**：精准模式多出的 SSE 事件顺序、顶栏与消息区 UI 增量；对齐 `preview-agent-platform.html` **v4.1** S3～S5。

### SSE 序列（Research §3 SSOT）

| 模式 | 事件顺序 |
|------|----------|
| **快速** | `citation*` → `token*` → `done`（**无** `tool_*` / `agent_budget`） |
| **精准** | `(tool_start → tool_result → agent_budget)*` → `citation*` → `token*` → `done` |

**硬约束**：

1. 所有 `tool_*` 在 **第一条 `citation` 之前**（用户先见过程再见引用块）  
2. `citation` 仍在 **第一条 `token` 之前**（R4-4 不变）  
3. `agent_budget` **每步后发**（H3-3-B）· 第 5 步可 `capped=true`（E-budget）

### 布局增量（§6 摘要）

```
Thread 列表 260px │ Toolbar + AgentModeSwitcher + budget-chip
                  │ ToolTimeline（精准 · 折叠 trace-panel）
                  │ 消息 + citation chips（R4-4 顺序不变）
                  │ Sticky 输入（G2 UX-1）
```

### 关键组件

| 组件 | 职责 |
|------|------|
| `AgentModeSwitcher` | 顶栏 **快速 / 精准** · Member「编辑」灰钮 disabled |
| `ToolTimeline` | 解析 `tool_start`/`tool_result` · 失败红色 |
| `AgentBudgetChip` | `agent_budget` → `N/5 步` · capped 变 warn |
| `use-thread-session.ts` | 扩展 SSE handlers · 发送中切模式 **Abort**（G3-E1） |

### 关键交互

| 操作 | 行为 |
|------|------|
| 默认进 `/ask` | mode = **快速** |
| 切精准再问 | 出现时间线 · budget 随步更新 |
| 发送中切模式 | Abort SSE · 输入恢复 |
| 步数 5/5 | budget warn · 停止新 tool · **仍基于已有片段作答** |
| 刷新页面 | 正文 + citation 在 · **无** tool 时间线 |

**页面**：`AskPage.tsx` · `ChatPage.tsx` · G2 thread 布局 **不得破坏**（S1/S2/S6/S7/S8 回归）。

---

## G-3-4 权限 · 限流 · 审计 · 乱操作 ✅

### 归属与隐私（H2-1-A · G3-E10）

| 规则 | 说明 |
|------|------|
| `agent_runs` / `agent_steps` 按 **user_id** 隔离 | 仅本人 thread 下的 run |
| Admin | **无** 他人对话正文 API · audit 仅 metadata |
| 审计 | **不含** 用户问题全文 · 记 run_id、tool、步数、latency |

### 限流与并发

| 规则 | 说明 |
|------|------|
| 限流 | `30/h` · **1 次发送 = 1 次 chat 计数**（HA-1-A） |
| 同 thread 并行 POST | **409**「上一条仍在生成」（H3-4-A · G3-E7） |
| 无可见库 | **400**（G3-E3） |

### 审计事件（摘要）

| 事件 | action | metadata 示例 |
|------|--------|---------------|
| 精准 run 开始 | `agent.run_started` | run_id, thread_id, mode, max_steps |
| tool 执行 | `agent.tool_executed` | run_id, step, tool, ok, latency_ms |
| 越权 kb | `agent.tool_denied` | run_id, tool, reason=forbidden_kb |
| run 结束 | `agent.run_completed` | run_id, steps_used, capped, citation_count |

### 乱操作（E · 摘要 · plan §8）

| ID | 乱操作 | 系统怎么处理 | 你怎么验 |
|----|--------|--------------|----------|
| **E-budget** | 复杂题触顶 5 步 | `capped=true` · 仍回答 | 对比 preview E-budget |
| **E-M** | Member 点「编辑」 | disabled · 无 POST | member 账号 |
| **E-empty** | 空 message | **422** | 空框发送 |
| **G3-E1** | 发送中切模式 | Abort SSE | 流式中途切换 |
| **G3-E2** | 模型传越权 kb_id | tool ok=false | pytest / 手工 |
| **G3-E3** | 无可见库 | **400** | 无 grant 场景 |
| **G3-E4** | 连问 31 次/h | **429** | 与 G1 相同计数 |
| **G3-E5** | 快速模式 | **无** tool SSE | 默认快速提问 |
| **G3-E6** | 全无命中 | 拒答 · 无 citation | 无关问题 |
| **G3-E7** | 连点发送 | **409** | 并行 POST |
| **G3-E8** | `mode=edit` 等非法值 | **422** | 硬闯参数 |
| **G3-E9** | 库内精准 | 默认当前 kb · tool 同显 | 库内 chat |
| **G3-E10** | Admin 查他人 | 无泄露 API | pytest audit |

---

## G-3-5 验收口径（S/E 摘要）

> **完整可勾选表**：[`G3_AGENT_ACCEPTANCE.md`](../G3_AGENT_ACCEPTANCE.md) · G3-4.3 ✅ · Plan §3.1 五步法 · TECH-7 §7.9 对照

### 浏览器最小集（Plan §3.1）

1. `/ask` 默认 **快速** · 问「年假」→ **无** 时间线 · 有 citation  
2. 切 **精准** · 问跨库对比题 → 展开时间线 · 见 2～5 步 · 仍有 citation  
3. **E-budget**：复杂题触顶 5/5 → chip 变 warn · 仍返回答  
4. 快速/精准 **连问 31 次/h** → 第 31 次 **429**（与 G1 相同计数）  
5. `test_agent_*.py` 绿 · `golden_agent_qa.json` **15/15** · `test_retrieval_golden` **12/12** · `npm run build` 绿  

### 自动化门槛（A 层 · TECH-7 §7.10）

| # | 项 | 期望 |
|---|-----|------|
| A1 | Agent 边界 pytest | `test_agent_*.py` 全绿 |
| A2 | Agent golden | `golden_agent_qa.json` **15/15**（multi_step / refusal / forbidden_kb） |
| A3 | 检索 golden 不回退 | `test_retrieval_golden` **12/12** |
| A4 | R4-4 顺序 | citation 先于 token · agent 用例绿 |
| A5 | 前端 build + abort | `npm run build` · `thread-stream-abort` 绿 |

### P 关 DoD（G3-5.2）

| # | 条件 | 状态 |
|---|------|------|
| P1 | G-3-1～G-3-4 与 plan H3 拍板一致 | ✅ |
| P2 | 全文落盘本文 | ✅ 2026-07-10 |
| P3 | 主 PRD §5.6 + §12.5 索引 · TECH-7 索引 | ✅ G3-5.2 |

---

## 文档关单（G3-5 · ✅ 2026-07-10）

- **G3-5.1** ✅ TECH **TECH-7** Agent 数据流  
- **G3-5.2** ✅ 本文 PRD G-3-x · 主 PRD §12.5 索引  
- **G3-5.3** ✅ cockpit · platform-plan §7 · SSOT 一致

---

## 答辩 30 秒

「G3 在 G2 thread 上加 **快速/精准** 两档：快速就是现网一次检索；精准是最多 5 步 **只读 tool**，SSE 多 tool 时间线和步数 meter，但 **citation 仍然在 token 前面**。四个 tool 全是现网 API 的包装，模型传的 kb_id 会被 OrgScope 截断。我们刻意不做 metadata tool 和历史 trace 回放，控制首版范围；评测用 15 题 golden，检索 golden 12 题继续挡 CI。」
