# 发现层 · 采纳写库 Agent Research（G4-min · R 关）

> **状态**：✅ **R 关**（2026-07-10）· tool/SSE/approval API 对照现网 · 乱操作 E 表映射 · 不写 Implement  
> **背景**：G4-min P ✅ · V ✅ v4.2 V2 冻结 · G3 整线 ✅ · pytest 523 绿  
> **依赖**：G3 Research `discovery-agent-g3-read-research.md` · G4 PRD `discovery-agent-g4-write-prd.md`  
> **验收**：tool/SSE/approval API 对照现网 upload · 乱操作 E 表映射 · 不写 Implement

---

## S1 摘要

G4-min = **编辑模式 + FAQ 草稿 → Admin 采纳入库**。Agent 循环只读查库后调 `generate_faq_draft` 生成待审草稿，SSE 弹出 `approval_required` 采纳卡片；用户点采纳入库后，服务端 `adopt_draft_to_kb` 在目标 KB **新建 `.md` 文件**并触发 ingestion pipeline，与现网 `upload_documents` 的文本/md 创建路径等价（非用户 multipart 上传）。

**三句话**：
1. 编辑模式复用 G3 四只读 tool + 新增 `generate_faq_draft`（写·待审），不新增只读 tool。
2. 采纳卡片由 `approval_required` SSE 事件驱动，`POST /approvals/{id}/resolve` 执行 adopt/cancel，服务端校验 kb write + 角色。
3. 写库路径 = 现网 `upload_documents` 的 md/txt 分支复用（`process_document_ingestion` 异步），不新建 ingestion 入口。

---

## S2 Tool 映射（G4-min 新增 vs 现网对照）

### 2.1 只读 Tool（复用 G3）

| Tool | G4-min 行为 | 与 G3 差异 |
|------|------------|-----------|
| `list_knowledge_bases` | 编辑模式下可用 | 无 |
| `semantic_search` | 编辑模式下可用 | 无 |
| `search_documents` | 编辑模式下可用 | 无 |
| `get_chunk_excerpt` | 编辑模式下可用 | 无 |

### 2.2 新增 Tool：`generate_faq_draft`

| 项 | 内容 |
|----|------|
| **类型** | 写·待审（不直接 CREATE documents） |
| **调用者** | Agent ReAct 循环（末步） |
| **入参** | `{ "kb_id": uuid, "filename": string, "source_chunk_ids": uuid[]?, "title": string? }` |
| **出参** | `{ "ok": true, "approval_id": uuid, "filename", "kb_name", "draft_chars": int, "citation_count": int }` |
| **副作用** | INSERT `agent_approvals`（status=pending），草稿正文存 `payload_json` |
| **权限** | 目标 `kb_id` ∈ visible 且 **kb read**（Member 可生成预览） |
| **失败** | `ok=false`，无 approval，助手应拒答（对齐 G3-E6） |

**现网对照**：无直接等价。最接近的是 `upload_documents` 的文本创建路径，但 `generate_faq_draft` **不触发 ingestion**——仅创建 approval 行。ingestion 在 adopt 后才触发。

**实现要点**：
- 文件名须 `.md` 后缀
- `source_chunk_ids` 用于审计溯源（可选，建议必传）
- Member 可调 tool 但 approval 的 `can_adopt=false`（前端卡片无采纳钮）

### 2.3 新增 Tool：`adopt_draft_to_kb`

| 项 | 内容 |
|----|------|
| **类型** | 写（服务端，**非模型调用**） |
| **调用者** | `services/agent/approvals.py`（POST resolve 后） |
| **入参** | `{ "approval_id": uuid }`（从 JWT 取 `user_id`） |
| **出参** | `{ "document_id": uuid, "kb_id", "filename", "status": "processing" }` |
| **副作用** | CREATE `documents`（.md）+ enqueue `process_document_ingestion` |
| **权限** | `kb write` + Admin/Owner 角色 + `approval.status=pending` |
| **幂等** | 同一 `approval_id` 重复 adopt → **409** 或返回已有 `document_id` |

**现网对照**：等价于 `upload_documents` 的 **文本/md 创建路径**：

| upload 现网 | adopt_draft_to_kb |
|------------|-------------------|
| `POST /knowledge-bases/{kb_id}/documents` (multipart) | `POST /agent/approvals/{id}/resolve` (JSON) |
| 用户上传文件 → `_read_upload_with_size_limit()` | 服务端读 `payload_json` → 直接写文件 |
| `_assert_filename_available()` 409 冲突 | 同名自动 `_v2`（H4-6-A）· 不 409 |
| `_validate_extension()` 白名单 | `filename` 须 `.md` 后缀（`generate_faq_draft` 校验） |
| `Document(status=queued)` | `Document(status=queued)` ← 相同 |
| `background_tasks.add_task(process_document_ingestion)` | 同 ← 相同 |
| 审计 `document.upload` | 审计 `approval_adopted` + `document.created` |

**关键差异**：
1. **文件来源**：upload = 用户 multipart 文件；adopt = 服务端从 `payload_json` 读 Markdown 文本写文件
2. **冲突策略**：upload = 409；adopt = 自动 `_v2` 后缀
3. **审计事件**：upload = `document.upload`；adopt = `approval_adopted` + `document.created`（`source=agent_adopt`）

### 2.4 Tool 注册变更

| 变更 | 位置 | 说明 |
|------|------|------|
| `ReadOnlyToolName` 扩展 | `services/agent/tools/registry.py` | 新增 `generate_faq_draft` 枚举值（不在 `READ_ONLY_TOOL_NAMES` 中） |
| `AgentToolScope` 扩展 | `services/agent/tools/scope.py` | 新增 `require_kb_write()` 方法（adopt 时校验） |
| `_dispatch_tool()` 扩展 | `services/agent/runtime.py` | 新增 `generate_faq_draft` 分支 |
| `ToolPlanner` 扩展 | `services/agent/dispatch.py` | 编辑模式 planner：只读步 + 末步 `generate_faq_draft` |

---

## S3 SSE 映射（G4-min 新增 vs 现网对照）

### 3.1 现网 SSE 事件序列（G3 thorough 模式）

```
tool_start → tool_result → agent_budget  (×N 步)
→ citation × K
→ token × M
→ done { message_id, citations, agent_run_id }
```

### 3.2 G4-min 编辑模式 SSE 事件序列

```
tool_start → tool_result → agent_budget  (×N 只读步)
→ tool_start → tool_result → agent_budget  (×1 generate_faq_draft)
→ citation × K
→ token × M
→ approval_required { … }                  ← G4 新增
→ done { message_id, citations, agent_run_id, approval_id, approval_status: "pending" }
```

**硬约束继承**：
- 所有 `tool_*` 在首条 `citation` 前（R4-4）
- `citation` 在首条 `token` 前（R4-4）
- `approval_required` 在 `done` 前

### 3.3 新增 SSE 事件：`approval_required`

| 字段 | 类型 | 说明 |
|------|------|------|
| `approval_id` | UUID | 待确认写操作 ID |
| `draft_type` | `"faq"` | 草稿类型（G4-min 仅 FAQ） |
| `filename` | string | 建议文件名 |
| `kb_id` | UUID | 目标 KB |
| `kb_name` | string | 目标 KB 名称 |
| `draft_preview` | string | 草稿预览（摘要/前几段） |
| `citations` | array | 引用来源（与助手消息 citation 一致） |
| `can_adopt` | bool | `true` = Admin/Owner 可采纳；`false` = Member 仅预览 |

**现网对照**：无等价 SSE 事件。现网 upload 无 SSE（同步 HTTP 201 返回）。

### 3.4 新增 SSE 事件（可选）：`approval_resolved`

| 字段 | 类型 | 说明 |
|------|------|------|
| `approval_id` | UUID | 已确认 ID |
| `action` | `"adopt"` \| `"cancel"` | 用户操作 |
| `document_id` | UUID? | adopt 时返回（cancel 为 null） |
| `status` | string | 终态 |

**现网对照**：无等价。现网 upload 无"待确认"阶段。

### 3.5 新增 SSE 事件（可选）：`document_status`

| 字段 | 类型 | 说明 |
|------|------|------|
| `document_id` | UUID | 文档 ID |
| `status` | `"processing"` \| `"completed"` \| `"failed"` | 整理状态 |
| `progress` | int? | 进度百分比（可选） |

**现网对照**：等价于轮询 `GET /documents/{doc_id}` 的 `status` 字段，但通过 SSE 推送。

### 3.6 HTTP API：`POST /api/v1/agent/approvals/{approval_id}/resolve`

| 项 | 内容 |
|----|------|
| **入参** | `{ "action": "adopt" \| "cancel" }` |
| **出参（adopt）** | 200 `{ "document_id": uuid, "kb_id", "filename", "status": "processing" }` |
| **出参（cancel）** | 200 `{ "ok": true }` |
| **权限** | JWT + kb write + Admin/Owner（adopt）；创建者本人或 Admin/Owner（cancel） |
| **幂等** | 同一 approval 重复操作 → **409** |

**现网对照**：无等价 API。现网 upload 是同步创建，无异步确认阶段。

---

## S4 乱操作表映射（E 表 → 实现映射）

> **SSOT**：G4 PRD §G4-4 · 本节映射到实现层校验点

| E 表 ID | 乱操作 | 实现层校验 | 映射文件 | 行号（参考） |
|---------|--------|-----------|---------|------------|
| **G4-E1** | Member 硬闯 `POST .../resolve {adopt}` | JWT `role != admin/owner` → 403 | `api/agent.py`（新建） | — |
| **G4-E2** | Member UI 点采纳 | `can_adopt=false` · 前端无按钮 | `ApprovalCard` 组件 | — |
| **G4-E3** | 重复采纳同一 `approval_id` | `approval.status != pending` → 409 | `services/agent/approvals.py`（新建） | — |
| **G4-E4** | 已取消后再 adopt | `status=cancelled` → 409 | 同上 | — |
| **G4-E5** | 已采纳后再 cancel | `status=adopted` → 409 | 同上 | — |
| **G4-E6** | 点取消 | `status=cancelled` · 卡片终态 | `services/agent/approvals.py` | — |
| **G4-E7** | 无可见库发编辑 chat | `visible_kb_ids` 空 → 400 | `api/chat.py`（复用 G3 校验） | 同 G3-E3 |
| **G4-E8** | 目标 kb 无 write（Admin 降级前已开卡） | resolve adopt → `require_kb_access(kb, write)` 403 | `services/agent/approvals.py` | — |
| **G4-E9** | grant 撤销后 Member 仍见旧卡片 | GET messages 带 `approval_status` 终态 | `api/chat.py` GET messages | — |
| **G4-E10** | 模型传越权 `kb_id` | `tool_scope.require_kb_visible()` → `ok=false` | `services/agent/tools/scope.py` | 同 G3-E2 |
| **G4-E11** | 全无命中仍要 FAQ | 无 `approval_required` · 拒答/说明 | `services/agent/runtime.py` finalize | 同 G3-E6 |
| **G4-E12** | 连点发送/并行 POST chat | `wrap_stream_with_thread_generation_lock` → 409 | `services/rag/thread_generation_lock.py` | 同 G3-E7 |
| **G4-E13** | 发送中切模式 | Abort SSE（同 G3-E1） | 前端 AbortController | 同 G3-E1 |
| **G4-E14** | 空 message | Pydantic 422 | `api/chat.py` schema 校验 | 同 G3 |
| **G4-E15** | 他人 thread 的 `approval_id` | `approval.thread_id != current_thread` → 404/403 | `services/agent/approvals.py` | — |
| **G4-E16** | 同名文件已存在于目标 kb | 自动 `_v2`、`_v3`…（H4-6-A） | `services/agent/approvals.py` → 文件写入逻辑 | — |
| **G4-E17** | 31 次/h 编辑发送 | `enforce_api_rate_limit` 429（1 发送=1 计数） | `api/chat.py`（复用限流） | 同 G3 |
| **G4-E18** | F5 刷新后卡片 | GET messages 带 `approval_status` 终态 | `chat_messages.approval_id` + `approval_status` | H4-3-B |
| **G4-E19** | 库内 edit 目标库 | 默认路径 kb · 模型传别库 id 被截断 | `services/agent/tools/scope.py` `default_kb_id` | — |
| **G4-E20** | `mode=edit` 非法/旧客户端 | Pydantic 422（枚举校验） | `api/chat.py` schema | — |

### E 表映射分层

| 层 | 校验点 | 文件 |
|----|--------|------|
| **API 层** | JWT、角色、限流、空 message、模式枚举 | `api/chat.py`、`api/agent.py`（新建） |
| **Service 层** | approval 状态机、幂等、同名冲突、grant 撤销 | `services/agent/approvals.py`（新建） |
| **Tool 层** | kb 可见性、kb write、无命中拒答 | `services/agent/tools/scope.py`、`runtime.py` |
| **前端层** | Member 无采纳钮、卡片终态渲染、Abort | `ApprovalCard` 组件 |

---

## S5 Hypotheses（G4-min 设计假设）

| ID | 假设 | 选定 | 后果（白话） | 状态 |
|----|------|------|-------------|------|
| **H4-1** | Member 可切编辑模式？ | **B** · Member 可编辑不可采纳 | Member 预览草稿 · 无采纳钮 · 同 30/h 限流 | ✅ P 关拍板 |
| **H4-2** | 入口：`/ask` + 库内 chat？ | **B** · 双入口 | 库维护可直接在库内 chat 生成 FAQ · 默认目标库 = 当前库 | ✅ P 关拍板 |
| **H4-3** | 刷新后采纳卡片终态？ | **B** · 落库附属状态 | F5 后仍见已采纳/已取消 · GET messages 需带 approval 字段 | ✅ P 关拍板 |
| **H4-4** | adopt 同步等 ingestion？ | **A** · 异步 | 立刻返回 document_id + processing · 卡片「整理中」 | ✅ P 关拍板 |
| **H4-5** | 谁可取消 pending 卡？ | **B** · 创建者 + Admin | Member 卡片有取消无采纳 · 不能撤他人 pending | ✅ P 关拍板 |
| **H4-6** | 同名文件冲突？ | **A** · 自动 `_v2` | 采纳不因重名失败 · 列表可能出现多版本 FAQ | ✅ P 关拍板 |

---

## S6 DoD（R 关交付物）

| # | 条件 | 状态 |
|---|------|------|
| R1 | tool 映射表：G4 新增 tool vs 现网 upload 对照 | ✅ S2 |
| R2 | SSE 映射表：G4 新增事件 vs 现网事件对照 | ✅ S3 |
| R3 | approval API 对照现网 upload 路径 | ✅ S2.3 + S3.6 |
| R4 | 乱操作 E 表 → 实现层映射（20 条） | ✅ S4 |
| R5 | H 假设归档（H4-1～H4-6） | ✅ S5 |
| R6 | 不写 Implement | ✅ 本文无代码改动 |

---

## S7 答辩 30 秒

「G4-min 的 R 关完成了 tool/SSE/approval API 三层对照：`generate_faq_draft` 创建待审 approval 行但不写 documents，adopt 后复用现网 ingestion pipeline 新建 md 文件，SSE 在 done 前插入 `approval_required` 事件驱动前端采纳卡片；20 条乱操作 E 表全部映射到 API/Service/Tool/Frontend 四层校验点，同名文件自动 `_v2`、幂等 409、Member 403 均有明确实现位置。」

---

**R 关 DoD 已满足** · 不写代码 · 不改 preview · 不开 Implement。
