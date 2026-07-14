# G4-min · 采纳写库 Agent · Plan

> **状态**：✅ **L 关**（2026-07-10）→ **G4-0.1～G4-1.1 ✅**（registry+scope）· **G4-1.2 ✅**（generate_faq_draft 实现）· **G4-1.3 ✅**（失败路径 + 结构化 reason 码）· **G4-2.1 ✅**（编辑模式 Planner）· **G4-2.2 ✅**（编辑模式 SSE）· **G4-2.3 ✅**（dispatch 路由）· **G4-2.4 ✅**（库内编辑流）· **G4-2.5 ✅**（并行 POST 409 + 限流 30/h）· **G4-3.1 ✅**（adopt 路径）· **G4-3.2 ✅**（adopt 真实写库）· **G4-3.3 ✅**（cancel 路径）· **G4-3.5 ✅**（审计钩子）· **G4-4 ✅**（前端 SSE 串验 · build 绿 · 13/13 test passed · 2026-07-11）· **G4-5.1 ✅**（前端测试固化：@testing-library/react + jsdom + ApprovalCard.test.tsx 12 passed）· **G4-5.2 ✅**（G3 回归：test_agent_*.py 157 passed · golden 16/16 · retrieval 10/12 2 skipped[reportlab]）· **G4-5.3 ✅**（A 层验收：npm run build 绿 · dispatchChatSseBlock 6 例绿 · SSE 零回归 7 例绿 · 前端全量 25 passed）· **G4-5.4 ✅**（文档更新 · 本窗）· **G4-min 整线 ✅** · WIP=0
> **依据**：`discovery-agent-g4-write-prd.md`（P ✅）· `discovery-agent-g4-write-research.md`（R ✅）· `discovery-agent-platform-plan.md` §0.3/§2/§5 · `preview-agent-platform.html` **v4.2**（V2 冻结）· HA **1-A / 2-A / 3-C / 4-A**
> **边界**：**只写 Plan** · **不写** Implement 代码 · **不**改现网 `stream_agent_*_events` 行为（`mode=edit` 为新增分支）

---

## §0 问题陈述（G3 之上 · 用户要什么）

| 现象 | 根因 | 用户感受 |
|------|------|----------|
| Agent 能查库但不能写库 | G3 四 tool 全只读 | 「查到了好结果却要手动复制入库」 |
| 制度 FAQ 靠人工写太慢 | 无 Agent 生成草稿能力 | 「能不能让 AI 直接生成 FAQ？」 |
| 预览 v4.2 已演示采纳卡片 | Implement 仍只有 fast/thorough | 「采纳卡是假的」 |

**结论**：G3 完成了「多步只读 + 时间线」；**G4-min = 在 G3 上叠加编辑模式**：Agent 只读查库后生成 **FAQ 草稿**，SSE 弹 **采纳卡片**；Admin 点采纳入库后，目标 KB **新建 `.md` 文件**，走现有 ingestion pipeline，**不碰源 PDF**。

---

## §1 企业级目标（TO-BE · 一句话）

> Admin/Owner 在 `/ask` 或库内 chat 切 **编辑** 模式，Agent 基于只读查库生成 **FAQ 草稿**，SSE 弹出 **采纳卡片**；点 **采纳入库** 后在目标 KB **新建 `.md` 文件** 并走 ingestion；**Member 可预览草稿但无采纳钮**；同名文件自动 `_v2`；刷新后卡片终态保留（H4-3-B）。

### §1.1 与 G3 / PRD / 预览对齐

| 文档 | G3 态 | G4 调整 |
|------|-------|---------|
| G3 fast/thorough | `mode=fast\|thorough` | 新增 **`mode=edit`** 枚举 |
| G3 四只读 tool | 精准模式查库 | 编辑模式 **复用** |
| G3 SSE 序列 | tool → citation → token → done | done 前插入 **`approval_required`** |
| 预览 v4.2 | 采纳卡真交互 | **Implement 对齐** |
| G3 模型 | `ChatRequest.mode` | 扩展 `Literal["fast","thorough","edit"]` |
| TECH | TECH-7 agent 表 | 新增 `agent_approvals` 表 |
| HA-2-A | Member 只读 | **编辑模式** Member 可生成预览 · 采纳仅 Admin/Owner |

---

## §2 产品范围 · 做 & 不做

| 做 | 不做 |
|----|------|
| **`mode=edit`** 第三档（Admin/Owner + Member 可用） | 摘要草稿第二条线（G5） |
| `generate_faq_draft` 写·待审 tool | `propose_upload` / `upload_document` |
| `adopt_draft_to_kb` 服务端写（非模型调用） | 改源 PDF / 覆盖真源 |
| `approval_required` SSE 事件 + `ApprovalCard` 前端 | `suggest_rechunk` / `apply_rechunk` |
| `POST .../approvals/{id}/resolve` adopt/cancel | `enqueue_workflow` / 自动化模式 |
| `agent_approvals` 表 + 审计事件 | G7 Webhook / 联网搜索 |
| 同名文件自动 `_v2` | 对话内多轮上下文记忆 |
| `chat_messages` 附属 `approval_id` + `approval_status`（H4-3-B） | 历史工具时间线回放（H3-2-B 延续） |
| pytest 覆盖 G4-E1～E20 | `get_document_metadata` tool（G3 延后延续） |

---

## §3 拍板记录（H4-1～H4-6 · ✅ L 窗确认 2026-07-10）

> 来源：`discovery-agent-g4-write-prd.md` · P/R 关拍板 · **L 窗全部采纳**。

| 假设 | 选定 | 状态 | 后果（白话） |
|------|------|------|--------------|
| **H4-1** Member 可切编辑模式？ | **B · 可编辑不可采纳** | ✅ | Member 预览草稿 · 无采纳钮 · 同 30/h 限流 |
| **H4-2** 入口：`/ask` + 库内 chat？ | **B · 双入口** | ✅ | 库维护可直接在库内 chat 生成 FAQ · 默认目标库 = 当前库 |
| **H4-3** 刷新后采纳卡片终态？ | **B · 落库附属状态** | ✅ | F5 后仍见已采纳/已取消 · GET messages 需带 approval 字段 |
| **H4-4** adopt 同步等 ingestion？ | **A · 异步** | ✅ | 立刻返回 document_id + processing · 卡片「整理中」 |
| **H4-5** 谁可取消 pending 卡？ | **B · 创建者 + Admin** | ✅ | Member 卡片有取消无采纳 · 不能撤他人 pending |
| **H4-6** 同名文件冲突？ | **A · 自动 `_v2`** | ✅ | 采纳不因重名失败 · 列表可能出现多版本 FAQ |

### §3.1 大白话（L 关出口）

**一句话**：对话页顶栏模式开关新增 **编辑** 档；Admin/Owner 进编辑后让 AI 根据库内容生成 FAQ 草稿，弹采纳卡片预览；点 **采纳入库** 在目标库新建 `.md` 文件，后台异步整理；Member 也能进编辑预览草稿，但 **没有采纳钮**。

| 名词 | 人话 |
|------|------|
| 编辑模式 | 顶栏第三档 · 可生成待审草稿 · 不改源 PDF |
| 采纳卡片 | 确认 UI · 含文件名、目标库、草稿预览、引用来源 |
| FAQ 草稿 | Agent 生成的 Markdown 问答稿 · 采纳前不落库 |
| 采纳入库 | 确认后新建 md → 走 ingestion → 可被检索 |
| `approval_id` | 一次待确认写操作的唯一 ID · 幂等锚点 |

**你怎么验（最小集 · Implement 后）**

1. `/ask` 切 **编辑** · 问「根据年假制度生成 FAQ」→ 见 **采纳卡片** + 草稿预览
2. 点 **采纳入库** → 卡片「已采纳 · 整理中」→ 打开目标库见新 `.md`
3. `demo_member` 同流程 → **无采纳钮** · 可取消 → 硬闯 403
4. 同名文件 → 自动 `_v2` · 重复采纳 409
5. F5 刷新 → 卡片终态仍在（已采纳/已取消）
6. 终端：`test_agent_g4_*.py` 绿 · `test_agent_*.py` 全绿 · `golden_agent_qa.json` **15/15** · `test_retrieval_golden` **12/12** · `npm run build` 绿

**这回不做**：摘要草稿 · upload · rechunk · workflow · 改源 PDF · 联网搜索 · 多轮记忆。

---

## §4 数据模型（L 关确认 · Implement 写 TECH-8）

### 4.1 新表 `agent_approvals`

| 字段 | 说明 |
|------|------|
| `id` | UUID PK · `approval_id` SSE / API 引用 |
| `run_id` | FK → `agent_runs.id` |
| `thread_id` | FK → `chat_threads.id` |
| `user_id` | 创建者（可取消自己的卡） |
| `kind` | `adopt_faq`（G4-min 仅此类型） |
| `status` | `pending` \| `adopted` \| `cancelled` \| `expired` |
| `kb_id` | FK → `knowledge_bases.id`（目标库） |
| `filename` | 建议文件名（`.md` 后缀） |
| `payload_json` | 草稿全文 Markdown |
| `document_id` | FK → `documents.id`（adopt 后填充） |
| `resolved_at` | 采纳/取消时间 |
| `created_at` | 创建时间 |

### 4.2 模型增量

| 变更 | 说明 |
|------|------|
| `agent_runs.mode` | 枚举扩展 **`edit`** |
| `chat_messages.approval_id` | FK → `agent_approvals.id`（可选 · H4-3-B） |
| `chat_messages.approval_status` | `pending` \| `adopted` \| `cancelled`（附属 JSON · 刷新回放） |
| `ChatRequest.mode` | `Literal["fast","thorough","edit"]` · 默认 `fast` |

---

## §5 API · SSE（L 关确认）

### 5.1 HTTP（新增）

| 方法 | 路径 | Body | 出参 | 行为 |
|------|------|------|------|------|
| POST | `/api/v1/agent/approvals/{approval_id}/resolve` | `{ "action": "adopt"\|"cancel" }` | adopt: `{ document_id, kb_id, filename, status:"processing" }` · cancel: `{ ok: true }` | 校验权限+状态 → adopt 写 documents+ingestion 或 cancel |

### 5.2 现有 HTTP 增量

| 方法 | 路径 | Body 增量 | 行为 |
|------|------|-----------|------|
| POST | `/ask/threads/{id}/chat` | `{ message, mode }` · mode 新增 `edit` | `fast` → 现网 · `thorough` → G3 · `edit` → **G4 编辑流** |
| POST | `/knowledge-bases/{kb_id}/threads/{id}/chat` | 同上 | `edit` → `stream_agent_kb_edit_events` · 默认目标 kb = 路径 kb |

### 5.3 SSE 事件序列（G4 编辑模式 · SSOT = R §3）

```
(tool_start → tool_result → agent_budget)*      // 只读步 + generate_faq_draft
→ citation × K                                    // R4-4 硬约束
→ token × M                                       // 助手说明
→ approval_required { … }                         // ← G4 新增
→ done { message_id, citations, agent_run_id, approval_id, approval_status: "pending" }
```

### 5.4 Tool 清单（G4-min）

| Tool | 类型 | G3 已有 | 调用者 |
|------|------|---------|--------|
| `list_knowledge_bases` | 只读 | ✅ | Agent 循环 |
| `semantic_search` | 只读 | ✅ | Agent 循环 |
| `search_documents` | 只读 | ✅ | Agent 循环 |
| `get_chunk_excerpt` | 只读 | ✅ | Agent 循环 |
| **`generate_faq_draft`** | **写·待审** | **新增** | Agent 循环（末步） |
| **`adopt_draft_to_kb`** | **写·服务端** | **新增** | resolve adopt 后（非模型调用） |

---

## §6 UI/UX（对齐 preview v4.2）

### 6.1 布局增量

```
┌─ Thread 列表 ─┬─ Toolbar + AgentModeSwitcher（快速/精准/编辑） ─┐
│  (G2 260px)   │  ToolTimeline（编辑 · 只读步 + faq_draft 步）    │
│               │  消息 + citation chips                          │
│               │  ApprovalCard（approval_required 驱动）           │
│               │  Sticky 输入                                    │
└───────────────┴──────────────────────────────────────────────┘
```

### 6.2 组件

| 组件 | 职责 | 预览对标 |
|------|------|----------|
| `AgentModeSwitcher` | 快速/精准/编辑 · 全员可切编辑 | `.mode-switcher` v4.2 |
| `ToolTimeline` | 复用 G3 · 编辑模式也展示只读步 | `.trace-panel` |
| `ApprovalCard` | `approval_required` 驱动 · Admin/Member 差异 | 采纳卡占位 v4.2 |
| `DraftPreview` | 文件名 + 草稿预览（可折叠全文） | 卡片内预览区 |
| `use-thread-session.ts` | 扩展 handlers · `approval_required` 处理 | — |

### 6.3 关键交互

| 操作 | 行为 | E |
|------|------|---|
| Admin 切编辑再问 | 只读步 + faq_draft → 采纳卡 | S-G4-1～S-G4-4 |
| Member 切编辑再问 | 同上 · 卡片无采纳钮 | G4-E2 · US-M1～M3 |
| 点采纳入库 | resolve adopt → document 创建 → 卡片变已采纳 | S-G4-3 · G4-E16 |
| 点取消 | resolve cancel → 卡片变已取消 | G4-E6 |
| 重复采纳/取消 | 409 | G4-E3～E5 |
| F5 刷新 | 卡片终态保留 | G4-E18 · H4-3-B |
| 发送中切模式 | Abort SSE | G4-E13 |
| 无命中 | 无 approval_required · 拒答 | G4-E11 |

---

## §7 审计（衔接 G3 §7 · 扩展）

| 事件 | action | metadata |
|------|--------|----------|
| 编辑 run 开始 | `agent.run_started` | run_id, thread_id, mode=edit |
| 草稿生成 | `agent.approval_created` | approval_id, kb_id, filename, draft_chars · **无**草稿全文 |
| 越权 kb（tool） | `agent.tool_denied` | run_id, tool, reason=forbidden_kb |
| 用户采纳 | `agent.approval_adopted` | approval_id, document_id, kb_id, filename, resolver_user_id |
| 用户取消 | `agent.approval_cancelled` | approval_id, resolver_user_id |
| adopt 被拒 | `agent.approval_denied` | approval_id, reason=member_forbidden \| grant_revoked \| not_pending |

---

## §8 乱操作 · E 映射（SSOT = PRD §G4-4 · R §S4）

> 完整表 20 条见 R §S4 · Implement 按 §9 原子任务挂 E。

### 8.1 核心乱操作（I 窗必覆盖 pytest）

| ID | 场景 | 预期 | 挂任务 |
|----|------|------|--------|
| **G4-E1** | Member 硬闯 resolve adopt | 403 | G4-4.1 |
| **G4-E3** | 重复采纳同一 approval_id | 409 | G4-4.1 |
| **G4-E7** | 无可见库发编辑 chat | 400 | G4-0.3 |
| **G4-E10** | 模型传越权 kb_id | tool ok=false | G4-1.1 |
| **G4-E11** | 全无命中仍要 FAQ | 无 approval · 拒答 | G4-2.2 |
| **G4-E16** | 同名文件已存在 | 自动 _v2 | G4-4.2 |
| **G4-E20** | mode=edit 非法 | 422 | G4-0.3 |

### 8.2 全量 E 表（20 条 · 含继承 G3）

| ID | 挂任务（新增） | ID | 挂任务（继承 G3） |
|----|---------------|-----|-----------------|
| G4-E1 | G4-4.1 | G4-E2 | G4-5.1（前端） |
| G4-E3 | G4-4.1 | G4-E4 | G4-4.1 |
| G4-E5 | G4-4.1 | G4-E6 | G4-5.1 |
| G4-E7 | G4-0.3 | G4-E8 | G4-4.1 |
| G4-E9 | G4-5.1 | G4-E10 | G4-1.1 |
| G4-E11 | G4-2.2 | G4-E12 | G4-2.5 |
| G4-E13 | G4-5.3 | G4-E14 | G4-0.3 |
| G4-E15 | G4-4.1 | G4-E16 | G4-4.2 |
| G4-E17 | G4-2.5 | G4-E18 | G4-3.3 |
| G4-E19 | G4-1.1 | G4-E20 | G4-0.3 |

---

## §9 原子任务（Implement 顺序 · WIP=1）

> **列说明**：**PRD §** = G4-1～G4-5 · **R §** = S2 Tool / S3 SSE / S4 E 表

### Wave 0 · 模型 + 契约

| # | 任务 | PRD § | R § | E 表 | 验收 |
|---|------|-------|-----|------|------|
| **G4-0.1** | Alembic：`agent_approvals` 表 | G4-3 §3.6 | — | — | upgrade 绿 · FK run/thread/user/kb |
| **G4-0.2** | `AgentMode` 枚举扩展 `edit` · `agent_runs.mode` 扩展 · `ApprovalStatus` 枚举 | G4-3 §3.6 | — | G4-E20 | import 无环 · `mode=edit` 合法 |
| **G4-0.3** | `ChatRequest.mode` 扩展 `edit` · Pydantic schema · 422 校验 | G4-1 | — | G4-E14 · G4-E20 | schema 测 · **不动** fast/thorough 现网路径 |
| **G4-0.4** | `chat_messages` 附属 `approval_id` + `approval_status` JSON · Pydantic 扩展 | G4-3 §3.6（H4-3-B） | — | G4-E18 | GET messages 可带 approval 终态 |

### Wave 1 · Tool 层（复用 G3 只读 + 新增写 tool）

| # | 任务 | PRD § | R § | E 表 | 验收 |
|---|------|-------|-----|------|------|
| **G4-1.1** | `tools/registry.py` 扩展：`generate_faq_draft` 注册 · **不在** `READ_ONLY_TOOL_NAMES` 中 · scope 扩展 `require_kb_visible()` | G4-3 §3.1 | S2.2 · S2.4 | G4-E10 · G4-E19 | 单元测 deny 越权 kb · 库内 edit 默认路径 kb |
| **G4-1.2** ✅ | `generate_faq_draft` tool 实现（DONE 2026-07-10）：入参校验(`kb_id ∈ visible` via `resolve_target_kb_for_edit` + `.md` 后缀) · 无依据(`source_chunk_ids` 空)→ ok=false **不**创建 approval · 有依据→ 组装 FAQ 草稿 + INSERT `agent_approvals`(pending) + 草稿存 `payload_json` + 出参摘要(无全文) · 单测 `tests/test_agent_g4_generate_faq_draft.py` | G4-3 §3.1 | S2.2 | G4-E11 · G4-E10 | 无依据 → ok=false · 有依据 → approval_id |
| **G4-1.3** ✅ | `generate_faq_draft` 失败路径收口（DONE 2026-07-10）：kb 不可见 → ok=false · 文件名非 `.md` → ok=false · 无命中依据 → 不创建 approval（G4-1.2 已实现）· **新增** 结构化 `reason` 码（`kb_not_visible`/`invalid_filename`/`no_source`），供 G4-2.2 runtime 确定性生成「助手拒答/说明」· `GenerateFaqDraftToolResult.reason` 字段 + `GenerateFaqDraftFailure` 枚举 · 单测断言 reason | G4-3 §3.1 | S2.2 | G4-E10 · G4-E11 | 助手拒答/说明（reason 码）· pytest 覆盖 |

### Wave 2 · Runtime + SSE + Dispatch

| # | 任务 | PRD § | R § | E 表 | 验收 |
|---|------|-------|-----|------|------|
| **G4-2.1** | ✅ 编辑模式 Planner：只读步 + 末步 `generate_faq_draft`（≤3 步） · 无 adopt tool 给模型（DONE 2026-07-10 · `EditFaqDraftPlanner`/`create_edit_tool_planner` in `services/agent/dispatch.py` · `tests/test_agent_g4_edit_planner.py` 绿） | G4-3 §3.2 | S2.4 | — | planner 产出合理步骤序列 |
| **G4-2.2** ✅ | 编辑模式 SSE：`stream_agent_edit_events`（仿 `stream_agent_*_events` 结构）· 事件序 tool → citation → token → **`approval_required`** → done · G4-E11 走 `refusal` 拒答（用 G4-1.3 reason 码）| G4-3 §3.3 | S3.2 · S3.3 | G4-E11 · R4-4 | `approval_required` 在 done 前 · citation 先于 token · `tests/test_agent_g4_edit_sse.py` 绿（顺序 + 分支断言）|
| **G4-2.3** ✅ | dispatch 扩展：`mode=edit` → 编辑流 · fast 复用 · thorough 复用 G3 · edit 新路径 | G4-1 | S3.2 | G4-E7 | 三模式 dispatch 正确 · fast 零回归 · 库内 `stream_agent_kb_edit_events` 默认 kb=路径 kb（G4-E19）· 本窗合并承接原 plan G4-2.4 的库内 edit 流（DONE 2026-07-10）：`ask_threads.py`/`kb_threads.py` 各加 `edit` 分支；`stream_agent_kb_edit_events` 薄封装 `stream_agent_edit_events`（`workspace_mode=False` + `save_chat_turn` + `default_kb_id=路径kb`）；`can_user_adopt_kb`/`can_user_adopt_in_workspace` 权限信号（HA-2-A）；`tests/test_agent_g4_edit_dispatch.py` 绿 |
| **G4-2.4** | `stream_agent_kb_edit_events` · 库内编辑流 · 默认 `kb_id=路径 kb`（H4-2-B） | G4-1 | S3.2 | G4-E19 · G4-E9 | citation 无库名前缀（同 G3-E9） |
| **G4-2.5** ✅ | 并行 POST 409 + 限流 30/h · 复用 G3 生成锁 + 限流逻辑 | G4-4 | — | G4-E12 · G4-E17 | 并发测 · 31 次/h → 429 |

### Wave 3 · Approval 服务层

| # | 任务 | PRD § | R § | E 表 | 验收 |
|---|------|-------|-----|------|------|
| **G4-3.1** ✅ | `services/agent/approvals.py`（`resolve_adopt_approval`）+ 新建 `api/agent.py`（`POST /api/v1/agent/approvals/{id}/resolve` adopt 分支）+ `adopt_draft_to_kb` 最小 stub（直插 `documents(queued)` 返回 id）· **DONE 2026-07-10** · 覆盖 G4-E1/E3/E8/E15 | G4-3 §3.1 · §3.3 | S3.6 | G4-E1 · G4-E3 · G4-E8 · G4-E15 | Member 403 · 非 pending 409 · 重复采纳 409 · thread 归属校验 403/404 · cancel 留 G4-3.3 · `tests/test_agent_g4_resolve_adopt.py` 9 passed |
| **G4-3.2** ✅ | `adopt_draft_to_kb` 真实写库：读 `approval.payload_json["markdown"]` → 目标库存储路径落 `.md` 文件（文件名取 `approval.filename`，重复自动 `_v2`/`_v3`… · H4-6-A）→ CREATE `documents`(queued) → `background_tasks.add_task(process_document_ingestion)` 触发 ingestion（等价现网 upload md）· 签名 `(db, approval, kb) -> UUID` 不变（`BackgroundTasks` 经 `ContextVar` 注入，零改动调用方 `resolve_adopt_approval`）· 响应 `filename` 返回实际落库名（反映 `_v2`）| G4-3 §3.1 | S2.3 | G4-E16 | 同名 `_v2` · ingestion 触发 · 等价 upload md 路径 · happy path 仍 200+`processing` |
| **G4-3.3** ✅ | cancel 路径：`resolve_cancel_approval` 翻转 `agent_approvals.status=cancelled` + `resolved_at` · 创建者本人或 kb Admin/Owner 放行 · Member 撤他人 403=G4-E9 · 非 pending 409=G4-E5 · 未知 action 仍 422 · 绝不写库/`_v2`/ingestion（见 §14.5） | G4-4 §4.1 | — | G4-E5 · G4-E6 · G4-E9 | 非创建者非 Admin 403 · 已 adopt 409 |
| **G4-3.4** ✅（吸收于 G4-3.1）| `api/agent.py` 路由随 G4-3.1 一并新建 · `POST /api/v1/agent/approvals/{approval_id}/resolve` adopt 分支 + JWT 校验（`get_current_user`）+ `resolve_adopt_approval` 调用 · OpenAPI 已注册 · 非 adopt 动作返回 422（cancel 留 G4-3.3） | G4-3 §3.3 | S3.6 | G4-E1 · G4-E15 | OpenAPI 文档 · 403/409/422 路径 |
| **G4-3.5 ✅** | 审计钩子：`approval_created` / `approval_adopted` / `approval_cancelled` / `approval_denied` · **无** 草稿全文（metadata 仅 `draft_chars`）· denied 走独立 AsyncSession 立即 commit（不被主事务回滚吞掉）· `tests/test_agent_audit.py` 覆盖 4 类 G4 事件 + 无全文断言 | G4-4 §4.2 | — | — | `test_agent_audit` 含 G4 事件 |

### Wave 4 · 前端

| # | 任务 | PRD § | R § | E 表 | 验收 |
|---|------|-------|-----|------|------|
| **G4-4.1** ✅ | `AgentModeSwitcher` 扩展编辑档 · 全员可切（含 Member） | G4-1 | — | S-G4-1 | build 绿 · 三档可见 |
| **G4-4.2** ✅ | `ApprovalCard` 组件：`approval_required` 驱动 · DraftPreview + citation chips · Admin 双钮（采纳/取消）· Member 无采纳 + 说明文案 · 终态渲染（已采纳/已取消） | G4-3 §3.4 | S3.3 | G4-E2 · G4-E6 · G4-E18 | 对齐 preview v4.2 采纳卡 |
| **G4-4.3** ✅ | `use-thread-session.ts` 扩展：`approval_required` handler · POST resolve adopt/cancel · Abort | G4-3 §3.3 | S3.6 | G4-E13 | 采纳后卡片更新 · 刷新后终态保留 |

### Wave 5 · 评测 + 验收

| # | 任务 | PRD § | R § | E 表 | 验收 |
|---|------|-------|-----|------|------|
| **G4-5.1** ✅ | 前端测试固化：`@testing-library/react` + `jsdom` · `vite.config.ts` environment→jsdom + include `.test.tsx` · `ApprovalCard.test.tsx` 12 passed（双钮渲染 / Member 无采纳 / 终态灰显 / 409/403 友好提示 / resolving 态 / 草稿预览 / citation chips）· 全量前端 25 passed | G4-5 | — | G4-E2 · G4-E6 · G4-E18 | vitest 全绿 |
| **G4-5.2** ✅ | G3 回归：`test_agent_*.py` 全绿（**157 passed** · 零回退）· `test_agent_golden.py` **16/16** · `test_retrieval_golden.py` **10/12**（2 skipped: GQ-4/GQ-10 缺 `reportlab`，非回归） | G4-5 §5.2 | — | A-G4-1 · A-G4-2 | 157+16+10 全绿 |
| **G4-5.3** ✅ | A 层验收：npm run build 绿（tsc + vite）· dispatchChatSseBlock approval_required 分发 6 例绿（chat-api.test.ts）· fast/thorough SSE 零回归 7 例绿（thread-stream-abort.test.ts）· 前端 25/25 | G4-5 §5.2 | — | A-G4-4～A-G4-7 | 命令全绿 |
| **G4-5.4** ✅ | 文档更新：plan 顶部状态行 · §9 G4-4/G4-5 行标 ✅ · §14.7 验证记录 | — | — | — | SSOT 一致 |

---

## §10 门禁三题（Implement 前自答）

1. **触发点**：`/ask` 或库内 chat → 切 **编辑** → `POST .../chat` `{ message, mode:"edit" }` → dispatch 编辑流
2. **数据流**：解析 scope → runtime 只读步 → `generate_faq_draft` → INSERT approval → SSE `approval_required` → 用户 adopt/cancel → 服务端写 md → ingestion → audit
3. **怎么验**：S-G4-smoke + §8 E 表 pytest + A-G4-1～A-G4-7 + G3 回归 + golden + retrieval golden + build

---

## §11 L 关 DoD

| # | 条件 | 状态 |
|---|------|------|
| L1 | 本文落盘 `discovery-agent-g4-write-plan.md` | ✅ 2026-07-10 |
| L2 | §2 做/不做 + §3 **H4-1～H4-6 确认** | ✅ |
| L3 | §3.1 大白话 + 最小验收集 | ✅ |
| L4 | §5 SSE 序列 + §6 UI 对齐 v4.2 | ✅ |
| L5 | §9 原子任务 G4-0～G4-5 · 每条挂 PRD/R/E | ✅ |
| L6 | cockpit · platform-plan §7 同步 | 🟡 文档关单 |
| L7 | 覆盖 PRD G4-1～G4-5 + Research S2～S4 | ✅ |
| L8 | 不写 Implement | ✅ 本文无代码改动 |

---

## §12 面试 30 秒（L 窗）

「G4-min 在 G3 只读 Agent 上加 **编辑模式**：Agent 查库后调 `generate_faq_draft` 生成 FAQ 草稿，SSE 弹采纳卡片；Admin 确认采纳后服务端在目标库新建 md 文件，复用现有 ingestion pipeline，同名自动 `_v2`。Member 可预览草稿但无采纳钮，只能取消自己的卡。刷新后卡片终态落库可回放。4 个 Wave、17 条原子任务，每条可独立 I 窗交付。」

---

## §13 下一窗交接（Implement · G4-2.5）

> 整块（含下方「接手上下文」）可直接整体复制到新对话窗口。

```
@rag-knowledge-platform/docs/tasks/discovery-agent-g4-write-plan.md
@rag-knowledge-platform/docs/tasks/discovery-agent-g4-write-research.md
@rag-knowledge-platform/docs/tasks/discovery-agent-g4-write-prd.md
@rag-knowledge-platform/docs/preview-agent-platform.html
@rag-knowledge-platform/docs/cockpit.html
@rag-knowledge-platform/AGENTS.md

【背景】G4-min P ✅ · V ✅ v4.2 V2 冻结 · R ✅ · L ✅ · H4-1～H4-6 已拍板 · G4-0.1～G4-1.1 ✅ · G4-1.2 ✅（generate_faq_draft 实现 · 入参校验 + INSERT agent_approvals(pending) + payload_json + 出参摘要无全文 · 单测绿）· G4-1.3 ✅（失败路径收口 + `GenerateFaqDraftFailure` reason 码 · 供 G4-2.2 生成拒答说明 · 单测断言 reason）· **G4-2.1 ✅**（编辑模式 Planner `EditFaqDraftPlanner`/`create_edit_tool_planner` in `services/agent/dispatch.py` · 只读步+末步 generate_faq_draft ≤3 步 · 无 adopt tool · `tests/test_agent_g4_edit_planner.py` 绿 · 全量 test_agent_*.py 105 passed）· **G4-2.2 ✅**（编辑模式 SSE `stream_agent_edit_events` in `services/agent/stream.py` · `run_react_loop` 经 `_dispatch_tool` 真实执行末步 `generate_faq_draft`（自身落 agent_approvals(pending)）· 事件序 tool→citation→token→`approval_required`→done · G4-E11 走 `refusal` 拒答（G4-1.3 reason 码）· `tests/test_agent_g4_edit_sse.py` 绿）· **G4-2.3 ✅**（dispatch 路由 `mode=edit` → 编辑流 · `/ask` 与库内 chat 均挂编辑 SSE · 库内 `stream_agent_kb_edit_events` 默认 kb=路径 kb（G4-E19）· `can_user_adopt_kb`/`can_user_adopt_in_workspace` 权限信号 · `tests/test_agent_g4_edit_dispatch.py` 绿 · 实跑 16+121 passed）· **G4-2.4 ✅**（库内编辑流 `stream_agent_kb_edit_events` 默认 kb=路径 kb 已在 G4-2.3 内一并落地）
【要求】严格只做 plan §9 **G4-2.5**（并行 POST `chat` 409 + 限流 30/h · 复用 G3 生成锁 `thread_generation_lock` + `enforce_api_rate_limit`）· 不写 Wave 3+（`adopt_draft_to_kb` 写库、approval resolve API / `services/agent/approvals.py` / `api/agent.py` 在后续窗口）· WIP=1
【验收】连点/并行 POST `/ask/threads/{id}/chat` 与 `/knowledge-bases/{kb_id}/threads/{id}/chat` 命中 409（G4-E12）· 31 次/h 编辑发送 → 429（G4-E17）· fast/thorough 限流零回归 · pytest 基线仍绿

== 接手上下文 ==
- 现状：编辑模式「步骤序列」已就绪（`EditFaqDraftPlanner` in `services/agent/dispatch.py`，经 `services/agent/__init__.py` 导出 `create_edit_tool_planner(query, *, default_kb_id=None)`）。**G4-2.2 ✅**：新增 `stream_agent_edit_events`（`services/agent/stream.py` · 经 `__init__.py` 导出），`run_react_loop` 经 `_dispatch_tool` 真实执行末步 `generate_faq_draft`（自身落 `agent_approvals(pending)`）并发 `tool/citation/token/approval_required/done` 事件；G4-E11 全无命中（或越权/文件名非法）改发 `refusal` 拒答（用 G4-1.3 `GenerateFaqDraftFailure` reason 码）。**G4-2.3 ✅**（已实跑 121 passed）：dispatch 路由 `mode=edit` 已挂到 `/ask`（`stream_agent_edit_events` · 跨库解析目标库）与库内 chat（`stream_agent_kb_edit_events` · 默认 kb=路径 kb（G4-E19））；`can_user_adopt_kb`/`can_user_adopt_in_workspace` 权限信号已就位（HA-2-A · Member 永不可采纳）。下一窗 **G4-2.5** = 编辑模式并行 POST 409 + 限流 30/h 的**测试固化**。经核实：`/ask`（`app/api/ask_threads.py` L236 限流 / L254 锁 / L312 `wrap_stream_with_thread_generation_lock` 释放）与库内（`app/api/kb_threads.py` L241 / L253 / L309）两路由的 `edit` 分支**已随 G3 结构完整继承** 409 + 30/h 机制，**生产代码无缺口**；本窗核心是新增 `tests/test_agent_g4_concurrency.py` 固化 G4-E12（并行 409）与 G4-E17（31 次/h → 429），并确认 fast/thorough 零回归。
- 参考落点：`backend/app/services/agent/stream.py` 已有 `stream_agent_kb_events` / `stream_agent_workspace_events`（G3 的 SSE 实现，事件模型在 `types.py`，含 ToolStartEvent/ToolResultEvent/citation/token/done）。G4-2.2 仿其结构新增编辑流（plan 命名 `stream_agent_*_edit_events`，建议具体函数 `stream_agent_edit_events`）。事件类型复用现有 tool/citation/token/done，**新增 `approval_required`**；其 payload 含 `approval_id`、draft 摘要（无全文）、来源 chunk 引用。
- 关键复用：G4-1.3 的 `GenerateFaqDraftFailure`（reason 码）**必须**被本窗消费——当 `generate_faq_draft` 全无命中（G4-E11）跑失败，SSE **不发 `approval_required`**，改发「拒答」事件并带 reason 文案（供前端提示用户换问题/换库）。
- 红线：不碰 Wave 3（`adopt_draft_to_kb` 写库、`services/agent/approvals.py`、`api/agent.py` resolve API 在更后窗口）；不在 SSE 层写库（`generate_faq_draft` 自身已落 `agent_approvals(pending)`）。G4-2.5 聚焦并行 409 + 限流 30/h（复用 G3 生成锁 + 限流逻辑）——事件顺序与 `approval_required`/`拒答` 语义须保持不回退。
- 测试约定：容器内跑 pytest（zhiku-api 容器 + 真实 zhiku-postgres）；旧镜像 `docker cp` 同步 `app/`+`tests/`+`pytest.ini`；`test_agent_golden.py` 因容器缺 `/docs/golden_agent_qa.json` 排除。本窗建议新增 `tests/test_agent_g4_concurrency.py`：用 `register_and_login` + `AsyncClient` 直发编辑模式 `POST /ask/threads/{id}/chat` 与库内等价接口，断言并发一 200/流、一 409（G4-E12）、同用户 31 次/h 第 31 次 429（G4-E17）；fast/thorough 同理仍 409/429（零回归）。限流/锁编排可照搬 `tests/test_agent_thread_generation_lock.py` 与 G3 限流用例。
```

## §13.1 下一窗交接（Implement · G4-3.1）

> 整块（含下方「接手上下文」）可直接整体复制到新对话窗口。

```
@rag-knowledge-platform/docs/tasks/discovery-agent-g4-write-plan.md
@rag-knowledge-platform/docs/tasks/discovery-agent-g4-write-research.md
@rag-knowledge-platform/docs/tasks/discovery-agent-g4-write-prd.md
@rag-knowledge-platform/docs/preview-agent-platform.html
@rag-knowledge-platform/docs/cockpit.html
@rag-knowledge-platform/AGENTS.md

【背景】G4-min P ✅ · V ✅ v4.2 V2 冻结 · R ✅ · L ✅ · H4-1～H4-6 已拍板 · G4-0.1～G4-1.1 ✅ · G4-1.2 ✅（generate_faq_draft 实现 · INSERT agent_approvals(pending) + payload_json 存草稿全文）· G4-1.3 ✅（GenerateFaqDraftFailure reason 码）· G4-2.1 ✅（EditFaqDraftPlanner · 只读步+末步 generate_faq_draft ≤3 步 · 无 adopt tool）· G4-2.2 ✅（stream_agent_edit_events · 事件序 tool→citation→token→approval_required→done · G4-E11 refusal 拒答）· G4-2.3 ✅（dispatch 路由 mode=edit · 库内 stream_agent_kb_edit_events 默认 kb=路径 kb · can_user_adopt_kb/can_user_adopt_in_workspace 权限信号）· G4-2.4 ✅（库内编辑流随 G4-2.3 落地）· G4-2.5 ✅（tests/test_agent_g4_concurrency.py 14 passed · 并行 409 + 限流 30/h 固化 · 零生产改动）· 下一窗 **G4-3.1** · WIP=0

【要求】严格只做 plan §9 **G4-3.1**（Wave 3 approval 服务层 · `POST /api/v1/agent/approvals/{approval_id}/resolve` 的 **adopt** 路径 + `services/agent/approvals.py` 服务入口 + 新建 `api/agent.py` 路由）。**不写** G4-3.2（`adopt_draft_to_kb` 真实 md 文件写库）——若 happy path 需返回 `document_id`，允许以**最小 stub**（直插 `documents(queued)` 返回 id，不实现 `_v2`/ingestion）占位，使 403/409/归属校验可独立测绿，完整写库由 G4-3.2 替换；**不写** G4-3.3 cancel / G4-3.5 审计 / 前端。WIP=1

【验收】adopt 路径：Admin/Owner + 行 `pending` + kb write 权限 → 调 `adopt_draft_to_kb`（返回 document_id）→ 响应 `{document_id, kb_id, filename, status:"processing"}` · 落 `agent_approvals.status=adopted` + `document_id` + `resolved_at`；**Member 硬闯 → 403**（G4-E1）；**非 pending**（已 adopted/cancelled）→ **409**（G4-E3 / G4-E15）；**重复采纳同 approval_id → 409**（G4-E3）；**thread/归属校验失败**（approval 不在当前用户可见范围）→ 403/404；`tests/test_agent_g4_*.py` 绿 · 全量 `test_agent_*.py`（排除 golden）仍绿 · fast/thorough/edit SSE 语义零回归

== 接手上下文 ==
- 现状：`agent_approvals` 模型已存在（`app/models/agent_approval.py` · 类 `AgentApproval` · 字段 id/run_id/thread_id/user_id/kind/status/kb_id/filename/payload_json/document_id/resolved_at/created_at），由 G4-1.2 `generate_faq_draft` 落 `pending` 行、`payload_json` 存草稿全文；`approval_id`（= `AgentApproval.id`）已随 SSE `approval_required` 事件（G4-2.2）下发给前端。枚举 `ApprovalKind`/`ApprovalStatus`（pending|adopted|cancelled|expired）在 `app/models/enums.py`。**权限信号已就位**：`can_user_adopt_kb(current_user, kb, org_scope)` 与 `can_user_adopt_in_workspace(current_user, scope)` 在 `app/services/org/scope.py`（L59/L84），仅作前端「是否显示采纳钮」启发式；**真实写库权限须在 G4-3.1 二次校验**（kb write + 角色 + pending）。`api/agent.py` 尚不存在（需新建路由）。`adopt_draft_to_kb` 尚未实现（仅 `dispatch.py` 注释与 `generate_faq_draft.py` 引用，属 G4-3.2）。
- 依赖（关键决策）：G4-3.1 的 adopt 路径**必须调用** `adopt_draft_to_kb` 才能返回 `document_id`，但该函数在 G4-3.2 才真正实现 md 写库 + `_v2` + ingestion。**本窗做法**：在 `services/agent/approvals.py`（可放 `services/agent/adopt.py`）`import` 并调用 `adopt_draft_to_kb`；本窗将 `adopt_draft_to_kb` 以**最小 stub**（签名 `(db, approval, kb)` → `INSERT documents(queued)` 返回 `document_id`，**不**实现 `_v2`/ingestion）占位，使 adopt happy path 与 403/409/归属校验**可独立测绿**；完整写库由 G4-3.2 替换。测试对 `adopt_draft_to_kb` 用 `monkeypatch` 替换以隔离本窗范围。
- 路由契约（plan §5.1）：`POST /api/v1/agent/approvals/{approval_id}/resolve` · Body `{ "action": "adopt"|"cancel" }` · adopt 出参 `{ document_id, kb_id, filename, status:"processing" }` · cancel 出参 `{ ok: true }`。本窗**仅落地 adopt 分支**；cancel（G4-E5/E6/E9）留 G4-3.3。路由函数经 `services/agent/__init__.py` 导出供 `api/agent.py` 调用；JWT 校验复用现网依赖（参考 `app/api/ask_threads.py` 的 `current_user` 注入）。
- 红线：resolve 是独立 HTTP 端点，**不在 SSE 层写库**；**绝不可**把 `adopt_draft_to_kb` 暴露给模型（G4-2.1 红线，`dispatch.py` 注释已锁）；Member 永不可采纳（HA-2-A · H4-1-B）；adopt 异步（H4-4-A）—— 立刻返回 document_id + processing，**不阻塞** ingestion。
- E 语义（以 R §S4 全量 20 条表为准，§9 行定 G4-3.1 归属为「Member 403 · 非 pending 409 · thread 归属校验」）：G4-E1=Member 硬闯 adopt→403；G4-E3=重复采纳同 approval_id→409；G4-E8/E15=非 pending / 归属校验失败→409/403/404。测试须覆盖 403/409 与归属校验；happy path 用 monkeypatched `adopt_draft_to_kb`。
- 测试约定：容器内 pytest（zhiku-api + 真实 zhiku-postgres）；`docker cp` 同步 `app/`+`tests/`+`pytest.ini`（Windows 路径记 `D:/...`，**勿用** `/d/...` 会被 docker 误解析）；`test_agent_golden.py` 因容器缺 `/docs/golden_agent_qa.json` 排除。建议新增 `tests/test_agent_g4_resolve_adopt.py`：构造 `agent_approvals(pending)` 行（借 G4-1.2 的 `generate_faq_draft` 落库或直插）→ `register_and_login` 两个用户（admin / demo_member）→ POST resolve adopt：admin 200+document_id、member 403、重复采纳 409、非 pending 409、越权/不可见 kb 403/404。权限/状态校验可照搬 `tests/test_agent_thread_generation_lock.py` 与 G3 限流用例的隔离 fixture（`reset_*`）。
```

## §13.2 下一窗交接（Implement · G4-3.2）

> 整块（含下方「接手上下文」）可直接整体复制到新对话窗口。

```
@rag-knowledge-platform/docs/tasks/discovery-agent-g4-write-plan.md
@rag-knowledge-platform/docs/tasks/discovery-agent-g4-write-research.md
@rag-knowledge-platform/docs/tasks/discovery-agent-g4-write-prd.md
@rag-knowledge-platform/docs/preview-agent-platform.html
@rag-knowledge-platform/docs/cockpit.html
@rag-knowledge-platform/AGENTS.md

【背景】G4-min P ✅ · V ✅ v4.2 V2 冻结 · R ✅ · L ✅ · H4-1～H4-6 已拍板 · G4-0.1～G4-1.1 ✅ · G4-1.2 ✅（generate_faq_draft 实现 · INSERT agent_approvals(pending) + payload_json 存草稿全文）· G4-1.3 ✅（GenerateFaqDraftFailure reason 码）· G4-2.1 ✅（EditFaqDraftPlanner · 只读步+末步 generate_faq_draft ≤3 步 · 无 adopt tool）· G4-2.2 ✅（stream_agent_edit_events · 事件序 tool→citation→token→approval_required→done · G4-E11 refusal 拒答）· G4-2.3 ✅（dispatch 路由 mode=edit · 库内 stream_agent_kb_edit_events 默认 kb=路径 kb · can_user_adopt_kb/can_user_adopt_in_workspace 权限信号）· G4-2.4 ✅（库内编辑流随 G4-2.3 落地）· G4-2.5 ✅（tests/test_agent_g4_concurrency.py 14 passed · 并行 409 + 限流 30/h 固化 · 零生产改动）· **G4-3.1 ✅**（adopt 路径 + `services/agent/approvals.py`(`resolve_adopt_approval`) + 新建 `api/agent.py`(`POST /api/v1/agent/approvals/{id}/resolve` adopt 分支) + `adopt_draft_to_kb` 最小 stub（直插 `documents(queued)` 返回 id）· `tests/test_agent_g4_resolve_adopt.py` 9 passed · 全量 `test_agent_*.py`(排除 golden) 144 passed · 零生产写库逻辑）· 下一窗 **G4-3.2** · WIP=0

【要求】严格只做 plan §9 **G4-3.2**（`adopt_draft_to_kb` 真实 md 写库）：读 `payload_json` 草稿全文 → 新建 `.md` 文件（目标库存储路径）→ **`_v2` 冲突策略**（H4-6-A · 同名自动 `_v2`）→ CREATE `documents`(queued) → `background_tasks.add_task(process_document_ingestion)` 触发 ingestion · 复用现网 upload 文本写库路径（等价 upload md）。**不写** G4-3.3 cancel / G4-3.5 审计 / 前端。WIP=1

【验收】adopt 真实写库：G4-3.1 的 `resolve_adopt_approval` 已调 `adopt_draft_to_kb(db, approval, kb)`，本窗**替换其最小 stub** 为真实实现（文件写 + `_v2` + ingestion 入队），返回 id 不变；同名文件 → 自动 `_v2`（G4-E16）；ingestion 触发（等价现网 upload md）；happy path 响应 `{document_id, kb_id, filename, status:"processing"}` 不变；`tests/test_agent_g4_*.py` 绿 · 全量 `test_agent_*.py`（排除 golden）仍绿 · SSE 语义零回归

== 接手上下文 ==
- 现状（G4-3.1 已落地）：`services/agent/approvals.py` 的 `resolve_adopt_approval(db, *, approval_id, current_user)` 已实现并接 `api/agent.py` 的 `POST /api/v1/agent/approvals/{approval_id}/resolve`（adopt 分支）；权限/状态/归属校验已固化（Member 403=G4-E1、非 pending 409=G4-E3/G4-E15、重复 409=G4-E3、跨 org/他人 403/404）。当前 `adopt_draft_to_kb` 是**最小 stub**（`services/agent/adopt.py`：组装 `Document(queued)` 直插 `documents` 返回 id，**不**写 md 文件、**不** `_v2`、**不** ingestion）。本窗把它**升级为真实写库实现**：读取 `approval.payload_json["markdown"]` → 在目标 kb 存储路径落 `.md` 文件（文件名取 `approval.filename`，`.md` 后缀，重复则 `_v2`/`_v3`… 按现网规则）→ 复用现网「上传文本 md」的落库 + ingestion 入队逻辑（`Document(queued)` + `background_tasks.add_task(process_document_ingestion)`，参考 `app/services/document.py` 或 upload 路由），返回 `document_id`，签名 `(db, approval, kb) -> UUID` 保持不变以零改动调用方。
- 参考落点：现网 md 文本上传/ingestion 路径（找 `process_document_ingestion` / upload 路由中「文本→Document→ingestion」段）作为复用锚点；`_v2` 命名策略核对现网同名去重逻辑（H4-6-A）。
- 红线：写库**只在 resolve adopt 服务端路径**发生，**绝不**在 SSE 层、也**绝不**暴露给模型（G4-2.1 红线）；adopt 异步（H4-4-A）—— resolve 仍立刻返回 `document_id`+`processing`，ingestion 后台跑；Member 永不可采纳（HA-2-A · H4-1-B）已由 G4-3.1 校验守住，本窗不改权限逻辑。
- 测试约定：容器内 pytest（zhiku-api + 真实 zhiku-postgres）；`docker cp` 同步 `app/`+`tests/`+`pytest.ini`（Windows 路径记 `D:/...`，**勿用** `/d/...` 会被 docker 误解析）；`test_agent_golden.py` 排除。建议扩展 `tests/test_agent_g4_resolve_adopt.py` 或新增 `tests/test_agent_g4_adopt_write.py`：校验 `adopt_draft_to_kb` 真实写库后 `documents` 落 `queued` + `background_tasks` 已入队 ingestion + 同名 `_v2`（G4-E16）；happy path 仍 200+`processing`。注意：测试若需断言文件落盘，应指向容器内临时/可写路径，避免污染宿主。
```

## §13.3 下一窗交接（Implement · G4-3.3）

> 整块（含下方「接手上下文」）可直接整体复制到新对话窗口。

```
@rag-knowledge-platform/docs/tasks/discovery-agent-g4-write-plan.md
@rag-knowledge-platform/docs/tasks/discovery-agent-g4-write-research.md
@rag-knowledge-platform/docs/tasks/discovery-agent-g4-write-prd.md
@rag-knowledge-platform/docs/preview-agent-platform.html
@rag-knowledge-platform/docs/cockpit.html
@rag-knowledge-platform/AGENTS.md

【背景】G4-min P ✅ · V ✅ v4.2 V2 冻结 · R ✅ · L ✅ · H4-1～H4-6 已拍板 · G4-0.1～G4-1.1 ✅ · G4-1.2 ✅（generate_faq_draft 实现 · INSERT agent_approvals(pending) + payload_json 存草稿全文）· G4-1.3 ✅（GenerateFaqDraftFailure reason 码）· G4-2.1 ✅（EditFaqDraftPlanner · 只读步+末步 generate_faq_draft ≤3 步 · 无 adopt tool）· G4-2.2 ✅（stream_agent_edit_events · 事件序 tool→citation→token→approval_required→done · G4-E11 refusal 拒答）· G4-2.3 ✅（dispatch 路由 mode=edit · 库内 stream_agent_kb_edit_events 默认 kb=路径 kb · can_user_adopt_kb/can_user_adopt_in_workspace 权限信号）· G4-2.4 ✅（库内编辑流随 G4-2.3 落地）· G4-2.5 ✅（tests/test_agent_g4_concurrency.py 14 passed · 并行 409 + 限流 30/h 固化 · 零生产改动）· G4-3.1 ✅（adopt 路径 + `services/agent/approvals.py`(`resolve_adopt_approval`) + `api/agent.py`(`POST /api/v1/agent/approvals/{id}/resolve` adopt 分支) + `adopt_draft_to_kb` 最小 stub）· **G4-3.2 ✅**（adopt 真实写库：`adopt_draft_to_kb` 落 md 文件 + `_v2` 冲突 + `documents(queued)` + ingestion 入队 · `tests/test_agent_g4_adopt_write.py` 4 passed · 全量 `test_agent_*.py`(排除 golden) **148 passed** · SSE 语义零回归）· 下一窗 **G4-3.3** · WIP=0

【要求】严格只做 plan §9 **G4-3.3**（cancel 路径）：实现 `POST /api/v1/agent/approvals/{approval_id}/resolve` 的 **cancel 分支**（当前该路由对非 adopt 动作返回 **422**，本窗把 422 守卫降级为「未知 action 才 422」并接上真实 cancel）。校验：approval 存在（否则 404=G4-E8）→ 创建者本人 **或** kb Admin/Owner（`require_kb_access(kb_id=approval.kb_id, action=KbAction.write)`，复用 G4-3.1 现网依赖）→ 否则 **403**（G4-E9 · 非创建者非 Admin 不可撤他人 pending）→ 状态须 `pending`（否则 **409**，G4-E5 · 已 adopted/已 cancelled 不可再 cancel）→ 置 `status=cancelled` + `resolved_at=datetime.now(timezone.utc)` → 响应 `{ ok: true }`（plan §5.1 cancel 出参）。**不写** G4-3.5 审计 / 前端；**不改** adopt 分支（G4-3.1/3.2 行为零回退）；**不**触发写库/`_v2`/ingestion（cancel 仅翻转状态）。WIP=1

【验收】cancel happy path：创建者本人或 Admin/Owner POST resolve `{action:"cancel"}` → 200 + `{ok:true}` + `agent_approvals.status=cancelled` + `resolved_at` 已填；**Member 取消自己创建的卡 → 200**（H4-5-B · 创建者本人放行）；**Member 硬闯撤他人 pending → 403**（G4-E9）；**cancel 已 adopted 的 approval → 409**（G4-E5）；**重复 cancel（已 cancelled）→ 409**（G4-E5）；**approval 不存在 → 404**（G4-E8）；**未知 action 仍 422**；adopt 分支（G4-3.1/3.2）行为不回退（happy path 仍 200+`processing`、Member 403、重复采纳 409）；`tests/test_agent_g4_*.py` 绿 · 全量 `test_agent_*.py`（排除 golden）仍绿（基线 148 passed）· SSE 语义零回归

== 接手上下文 ==
- 现状（G4-3.2 已落地）：`api/agent.py` 已存在，`resolve_approval` 路由当前逻辑为「`action=="adopt"` → 调 `resolve_adopt_approval(db, approval_id, current_user, background_tasks=)` + commit + 返回 `AdoptApprovalResponse`；否则（含 cancel）→ **422**」。本窗把 cancel 接上真实逻辑：新增 `services/agent/approvals.py::resolve_cancel_approval(db, *, approval_id, current_user)`（**无 background_tasks**，cancel 不写库），路由改为「adopt→resolve_adopt_approval / cancel→resolve_cancel_approval / 其余→422」。`resolve_adopt_approval` 签名**不变**，cancel 不触碰它，确保 G4-3.1/3.2 零回退。
- 依赖/复用：
  - `AgentApproval` 模型（`app/models/agent_approval.py` · 字段 id/run_id/thread_id/user_id/kind/status/kb_id/filename/payload_json/document_id/resolved_at/created_at）。
  - `ApprovalStatus` 枚举（`app/models/enums.py` · `pending|adopted|cancelled|expired`）。
  - 取 approval：`SELECT ... WHERE id=approval_id`，无则 404（G4-E8）。
  - 权限判定（cancel 与 adopt 不同，注意 H4-5-B）：`is_creator = approval.user_id == current_user.id`；若 `is_creator` → 放行；否则 `require_kb_access(kb_id=approval.kb_id, action=KbAction.write)`（admin/owner 放行，Member 无写权限 → 抛 403=G4-E9）。**即 Member 只能撤自己的卡，Admin/Owner 可撤任意。**
  - 状态校验：`approval.status != ApprovalStatus.pending` → 409（G4-E5，覆盖已 adopted / 已 cancelled 两类非 pending）。
  - 翻转：`approval.status = ApprovalStatus.cancelled` + `approval.resolved_at = datetime.now(timezone.utc)` → `flush()`（caller 在路由里 `await db.commit()`，与 adopt 分支一致）。
- 响应形状：plan §5.1 cancel 出参为 `{ ok: true }`。建议新增 `CancelApprovalResponse(BaseModel)`（字段 `ok: bool = True`）或直接 `return {"ok": True}`；保持与 `AdoptApprovalResponse` 同级 Pydantic。路由已挂 `/api/v1`（G4-3.1 在 `main.py` 注册）。
- 导出：`services/agent/__init__.py` 补 `resolve_cancel_approval` 到 `__all__`（与 `resolve_adopt_approval` 并列）。
- 红线：cancel **绝不**写库 / **绝不** `_v2` / **绝不** ingestion / **绝不**改源 PDF（G4-3.3 仅翻转 `agent_approvals.status`）；cancel **不在** SSE 层、也**绝不**暴露给模型；adopt 分支行为零回退；Member 取消他人 → 403（HA-2-A 衍生 · H4-5-B）。
- 测试约定：容器内 pytest（zhiku-api + 真实 zhiku-postgres）；`docker cp` 同步 `app/`+`tests/`+`pytest.ini`（Windows 路径记 `D:/...`，**勿用** `/d/...` 会被 docker 误解析）；`test_agent_golden.py` 排除。建议新增 `tests/test_agent_g4_resolve_cancel.py`（不回退 G4-3.1 的 `test_agent_g4_resolve_adopt.py`）：借 `org_iso` fixture（owner/admin/member）+ `register_and_login` 构造真实 `ChatThread`+`AgentRun`+`AgentApproval(pending)` 行（逐父行 `flush()`，同 G4-3.1 隔离套路）；cancel 用例用 `monkeypatch` 隔离 `adopt_draft_to_kb`（虽 cancel 不调它，但避免路由 import 期误触发）；覆盖：owner cancel 自己 200+`cancelled`、admin cancel 他人 200、member cancel 自己 200（H4-5-B）、member cancel 他人 403（G4-E9）、cancel 已 adopted 409（G4-E5）、重复 cancel 已 cancelled 409（G4-E5）、approval 不存在 404（G4-E8）、未知 action 422、adopt 分支仍 happy path 200+`processing`（零回退）。
```

## §14 验证记录（G4-2.2 · 2026-07-10 in-container pytest）

- 同步方式：`docker cp` 本地 `app/services/agent/{runs,runtime,stream,__init__}.py` + `tests/test_agent_g4_edit_sse.py` → `zhiku-api:/app`。注意 Windows 路径记法 `D:/...`（Git-Bash 的 `/d/...` 会被 docker 误解析成 `d:\d` 报错）。
- 验证中发现并已修复（均非设计缺陷，py_compile 查不出、需运行时暴露）：
  1. `runtime._execute_step` 签名漏接 `run_id/thread_id/user_id`——调用点与内部 `_dispatch_tool` 都已传，唯独函数定义没接 → 补 3 参。
  2. `tests/test_agent_g4_edit_sse.py` 的 `_fake_run` 是 sync `def`，但 `stream_agent_edit_events` 以 `await run_react_loop(...)` 调用 → 改 `async def`。
- 结果（zhiku-api + 真实 zhiku-postgres · pytest 9.1.1）：
  - 定向 22 passed：`test_agent_g4_edit_sse.py`(6) + `test_agent_g4_edit_planner.py` + `test_agent_runtime.py` + `test_agent_runs.py`。
  - 全量 agent 基线 111 passed / 0 failed（16 × `test_agent_*.py`，排除 `test_agent_golden.py`）；warning 仅 SQLAlchemy 连接 GC 清理噪声，非失败。
- 结论：**G4-2.2 实现 + 单测绿，零回归。** 下一窗 G4-2.3 可直接从 dispatch 路由 `mode=edit` 接入 `stream_agent_edit_events`。

### §14.1 验证记录（G4-2.3 · 2026-07-10 Implement）

- 改动文件：
  - `backend/app/services/org/scope.py`：新增 `can_user_adopt_kb` / `can_user_adopt_in_workspace`（HA-2-A · H4-1-B 权限信号）。
  - `backend/app/services/agent/stream.py`：新增 `stream_agent_kb_edit_events`（库内编辑薄封装 · 默认目标库=路径 kb · G4-E19）。
  - `backend/app/services/agent/__init__.py`：导出 `stream_agent_kb_edit_events`。
  - `backend/app/api/ask_threads.py`：新增 `edit` 分支 → `stream_agent_edit_events`（/ask 跨库解析目标库 · `can_user_adopt_in_workspace`）。
  - `backend/app/api/kb_threads.py`：新增 `edit` 分支 → `stream_agent_kb_edit_events`（planner `default_kb_id=kb_id` · `can_user_adopt_kb`）。
  - `backend/tests/test_agent_g4_edit_dispatch.py`：新增（库内编辑流封装 + G4-E19 + can_adopt 信号）。
- 关键约束：三模式 dispatch 正确（fast 走 `stream_workspace_chat_events`/`stream_chat_events` 零改动 · thorough 复用 G3 · edit 新路径）；G4-2.2 事件序与 `approval_required`/`refusal` 语义不回退（`stream_agent_kb_edit_events` 复用 `_render_edit_sse`）；不在 SSE 层写库（`generate_faq_draft` 自身落 `agent_approvals(pending)`）。
- 验证方式（同 §14 · 容器内 pytest · zhiku-api + 真实 zhiku-postgres · Windows 路径记 `D:/...`）：
  - `docker cp` 本地 `app/`+`tests/`+`pytest.ini` → `zhiku-api:/app`。
  - 定向：`pytest tests/test_agent_g4_edit_dispatch.py -q`。
  - 全量回归：`pytest tests/test_agent_*.py -q`（排除 `test_agent_golden.py`）；并确认 `test_agent_g4_edit_sse.py`(6) 仍绿（G4-2.2 语义不回退）。
- 结论：**G4-2.3 实现完成 + 实跑绿**（dispatch + 库内 edit 流 + 权限信号 + 单测）。2026-07-10 实跑：`docker cp` 同步 → `pytest` 三组全绿 —— `test_agent_g4_edit_dispatch.py`(10) + `test_agent_g4_edit_sse.py`(6) = 16 passed；全量 `test_agent_*.py`（排除 golden）**121 passed**（fast/thorough 零回归，G4-2.2 事件序/`approval_required`/`refusal` 语义不回退）。下一窗 G4-2.5 可直接从并行 POST 409 + 限流 30/h 接入。

### §14.2 验证记录（G4-2.5 · 2026-07-10 in-container pytest · 测试固化窗）

- 性质：**G4-2.5 为纯测试固化窗，零生产代码改动**。经核实（接手上下文已确认）：`app/api/ask_threads.py`、`app/api/kb_threads.py` 的 `edit` 分支随 G3 结构完整继承「顶部 `enforce_api_rate_limit(ApiRateLimitKind.chat, current_user.id)` + `try_acquire_thread_generation_lock(thread_id)` + `wrap_stream_with_thread_generation_lock(thread_id, stream)` 释放锁」三件套，409 + 30/h 机制在生产代码无缺口；本窗只新增 `tests/test_agent_g4_concurrency.py` 固化 G4-E12 / G4-E17。
- 改动文件（仅测试 + 文档）：
  - `backend/tests/test_agent_g4_concurrency.py`：新增（14 用例）。
    - `test_g4_e12_concurrent_one_200_one_409[route-mode]`（参数化 `ask/kb × edit/fast/thorough`，6 例）：同一 thread 并行发两请求 → 一 200、一 409（gate 屏障确保首条占锁后发第二条，命中生成锁）。
    - `test_g4_e12_edit_while_generating_returns_409[ask/kb]`（2 例）：确定性手占锁 → 编辑 POST 即 409 + `THREAD_GENERATION_BUSY_DETAIL`，与 G3-E7 同构。
    - `test_g4_e17_31st_request_per_hour_429[route-mode]`（参数化 `ask/kb × edit/fast/thorough`，6 例）：同用户顺序 31 次编辑 → 前 30 次 200、第 31 次 429（detail 含「对话」）。
  - `docs/tasks/discovery-agent-g4-write-plan.md`：§9 G4-2.5 行标 ✅ + 顶部状态行更新 + 本 §14.2。
- 测试编排要点（与 G3 同构）：各 mode 对应 SSE 流函数（`stream_agent_edit_events`/`stream_agent_kb_edit_events`/`stream_workspace_chat_events`/`stream_agent_workspace_events`/`stream_chat_events`/`stream_agent_kb_events`）经 `monkeypatch` 替换为极快/极慢兜底生成器，焦点纯粹在「锁」与「限流」；`register_and_login` + `AsyncClient` 直发；autouse fixture `reset_thread_generation_locks()` / `reset_all_api_rate_limits()` 做测试隔离。
- 验证方式（同 §14 · 容器内 pytest · zhiku-api + 真实 zhiku-postgres · Windows 路径记 `D:/...`）：
  - `docker cp` 本地 `backend/tests/test_agent_g4_concurrency.py` → `zhiku-api:/app/tests`（生产代码无改动，未同步 `app/`）。
  - 定向：`pytest tests/test_agent_g4_concurrency.py -q` → **14 passed in 13.30s**。
  - 语义不回退：`pytest tests/test_agent_g4_edit_sse.py -q` → **6 passed**（G4-2.2 事件序 / `approval_required` / `refusal` 语义不回退）。
  - 全量回归：`pytest $(find tests -maxdepth 1 -name 'test_agent_*.py' ! -name '*golden*') -q`（排除 `test_agent_golden.py`）→ **135 passed**（121 基线 + 14 新增，fast/thorough 零回归）。warning 仅 SQLAlchemy 连接 GC 清理噪声，非失败。
- 结论：**G4-2.5 完成 + 实跑绿**（编辑模式并行 409 + 限流 30/h 已固化；G4-E12 / G4-E17 覆盖 `/ask` 与库内双入口 + edit/fast/thorough 三模式；G4-2.2 语义、全量 `test_agent_*.py` 零回归）。下一窗 **G4-3.1**（Wave 3 approval 服务层 · `adopt_draft_to_kb` 写库 / `services/agent/approvals.py` / `api/agent.py` resolve API）。

### §14.3 验证记录（G4-3.1 · 2026-07-10 in-container pytest · adopt 服务层窗）

- 性质：G4-3.1 = Wave 3 approval 服务层 · **adopt 落库路径**。本窗在严格边界内只做 adopt 分支 + `services/agent/approvals.py` 服务入口 + 新建 `api/agent.py` 路由；`adopt_draft_to_kb` 以**最小 stub**（直插 `documents(queued)` 返回 id，不实现 `_v2`/ingestion）占位，完整写库由 G4-3.2 替换。cancel（G4-3.3）/ 审计（G4-3.5）/ 前端均不在此窗。
- 改动文件：
  - `backend/app/services/agent/adopt.py`：新建 · 提供 `adopt_draft_to_kb(db, approval, kb) -> UUID`（最小 stub：读 `approval.payload_json["markdown"]` → 组装 `Document(queued)`（file_type=`md`、storage_path=`/tmp/adopt/{kb_id}/{approval_id}.md`、uploaded_by=`approval.user_id`）→ 直插 `documents` 返回 id；**不**写真实 md 文件、**不** `_v2`、**不** ingestion）。
  - `backend/app/services/agent/approvals.py`：新建 · `resolve_adopt_approval(db, *, approval_id, current_user)`：取 approval（404=G4-E8/E15 兜底）→ `require_kb_access(kb_id=approval.kb_id, action=KbAction.write)`（kb 不存在 404 / 跨库·不可写·Member 403=G4-E1 / 归属校验失败 403/404）→ 非 `pending`→409（G4-E3 重复采纳 / 非 pending G4-E15）→ 调 `adopt_draft_to_kb` → 置 `adopted`+`document_id`+`resolved_at=datetime.now(timezone.utc)` → `flush()`（caller commit）。
  - `backend/app/api/agent.py`：新建 · `ResolveApprovalRequest{action:str}` + `AdoptApprovalResponse{document_id, kb_id, filename, status:"processing"}`；`POST /agent/approvals/{approval_id}/resolve`（经 `main.py` 挂 `/api/v1`）；`action != "adopt"` → 422（cancel 留 G4-3.3）；否则调 `resolve_adopt_approval` + `await db.commit()` 返回 `AdoptApprovalResponse`。
  - `backend/app/main.py`：注册 `agent_router`（`from app.api.agent import router as agent_router` + `app.include_router(agent_router, prefix="/api/v1")`，插入于 `ask_router` 前）。
  - `backend/app/services/agent/__init__.py`：导出 `resolve_adopt_approval`（import + `__all__`）。
  - `backend/tests/test_agent_g4_resolve_adopt.py`：新建（9 用例，详见下）。
- 关键决策/红线：resolve 是独立 HTTP 端点，**不在 SSE 层写库**；`adopt_draft_to_kb` **绝不**暴露给模型（G4-2.1 红线，`dispatch.py` 注释已锁）；Member 永不可采纳（HA-2-A · H4-1-B）；adopt 异步（H4-4-A）—— 立刻返回 `document_id`+`processing`，不阻塞 ingestion。
- 测试要点（`tests/test_agent_g4_resolve_adopt.py`，9 例）：helper 借 `org_iso` fixture（owner/admin/member）+ `register_and_login` 构造真实 `ChatThread`+`AgentRun`+`AgentApproval(pending)` 行（**逐父行 `flush()`** 规避 SQLAlchemy 同会话 FK 不自动排序问题）；`adopt_draft_to_kb` 用 `monkeypatch` 替换为真实插入 `Document(queued)` 返回 id 的 fake（满足 `document_id` FK）。覆盖：owner 200+processing+adopted、personal owner 200、member 403（G4-E1）、重复采纳 409（G4-E3）、非 pending 409（G4-E15）、跨 org kb 403、个人库他人 403、approval 不存在 404（G4-E8）、cancel→422。
- 验证方式（同 §14 · 容器内 pytest · zhiku-api + 真实 zhiku-postgres · Windows 路径记 `D:/...`）：
  - `docker cp` 同步 `backend/app/api/agent.py` + `backend/app/services/agent/{__init__,approvals,adopt}.py` + `backend/app/main.py` + `backend/tests/test_agent_g4_resolve_adopt.py` → `zhiku-api:/app`。
  - 定向：`pytest tests/test_agent_g4_resolve_adopt.py -q` → **9 passed**。
  - 路由注册核验：OpenAPI `paths` 含 `/api/v1/agent/approvals/{approval_id}/resolve`（adopt 分支 + 422 cancel 守卫）。
  - 真实 stub 核验：`adopt_draft_to_kb(db, approval, kb)` 用真实 `approval.user_id` 跑 → 返回 `document_id` 且 `documents` 落 `queued` 行（确认 stub 非缺陷，生产 `approval.user_id` 恒为真实用户）。
  - 全量回归：`pytest $(find tests -maxdepth 1 -name 'test_agent_*.py' ! -name '*golden*') -q`（排除 `test_agent_golden.py`）→ **144 passed**（135 基线 + 9 新增；fast/thorough/edit SSE 语义零回归；warning 仅 SQLAlchemy 连接 GC 清理噪声，非失败）。
- 结论：**G4-3.1 完成 + 实跑绿**（adopt 路径 + 服务入口 + 路由 + `adopt_draft_to_kb` 最小 stub；G4-E1/E3/E8/E15 + 409/403/404/cancel-422 全覆盖；零生产写库逻辑；fast/thorough/edit 全量零回归）。下一窗 **G4-3.2**（`adopt_draft_to_kb` 真实 md 写库 + `_v2` 冲突策略 + `background_tasks.add_task(process_document_ingestion)` · 复用现网 upload 文本路径 · G4-E16）。

### §14.4 验证记录（G4-3.2 · 2026-07-10 in-container pytest · adopt 真实写库窗）

- 性质：G4-3.2 = 替换 G4-3.1 的 `adopt_draft_to_kb` 最小 stub 为**真实写库实现**（文件落盘 + `_v2` 冲突 + `documents(queued)` + ingestion 入队）。**只做** plan §9 G4-3.2；**不写** G4-3.3 cancel / G4-3.5 审计 / 前端。
- 改动文件：
  - `backend/app/services/agent/adopt.py`：重写（替换 stub）。真实实现：读 `approval.payload_json["markdown"]` → `_resolve_adopt_filename`（`_v2`/`_v3`… 按 H4-6-A，复用 upload 同名判定口径 case-insensitive，不 409）→ `settings.upload_dir/{kb_id}/{doc_id}/{uuid}.md` 落盘 → `Document(queued)`（file_type=`md`、`uploaded_by=approval.user_id`、`content_sha256`=sha256）→ `flush()` → 经请求级 `ContextVar`（`_adopt_background_tasks`）入队 `process_document_ingestion(doc.id)`（复用现网 upload 文本路径）。签名 **`(db, approval, kb) -> UUID` 不变**，调用方 `resolve_adopt_approval` 零改动。
  - `backend/app/services/agent/approvals.py`：`resolve_adopt_approval` 增可选 kwarg `background_tasks=None`；在调 `adopt_draft_to_kb` 前后 `bind/unbind_adopt_background_tasks`（仅注入 `BackgroundTasks`，不改 `(db, approval, kb)` 调用点）。
  - `backend/app/api/agent.py`：`resolve_approval` 注入 `BackgroundTasks` 透传 `background_tasks=`；响应 `filename` 改为读**实际落库** `Document.filename`（同名时反映 `_v2`，更贴近前端展示）；返回形状 `{document_id, kb_id, filename, status:"processing"}` 不变。
- 关键决策/红线：写库**只在** resolve adopt 服务端路径（G4-3.1 已二次校验 kb write + 角色 + pending）；**绝不**暴露给模型（G4-2.1 红线）；adopt 异步（H4-4-A）—— 立刻返回 `document_id`+`processing`，ingestion 后台跑；Member 永不可采纳（HA-2-A）由 G4-3.1 守住，本窗不改权限。
- 测试要点（`tests/test_agent_g4_adopt_write.py`，4 例 · 真实 `adopt_draft_to_kb`，**不** monkeypatch）：
  - `test_g4_adopt_unit_writes_file_and_enqueues`：单元直调 → `.md` 落盘 + `documents` 落 `queued` + `process_document_ingestion` 被入队并传入正确 `document_id`（spy 确认）。
  - `test_g4_e16_unit_same_name_auto_v2`：预置同名 `Document` → 新文档 `filename=faq-draft_v2.md`（G4-E16）。
  - `test_g4_adopt_http_writes_file_and_enqueues`：HTTP happy path owner → 200 + `processing` + 文件落盘 + ingestion 入队（spy）。
  - `test_g4_e16_http_same_name_auto_v2`：HTTP 同名 → 响应 `filename=faq-draft_v2.md` + 文档以 `_v2` 落库。
  - `settings.upload_dir` 指向 `tmp_path`，避免污染宿主；`process_document_ingestion` 以 spy 替换（不触发真实嵌入）。
- 验证方式（同 §14 · 容器内 pytest · zhiku-api + 真实 zhiku-postgres · Windows 路径记 `D:/...`）：
  - `docker cp` 同步 `backend/app/services/agent/{adopt,approvals}.py` + `backend/app/api/agent.py` + `backend/tests/test_agent_g4_adopt_write.py` → `zhiku-api:/app`。
  - 定向：`pytest tests/test_agent_g4_adopt_write.py -q` → **4 passed**。
  - G4-3.1 不回退：`pytest tests/test_agent_g4_resolve_adopt.py -q` → **9 passed**（adopt_draft_to_kb 仍被 monkeypatch 隔离；`resolve_adopt_approval` 增 kwarg 不影响行为）。
  - 全量回归：`pytest $(find tests -maxdepth 1 -name 'test_agent_*.py' ! -name '*golden*') -q`（排除 `test_agent_golden.py`）→ **148 passed**（144 基线 + 4 新增；0 failed；fast/thorough/edit SSE 语义零回归）。warning 仅 SQLAlchemy 连接 GC 清理噪声（"Event loop is closed" unraisable），非失败。
- 结论：**G4-3.2 完成 + 实跑绿**（adopt 真实写库：md 落盘 + `_v2` 冲突 + `documents(queued)` + ingestion 入队；G4-E16 同名 `_v2` 覆盖；happy path 200+`processing` 不变；G4-3.1 9 passed 不回退；全量 `test_agent_*.py` 148 passed 零回归）。下一窗 **G4-3.3**（cancel 路径 · G4-E5/E6/E9）。

### §14.5 验证记录（G4-3.3 · 2026-07-10 in-container pytest · cancel 路径窗）

- 性质：G4-3.3 = plan §9 的 **cancel 分支**：把 `api/agent.py` 原 422 守卫降级为「未知 action 才 422」，接上真实 cancel 逻辑。**只做** G4-3.3；**不写** G4-3.5 审计 / 前端；**不改** adopt 分支（G4-3.1/3.2 行为零回退）。
- 改动文件：
  - `backend/app/services/agent/approvals.py`：新增 `resolve_cancel_approval(db, *, approval_id, current_user)`（**无 background_tasks**，cancel 不写库）。校验顺序：① approval 存在性 → 404（G4-E8）；② `is_creator = approval.user_id == current_user.id`，创建者本人放行，否则 `require_kb_access(kb_id=approval.kb_id, action=KbAction.write)`（kb 不存在 404 / Member 写动作 403=G4-E9）；③ `approval.status != pending` → 409（G4-E5）；翻转 `status=cancelled` + `resolved_at=datetime.now(timezone.utc)` → `flush()`（caller commit）。导出补入 `__all__`。
  - `backend/app/services/agent/__init__.py`：导出 `resolve_cancel_approval`（与 `resolve_adopt_approval` 并列）。
  - `backend/app/api/agent.py`：路由三分支 `adopt → resolve_adopt_approval` / `cancel → resolve_cancel_approval` / 其余 → **422**（未知 action 守卫）。新增 `CancelApprovalResponse{ok:bool=True}`；取消 `response_model`（adopt/cancel 返回各自 Pydantic 实例）；`resolve_adopt_approval` 签名不变，cancel 不触碰它。
  - `backend/tests/test_agent_g4_resolve_cancel.py`：新建（9 例，详见下）。
  - `backend/tests/test_agent_g4_resolve_adopt.py`：`test_g4_only_adopt_supported_cancel_422` 改写为 `test_g4_unknown_action_still_422`（cancel 现已支持，改为断言未知 action 422），其余 9 例不变。
- 关键决策/红线：cancel **仅翻转** `agent_approvals.status`（G4-3.3 红线）—— **绝不**写库 / 落 md / `_v2` / ingestion / 改源 PDF；cancel 不在 SSE 层、也绝不暴露给模型；adopt 分支行为零回退（签名不变、单测全绿）；Member 取消他人 → 403（HA-2-A 衍生 · H4-5-B），Member 取消自己 → 200（H4-5-B 创建者本人放行）。
- 测试要点（`tests/test_agent_g4_resolve_cancel.py`，9 例）：借 `org_iso` fixture（owner/admin/member）+ `_login` 构造真实 `ChatThread`+`AgentRun`+`AgentApproval(pending)` 行（逐父行 `flush()`，同 G4-3.1 隔离套路）；`adopt_draft_to_kb` 用 `monkeypatch` 隔离（cancel 不调它，仅为路由 import 防御）。覆盖：owner cancel 自己 200+`cancelled`+`resolved_at`、admin/owner cancel 他人 200、member cancel 自己 200（H4-5-B）、member cancel 他人 403（G4-E9）、cancel 已 adopted 409（G4-E5）、重复 cancel 已 cancelled 409（G4-E5）、approval 不存在 404（G4-E8）、未知 action 422、adopt 分支仍 happy path 200+`processing`（零回退）。
- 验证方式（同 §14 · 容器内 pytest · zhiku-api + 真实 zhiku-postgres · Windows 路径记 `D:/...`）：
  - `docker cp` 同步 `backend/app/api/agent.py` + `backend/app/services/agent/{__init__,approvals}.py` + `backend/tests/test_agent_g4_resolve_cancel.py` + `backend/tests/test_agent_g4_resolve_adopt.py` → `zhiku-api:/app`。
  - 定向：`pytest tests/test_agent_g4_resolve_cancel.py tests/test_agent_g4_resolve_adopt.py -q` → **18 passed**（9 + 9）。
  - 全量回归：`pytest $(find tests -maxdepth 1 -name 'test_agent_*.py' ! -name '*golden*') -q`（排除 `test_agent_golden.py`）→ **157 passed**（148 基线 + 9 新增；0 failed；fast/thorough/edit SSE 语义零回归；warning 仅 SQLAlchemy 连接 GC 清理噪声，非失败）。
- 结论：**G4-3.3 完成 + 实跑绿**（cancel 真实落地：创建者本人或 Admin/Owner 放行、Member 撤他人 403、非 pending 409、未知 action 422、adopt 分支零回退；`agent_approvals.status` 仅翻转不写库；全量 `test_agent_*.py` 157 passed 零回归）。下一窗 **G4-3.5**（审计钩子 `approval_cancelled` 等 · 无草稿全文）。

### §14.6 验证记录（G4-3.5 · 审计钩子窗 · 实现已落地）

- 性质：G4-3.5 = plan §9 的**审计钩子**：覆盖 plan §7 的 4 个 approval 事件（created / adopted / cancelled / denied）。**只做** G4-3.5；**不改** adopt/cancel 既有行为与出参（G4-3.1/3.2/3.3 零回退）；**不动**前端、SSE 层、G4-3.5 之外任何窗口。
- 改动文件：
  - `backend/app/services/audit/agent.py`：新增 4 个 async 审计函数（与 `audit_agent_run_started` 同构，复用 `write_audit_log`）+ `safe_audit` 容忍 helper。
    - `audit_agent_approval_created(db, *, actor_user_id, approval_id, kb_id, filename, draft_chars)` → `agent.approval_created`；metadata **仅** `{approval_id, kb_id, filename, draft_chars}`（**无**草稿全文）。
    - `audit_agent_approval_adopted(db, *, resolver_user_id, approval_id, document_id, kb_id, filename)` → `agent.approval_adopted`；metadata `{approval_id, document_id, kb_id, filename, resolver_user_id}`。
    - `audit_agent_approval_cancelled(db, *, resolver_user_id, approval_id)` → `agent.approval_cancelled`；metadata `{approval_id, resolver_user_id}`。
    - `audit_agent_approval_denied(db, *, approval_id, reason)` → `agent.approval_denied`；metadata `{approval_id, reason}`，reason ∈ {member_forbidden, grant_revoked, not_pending}。
  - `backend/app/services/agent/tools/generate_faq_draft.py`：在 `db.add(approval); await db.flush()` 之后 `await safe_audit(audit_agent_approval_created(...))`（actor_user_id=user_id, kb_id=resolved, draft_chars=len(draft)）；新增 import（audit 函数 + `write_audit_log`）。
  - `backend/app/services/agent/approvals.py`：`resolve_adopt_approval` / `resolve_cancel_approval` 在状态 `flush()` 后各加 `await safe_audit(audit_agent_approval_adopted/cancelled(...))`；**独立**于 deny 归因，在服务内把 `require_kb_access` 抛出的 403/404 标注 `exc.audit_reason`（Member 角色 403→`member_forbidden`，其余 403/404→`grant_revoked`），并把非 pending 的 409 标注 `exc.audit_reason="not_pending"`（仅加属性，不改变 status_code/detail，出参零回退）。
  - `backend/app/api/agent.py`：`resolve_approval` 用 `try/except HTTPException` 包住服务调用；捕获后调 `_audit_approval_denied(approval_id, exc)`。**关键**：denied 用**独立 `SessionLocal()`** 会话 `write_audit_log` + 立即 `commit`，避免被主请求（将回滚）吞掉；写完后原样 `re-raise` 原异常。422（未知 action）不记；approval 不存在（404 G4-E8）跳过（无 approval_id 可关联）；审计写入异常被 `safe` 容忍，绝不冒泡为 500。
  - `backend/tests/test_agent_audit.py`：新增（7 例，详见下）。
  - `backend/tests/test_agent_g4_generate_faq_draft.py`：为保持基线 157 绿，将 `test_generate_faq_draft_creates_pending_approval` 的 `db.add.assert_called_once()` 放宽为「首个被 add 的对象仍是 `AgentApproval`」（G4-3.5 的 created 钩子会追加一条审计 `db.add`，属预期副作用，不改工具行为）。
- 红线遵守：metadata **绝不**含草稿全文（payload_json.markdown）；审计**绝不**阻塞主流程（adopted/cancelled/created 的 audit 异常被 `safe_audit` 容忍）；审计**不在** SSE 层、也**绝不**暴露给模型（4 函数仅由服务/工具/路由调用，模型无感知）；adopt/cancel 行为与出参零回退。
- 测试要点（`tests/test_agent_audit.py`，7 例）：直查 `audit_logs` 表（action + metadata）验证：
  - `test_g4_audit_approval_created_no_full_text`：`run_generate_faq_draft` 成功后有 `agent.approval_created`（含 `draft_chars` > 0，无全文）。
  - `test_g4_audit_approval_adopted_owner`：owner（Admin/Owner）采纳后有 `agent.approval_adopted`（含 `document_id` / `resolver_user_id`）。
  - `test_g4_audit_approval_cancelled_member_own`：member 取消自己后有 `agent.approval_cancelled`（含 `resolver_user_id`）。
  - `test_g4_audit_approval_denied_member_cancel_others_403`：member 撤他人 → 403 后有 `agent.approval_denied`(reason=`member_forbidden`)，主流程状态仍 pending。
  - `test_g4_audit_approval_denied_duplicate_adopt_409`：重复采纳 → 第二次 409 后有 `agent.approval_denied`(reason=`not_pending`)。
  - `test_g4_audit_metadata_never_contains_full_draft`：该 approval 关联的全部审计行 `details` 不含 `markdown` / `payload_json` / 草稿全文片段。
  - 复用 `org_iso` fixture（owner/admin/member）+ `register_and_login`；`adopt_draft_to_kb` 用 `monkeypatch` 隔离；逐父行 `flush()` 构造 `ChatThread`+`AgentRun`+`AgentApproval(pending)`。
- 验证方式（同 §14 · 容器内 pytest · zhiku-api + 真实 zhiku-postgres · Windows 路径记 `D:/...`）：
  - `docker cp` 同步 `backend/app/services/audit/agent.py` + `backend/app/services/agent/tools/generate_faq_draft.py` + `backend/app/services/agent/approvals.py` + `backend/app/api/agent.py` + `backend/tests/test_agent_audit.py` + `backend/tests/test_agent_g4_generate_faq_draft.py` → `zhiku-api:/app`。
  - 定向：`pytest tests/test_agent_audit.py -q`（7 例）。
  - 既有窗零回退：`pytest tests/test_agent_g4_resolve_cancel.py tests/test_agent_g4_resolve_adopt.py -q`（18 passed）。
  - 全量回归：`pytest $(find tests -maxdepth 1 -name 'test_agent_*.py' ! -name '*golden*') -q`（排除 `test_agent_golden.py`）；预期 **157 + 新增 = 全绿**（0 failed；fast/thorough/edit SSE 语义零回归；warning 仅 SQLAlchemy 连接 GC 清理噪声，非失败）。
  - 注：实跑核验待容器内执行（本环境无 docker / 依赖，未运行 pytest）。
- 结论：**G4-3.5 实现完成**（4 审计事件 + 独立会话 denied + metadata 无草稿全文；adopt/cancel 零回退；基线 157 不回退）。下一窗 **G4-4**（端到端 SSE 串验）。

### §14.7 验证记录（G4-5.1 / G4-5.3 · 2026-07-11 · 前端测试固化 + A 层验收窗）

- 性质：**G4-5.1 = 前端测试固化**（安装 `@testing-library/react` + `jsdom` + 配置 vitest jsdom 环境 + 创建 `ApprovalCard.test.tsx`）；**G4-5.3 = A 层验收**（build + dispatchChatSseBlock + SSE 零回归核验）；**后端一律不动**（G4-3.x 零回退红线）。
- 改动文件（仅前端 + 文档）：
  - `frontend/package.json`：新增 devDependencies `@testing-library/react`、`@testing-library/jest-dom`、`jsdom`。
  - `frontend/vite.config.ts`：`test.environment` 改为 `"jsdom"`（原 `"node"`）；`test.include` 新增 `"src/**/*.test.tsx"`；`test.setupFiles` 新增 `"./src/test-setup.ts"`。
  - `frontend/src/test-setup.ts`：新建 · `afterEach(cleanup)` 确保 @testing-library/react DOM 隔离。
  - `frontend/src/components/chat/ApprovalCard.test.tsx`：新建 · 12 用例：双钮渲染 / Member 无采纳（G4-E2）/ 终态灰显已采纳·已取消（G4-E6/E18）/ 409/403 友好提示 / resolving 态 / onAdopt/onCancel 回调 / 草稿预览折叠 / citation chips / 文件名显示。
  - `docs/tasks/discovery-agent-g4-write-plan.md`：顶部状态行更新 + §9 G4-4.x/G4-5.x 行标 ✅ + 本 §14.7。
- 测试结果（前端 · Windows 本地 · vitest 3.2.7 · jsdom）：
  - `npm run build`：**tsc + vite build 绿**（572 kB JS + 72 kB CSS，无报错）。
  - 定向：`npx vitest run src/components/chat/ApprovalCard.test.tsx` → **12 passed**。
  - 全量前端：`npx vitest run` → **25/25 passed**（`chat-api.test.ts` 6 + `thread-stream-abort.test.ts` 7 + `ApprovalCard.test.tsx` 12）。
  - dispatchChatSseBlock approval_required 分发 6 例绿 ✅（G4-4.3 既存）。
  - fast/thorough SSE 零回归 7 例绿 ✅（G4-3 既存）。
- 红线遵守：后端代码零改动（G4-3.x 157 passed 基线不动）；fast/thorough SSE 语义零回归；Member 无采纳钮走 `can_adopt=false` 渲染而非硬闯 403。

### §14.8 验证记录（G4-5.2 · 2026-07-11 · G3 回归 · Docker 环境）

- 性质：**G3 回归**——验证 G4-min 实施中后端 157 passed + agent golden + retrieval golden 均无回退。
- 环境：Docker `zhiku-api` 容器 · Python 3.11.15 · pytest 9.1.1 · PostgreSQL (zhiku-postgres)。
- 前置：`docker cp` `golden_agent_qa.json` → `/docs/`（容器内 `parents[2]` 解析至 `/` 而非 `/app`，需补齐路径）。
- 测试结果：
  - `test_agent_*.py`（排除 golden）：**157 passed** · 0 failed · 零 G4 回退（含 G4-3.x adopt/cancel/audit/concurrency 全绿）。
  - `test_agent_golden.py`：**16/16 passed**（GQ-1～GQ-12 + 新增 multi_step/refusal/forbidden_kb 三类齐全）。比预期 15 多 1（G4 期间新增）。
  - `test_retrieval_golden.py`：**10 passed · 2 skipped**（GQ-4 / GQ-10 · 容器缺 `reportlab` 依赖 → `pytest.skip`，非回归）。10/10 已跑全绿。
- 结论：**G4-5.2 通过**——后端 157 + golden 16/16 + retrieval 10/10（2 skip 非回归）· G3 基线固守 · 零回退。G4-min 整线关闭。
- 结论：**G4-5.1 / G4-5.3 / G4-5.4 完成**（前端测试固化 12/12 + build 绿 + dispatch 6 例绿 + SSE 零回归 7 例绿 + 全量前端 25/25 + 文档更新）。G4-5.2 因需 Docker 环境本次跳过。下一窗视需要进入 G5（摘要草稿第二条线）或 G6（端到端集成测试）。
