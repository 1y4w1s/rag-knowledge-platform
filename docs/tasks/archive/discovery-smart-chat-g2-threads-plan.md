# G-2 · 企业级对话历史 + 对话 UX 大修 · Plan

> **状态**：… → ✅ **G2-4.1**（2026-07-09）→ ✅ **G2-4.2**（2026-07-09）→ ✅ **G2-4.3**（2026-07-09）· **G-2 整线 ✅**  
> **触发**：G1-4 `/ask` 验收 · 「新建对话后记录像没了」· 要 **可溯源** 的企业级历史  
> **依赖**：G1 ✅（`/ask` + `chat_messages` workspace 列）· UX-P1 Wave B5 chat-compare · PRD P1「多 thread UI」  
> **SSOT 关系**：G1 = 跨库问答 MVP · **G2 = thread 模型 + 历史 UI + 审计衔接** · UX-P1 = 视觉壳层（与 G2 同窗预览）

---

## §0 问题陈述（G1 MVP 债 · 用户原话对齐）

| 现象 | 根因（技术） | 用户感受 |
|------|--------------|----------|
| 点「+ 新建对话」后中间变空 | 前端 `resetChat()` **只清 React state**，无 server thread | 「记录没了」 |
| F5 后旧问答又出现 | `GET /ask/messages` 拉的是 **同一 workspace 下全部消息**（无 thread 边界） | 「到底算不算新建？」 |
| 无左侧/列表「历史会话」 | G1 Plan **明确不做** 多 thread 列表 | 「不像企业产品」 |
| 库内 chat 与 `/ask` 两套入口 | `thread_kind` 不同 · UI 未统一 | 「历史散在两处」 |
| 引用可点预览 | citation 已带 doc/page · E14 灰态 | 溯源 **内容级** 有 · **会话级** 弱 |

**结论**：G1 完成了「跨库检索 + 单条连续流落库」；**不等于** 企业级「多会话、可找回、可审计边界清晰」。

---

## §1 企业级目标（TO-BE · 一句话）

> 用户在 **工作区 `/ask` 与库内 chat** 都能：**看见历史会话列表 · 新建 = 服务端新 thread · 切换 thread 加载完整问答与引用 · 每条回答仍可追到文档片段**；管理员 **只看统计/审计元数据，不看他人正文**（对齐 TECH-SEC）。

### §1.1 与 G1 / PRD / TECH 对齐

| 文档 | 原表述 | G2 调整 |
|------|--------|---------|
| PRD §5.6 | 「新建对话 = 前端清空，历史仍落库」 | **升级为**：新建 = **POST thread** + 切到新 thread |
| PRD P1 | 「对话多 thread 历史 UI」 | **升格为 G2 主交付**（非无限拖延） |
| TECH §chat_messages | MVP 无 thread 表 | **新增 `chat_threads`** + message.`thread_id` |
| TECH-SEC | 对话审计不记全文 | **记** thread_id · kb/workspace · 字数 · 引用条数 · **不记** user 原文 |
| G1 §0 不做 | 多 thread 列表 | **移入 G2 做** |
| UX-P1 B5 | chat sticky + chip | **扩展**：thread 侧栏 + 与 G2 同一 compare 冻结 |

---

## §2 产品范围 · 做 & 不做

| 做 | 不做 |
|----|------|
| **`chat_threads` 表** + 迁移/backfill G1 已有消息 | 管理员查看他人对话 **正文** |
| `/ask` **thread 列表 UI**（侧栏或二级栏） | 团队 **共享** 同一条 thread（多人协作编辑） |
| 库内 `/knowledge-bases/:id/chat` **同构 thread UX** | 对话内 **多轮上下文记忆**（仍每问独立检索，另立项） |
| 「新建对话」= **创建 thread + 切换** | 导出 Word/PDF 会话（Wave 2+） |
| thread **标题**（首问自动截断 + 可改） | 全文搜索所有历史消息（P2） |
| 消息 **时间戳** 展示 · 按日分组 | 支付 / 积分 |
| 切换 thread / 切 workspace / 切部门 **边界规则** | 替换 G1 检索/引用逻辑 |
| 审计：`chat.thread_created` · `chat.message_sent` 元数据 | audit 存 user 问题全文 |
| UX：sticky 输入（UX-1）· thread 列表 · 空态 | UX-P1 全站 12 页一次 Implement |
| pytest + `npm run build` + golden 12/12 回归 | OCR / Agent |

---

## §3 拍板记录（H2-1～H2-7 · ✅ 用户确认 2026-07-08）

| 假设 | 选定 | 状态 |
|------|------|------|
| **H2-1** thread 归属 | **A** · 仅本人可见自己的 thread | ✅ |
| **H2-2** G1 旧数据 | **A** · 每 workspace+部门 合并 1 条「历史对话」 | ✅ |
| **H2-3** 新建对话 | **A** · POST 空 thread · 旧会话可点回 | ✅ |
| **H2-4** 列表位置 | **A** · 左二级栏 260px · 375 drawer | ✅ |
| **H2-5** 库内 vs 工作区 | **A** · 同一套 ThreadList 组件 | ✅ |
| **H2-6** 切部门 | **A** · thread 绑创建时 department_key · 列表 scope 过滤 Implement 再定 | ✅ |
| **H2-7** 删除 | **A** · 用户可归档/软删自己的 thread | ✅ |

<details><summary>拍板时后果摘要（归档）</summary>

| 假设 | 选 A 的后果（白话） |
|------|---------------------|
| H2-1 | Admin 只看统计/审计元数据，**打不开**成员聊天正文 |
| H2-2 | 升级后旧问答进一条「历史对话」，不会空白 |
| H2-3 | 点「新建」列表多一行，旧会话仍在左侧 |
| H2-4 | 桌面像企业 Chat；手机用「历史」抽屉 |
| H2-5 | `/ask` 与库内 chat 操作一致，只换数据源 |
| H2-6 | 切部门后旧 thread 还在；旧引用可能变灰 |
| H2-7 | 可删自己的会话；需软删 API |

</details>

### §3.1 大白话（L 关出口 · ✅ 用户确认 2026-07-09）

**一句话**：对话页左边多一列 **历史会话**；点「新建对话」会在服务器 **新建一条会话**，不是只清屏；旧问答并进一条叫 **「历史对话」** 的会话，点一下还能找回来；`/ask` 和库内 chat **同一套操作**。

| 名词 | 人话 |
|------|------|
| thread | 一条独立会话（像微信里一个聊天窗口） |
| 新建对话 | 调 API 建空 thread · 列表多一行 · **旧会话还在左侧** |
| 历史对话 | 升级时把 G1 旧消息合并进的默认会话名 |
| Thread 列表 | 桌面左侧 260px 栏 · 手机点「历史」开抽屉 |
| 切部门 | 旧会话还在列表里 · 旧引用可能变灰（E14 已有） |

**你怎么验（最小集 · Implement 后）**

1. 侧栏 **对话** → 左侧见会话列表 · 点 **+ 新建** → 中间空 · 列表多一行  
2. 问一句 → 标题自动变成问题前几字 · 切到旧会话 → 问答完整回来  
3. 库详情 **开始对话** → 同样左侧列表 · chip **仍无库名**  
4. 刷新页面 → 当前会话历史还在  
5. 终端：`pytest` 全绿 · golden 12/12 · `npm run build` 绿  

**这回不做**：多人共编同一会话 · 对话内多轮记忆 · 导出 PDF · 管理员看别人聊天正文 · 改 RAG 检索。

---

## §4 数据模型（L 关确认 · Implement 时写 TECH）

### 4.1 新表 `chat_threads`

| 字段 | 说明 |
|------|------|
| `id` | UUID PK |
| `thread_kind` | `workspace` \| `knowledge_base` |
| `kb_id` | 库内 thread 必填；工作区 NULL |
| `user_id` | 所有者 |
| `title` | 默认首问前 40 字；可 PATCH |
| `workspace_kind` / `workspace_org_id` / `workspace_department_key` | 与 G1 message 同语义 |
| `status` | `active` \| `archived` |
| `created_at` / `updated_at` | 列表排序用 |
| `last_message_at` |  denormalized 便于列表 |

### 4.2 `chat_messages` 变更

| 变更 | 说明 |
|------|------|
| `thread_id` FK → `chat_threads.id` | NOT NULL（迁移后） |
| 保留 G1 列 | 便于 scope 查询与审计 |

### 4.3 Backfill（H2-2-A）

1. 按 `(user_id, thread_kind, kb_id?, workspace_*)` 分组现有 messages  
2. 每组 insert 1 thread，`title` =「历史对话」或首条 user 内容截断  
3. 更新 message.`thread_id`

---

## §5 API（L 关确认）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/ask/threads` | 当前 user + workspace scope 下 workspace threads |
| POST | `/ask/threads` | 新建空 thread（**新建对话**） |
| PATCH | `/ask/threads/{id}` | 改 title / archive |
| DELETE | `/ask/threads/{id}` | 软删 |
| GET | `/ask/threads/{id}/messages` | 替代 flat `GET /ask/messages`（旧 API deprecate 一版） |
| POST | `/ask/threads/{id}/chat` | SSE（原 `POST /ask/chat` + thread_id） |
| GET/POST/... | `/knowledge-bases/{kb_id}/threads/*` | 库内同构（或统一 `/chat/threads?kind=` 🟡） |

**M5 限流**：仍按 user · 按 thread 发送计数。

---

## §6 UI/UX 大修（与 UX-P1 B5 合并预览）

### 6.1 布局（Desktop）

```
┌──────────┬─────────────┬──────────────────────────────┐
│  App     │ Thread      │  Toolbar: 空间/库 · 新建      │
│  Sidebar │ 列表        ├──────────────────────────────┤
│  220px   │  260px      │  消息区（按日分组 + 时间）    │
│          │  · 今天      │  引用 chip（workspace 带库名）│
│          │  · 昨天      ├──────────────────────────────┤
│          │  · 更早…     │  Sticky 输入（UX-1）          │
└──────────┴─────────────┴──────────────────────────────┘
```

### 6.2 375

- Thread 列表 → **抽屉**（顶栏「历史」按钮）
- 输入区 **始终 sticky**

### 6.3 关键交互

| 操作 | 行为 |
|------|------|
| 侧栏「对话」进 `/ask` | 打开 **最近 active thread** 或空 thread 引导 |
| 「+ 新建对话」 | POST thread → 空消息区 → 首问后自动改 title |
| 点列表项 | GET messages · 恢复引用与灰态 |
| 概览 `?q=` | 写入 **当前 thread**；无 thread 则先 POST |
| 库内「开始对话」 | 同构，列表只显示该 `kb_id` threads |

### 6.4 可溯源（用户可见）

| 层级 | 展示 |
|------|------|
| 会话 | thread title + 更新时间 |
| 消息 | 相对时间（今天 14:32） |
| 回答 | citation chip → 预览 → 文档页码 |
| 失效 | E14 灰 chip + 文案（已有） |
| 可选 P2 | 消息角标「复制 message_id」供工单 |

---

## §7 审计与合规（企业级 · 衔接 Plan-3E）

| 事件 | audit action | metadata 示例 |
|------|--------------|---------------|
| 新建 thread | `chat.thread_created` | thread_id, thread_kind, workspace, kb_id |
| 发送消息 | `chat.message_sent` | thread_id, citation_count, retrieval_ms, **不含** question 全文 |
| 归档/删 thread | `chat.thread_archived` | thread_id |

**不做**：Admin UI 查看他人 thread 正文（H2-1-A）。

---

## §8 还差什么 · 专业团队 Gap 清单

| # | 域 | 缺口 | G2 覆盖 | 仍后置 |
|---|-----|------|---------|--------|
| 1 | **产品** | 多 thread 列表 + 新建语义 | ✅ §6 | — |
| 2 | **数据** | 无 `thread_id` | ✅ §4 | — |
| 3 | **API** | flat messages | ✅ §5 | 全文搜索 |
| 4 | **UX** | 输入滚走 UX-1 | ✅ Wave G2-4 + UX-P1 A1 | — |
| 5 | **UX** | `/ask` 与库内 chat 双壳 | ✅ 组件复用 | — |
| 6 | **溯源** | 引用链 | G1 已有 | 消息级 export |
| 7 | **审计** | 对话仅计数 | ✅ §7 | 审计 **查看页**（master P1） |
| 8 | **合规** | 保留 N 天 | 字段预留 | SEC-8 配置 UI |
| 9 | **权限** | 切部门 thread 边界 | ✅ H2-6 | — |
| 10 | **测试** | 无 thread CRUD 测 | Wave G2-5 | — |
| 11 | **文档** | PRD §5.6 过时 | G2 PRD 增补节 | — |
| 12 | **预览** | 无 thread 对比稿 | `preview-agent-platform.html` ✅ | — |

---

## §9 原子任务（Implement 顺序 · WIP=1）

### Wave 0 · 模型 + 迁移

| # | 任务 | 验收 |
|---|------|------|
| **G2-0.1** ✅ | Alembic：`chat_threads` + `messages.thread_id` | upgrade 绿 · 2026-07-09 |
| **G2-0.2** ✅ | Backfill G1 消息 → 默认 thread | `019_chat_threads_backfill.py` · 2026-07-09 |
| **G2-0.3** ✅ | persistence/service 按 thread 读写 | `thread_persistence.py` · `020` NOT NULL · 2026-07-09 |

### Wave 1 · API

| # | 任务 | 验收 |
|---|------|------|
| **G2-1.1** ✅ | `/ask/threads` CRUD + `/threads/{id}/messages` | T-thread-1～4 · 2026-07-09 |
| **G2-1.2** ✅ | `POST /threads/{id}/chat` SSE | T-thread-5～6 · T-ask 回归 · 2026-07-09 |
| **G2-1.3** ✅ | 库内 `/knowledge-bases/{id}/threads/*` | T-kb-thread-1～6 · kb chat 回归 · 2026-07-09 |
| **G2-1.4** ✅ | audit 钩子 §7 | audit_logs 可查 · `test_chat_audit_events.py` · 2026-07-09 |

### Wave 2 · 前端 thread UI

| # | 任务 | 验收 |
|---|------|------|
| **G2-2.1** ✅ | `thread-api.ts` + `use-thread-session.ts` | Network 正确 · `npm run build` 绿 · 2026-07-09 |
| **G2-2.2** ✅ | `ThreadListPanel` 组件 | 列表/新建/切换 · `thread-list-utils` · build 绿 · 2026-07-09 |
| **G2-2.3** ✅ | `AskPage` 三栏布局 + drawer 375 | S-thread 浏览器 · 2026-07-09 |
| **G2-2.4** ✅ | `ChatPage` 同构 + 库内无库名 chip | S6 仍过 · 2026-07-09 |
| **G2-2.5** ✅ | 「新建对话」接 POST thread | toolbar POST · 列表多一行 · 2026-07-09 |

### Wave 3 · UX 大修 + 预览

| # | 任务 | 验收 |
|---|------|------|
| **G2-3.1** ✅ | `preview-agent-platform.html` v3.1（意图驱动 · 历史侧栏对齐实装） | V 关 S+E · 2026-07-09 |
| **G2-3.2** ✅ | sticky 输入 · 消息时间 · 按日分组 | UX-1 ✅ · day pill + 相对时间 · 2026-07-09 |
| **G2-3.3** ✅ | 空态/加载/错态统一 | DESIGN-6 更新 · `ChatEmptyPanel` / `ChatLoadingPanel` · 2026-07-09 |

### Wave 4 · 文档关单

| # | 任务 | 验收 |
|---|------|------|
| **G2-4.1** ✅ | PRD 增 **G-2-x** 节 · TECH thread 数据流 | `discovery-smart-chat-g2-threads-prd.md` · TECH-5.8 · PRD §12.5 索引 · 2026-07-09 |
| **G2-4.2** ✅ | cockpit · master-plan 指 G2 | SSOT · cockpit G-2 wave 终对齐 · master-plan §10 发现层索引 · 2026-07-09 |
| **G2-4.3** ✅ | 验收表 S/E | `G2_THREADS_ACCEPTANCE.md` · S/E 可勾选 · 2026-07-09 |

**Golden gate**：动 RAG 检索路径时仍跑 `test_retrieval_golden` 12/12；G2 默认 **不动** retrieval。

---

## §10 与 master-plan / UX-P1 排期建议

| 线 | 建议 |
|----|------|
| **G1** | G1-5 文档关单可先做；**不阻塞** G2 P 窗 |
| **G2** | **Phase 1**（2026-09～10）与 FE-P0、audit 页并行 — 用户已提 **历史/UX 为 P0 体验债** |
| **UX-P1** | B5 chat-compare **改为 G2 预览**（含 thread 侧栏），避免做两遍 |
| **Eval-Ops** | 不挡 G2；k6 加 thread list 接口可选 |

---

## §11 门禁三题（Implement 前自答）

1. **触发点**：侧栏「对话」→ `/ask` → 选/建 thread → `POST /api/v1/ask/threads/{id}/chat`  
2. **数据流**：POST/GET threads → 消息带 `thread_id` → SSE 检索（G1 路径不变）→ 落库 → 列表按 `last_message_at` 排序  
3. **怎么验**：§3.1 浏览器 5 步 + thread CRUD pytest + golden 12/12 + build  

---

## §12 L 关 DoD（Plan 出口）

| # | 条件 | 状态 |
|---|------|------|
| L1 | 本文落盘 | ✅ 2026-07-08 |
| L2 | §2 做/不做 + §3 假设 **用户确认** | ✅ 2026-07-08 |
| L3 | §3.1 大白话 **用户确认** | ✅ 2026-07-09 |
| L4 | §6 布局 + V 预览确认 | ✅ 2026-07-08 |
| L5 | §9 原子任务无歧义 | ✅ |
| L6 | cockpit / master-plan 索引指向 G2 | ✅ 2026-07-09 |

---

## §13 下一窗交接（G-2 整线 ✅ · 可选 G-AGENT / UX-P1）

```
@rag-knowledge-platform/docs/cockpit.html
@rag-knowledge-platform/docs/G2_THREADS_ACCEPTANCE.md
@rag-knowledge-platform/docs/tasks/discovery-agent-platform-plan.md

【背景】G-2 G2-0～G2-4.3 ✅ · 验收表 `G2_THREADS_ACCEPTANCE.md` 脚本就绪 · 待用户亲手勾选 S/E

【要求】浏览器按 §3 S1～S8 + E 边界点一遍 · 填 §8 试跑记录 · 口头「G-2 验收 ✅」

【验收】S/E 勾选 · A 层 pytest 30 + golden 12/12 + build 绿 · cockpit G-2 整线 ✅
```
