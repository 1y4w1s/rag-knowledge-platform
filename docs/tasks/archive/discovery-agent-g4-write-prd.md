# 发现层 · 采纳写库 Agent PRD（G4-min · W2）

> **状态**：✅ **P 关**（2026-07-10）· G4-1～G4-5 分步确认 · ✅ **V 关**（2026-07-10）preview G4 真交互 v4.2 · 下一 **R 关**  
> **背景**：G-3 整线 ✅ · pytest 523 绿 · 用户选定下一线 **G4-min（W2 · 采纳写库）** · 首场景 **仅 FAQ 草稿 → Admin 采纳入库**  
> **依赖**：G-1 ✅ · G-2 ✅ · G-3 ✅ · HA-2-A 已拍板 · Plan 总图 `discovery-agent-platform-plan.md` §W2  
> **预览对齐**：`preview-agent-platform.html` v4.2 · G4 采纳卡片 **真交互**（V2 冻结 2026-07-10）

---

## 索引

| 节 | 内容 | 状态 |
|----|------|------|
| **G4-1** | 用户故事 · 编辑模式主路径 · 与 G3 关系摘要 | ✅ 2026-07-10 · H4-1-B · H4-2-B |
| **G4-2** | 做 / 不做边界 | ✅ 2026-07-10 |
| **G4-3** | Tool · SSE · 采纳卡片 · 写库数据流 | ✅ 2026-07-10 · H4-3-B · H4-4-A |
| **G4-4** | 权限 · 审计 · 乱操作表 | ✅ 2026-07-10 · H4-5-B · H4-6-A |
| **G4-5** | 验收口径草案（A 层 + 1 条 smoke） | ✅ 2026-07-10 |

**关联文档**：G3 PRD `discovery-agent-g3-read-prd.md` · TECH `TECH.md` TECH-7 · 总图 `discovery-agent-platform-plan.md` · 主 PRD `docs/PRD.md` §5.6

---

## G4-1 用户故事 · 编辑模式主路径 · 与 G3 关系 ✅

> **拍板**：**H4-1-B** · Member 可切编辑、可预览草稿、**无**采纳入库钮 · **H4-2-B** · `/ask` + 库内 chat 双入口 · 库内默认采纳目标 = 当前库

**这节定什么**：G4-min **唯一首场景**——**Admin/Owner** 在对话页切 **编辑** 模式，基于可见库内容让 Agent 生成 **FAQ 草稿**，弹出 **采纳卡片**；点 **采纳入库** 后在目标库 **新建 `.md` 文件** 并走现有整理管线；**不修改** 任何源 PDF。

### 用户故事（主角色 · Admin/Owner）

| # | 作为… | 我想… | 以便… |
|---|--------|--------|--------|
| US-1 | 制度库 Admin | 在 `/ask` 切 **编辑** 模式，问「根据年假制度生成 FAQ」 | Agent 先只读查库，再给出可审阅的 FAQ 草稿 |
| US-2 | Admin | 在助手回复下方看到 **采纳卡片**（文件名、目标库、草稿预览、引用来源） | 入库前我能看清要写什么、写到哪 |
| US-3 | Admin | 点 **采纳入库** | 系统在目标库创建 **新 md**（如 `FAQ_年假_v1.md`），触发 chunk/索引，卡片变「已采纳 · 整理中」 |
| US-4 | Admin | 点 **取消** | 草稿 **不入库** · 卡片变「已取消」· thread 内可回看文字说明 |
| US-5 | Admin | 采纳后在库文档列表看到新文件 | FAQ 可被 **快速/精准** 模式检索并带 citation |

### 用户故事（Member · H4-1-B）

| # | 作为… | 我想… | 以便… |
|---|--------|--------|--------|
| US-M1 | Member | 在 `/ask` 或库内 chat 切 **编辑** 模式，问「根据制度生成 FAQ」 | 我能 **预览** Agent 生成的 FAQ 草稿，了解内容质量 |
| US-M2 | Member | 在采纳卡片上看到说明「采纳需 Admin/Owner」 | 我知道 **不能** 自己入库 · 需找管理员采纳 |
| US-M3 | Member | **没有**「采纳入库」按钮 | 与 HA-2-A 一致 · 写库权限不下放 |

### 正常流程（S · 摘要 · 对齐 preview G4 占位）

| # | 用户做什么 | 看见什么 |
|---|------------|----------|
| **S-G4-1** | Admin 进 **`/ask` 或库内 chat** · 顶栏切 **编辑**（第三档 · Member 也可用 · H4-1-B） | 模式指示「编辑」· budget 显示编辑步数上限（预览为 2 步，Implement 以 plan 为准）· 库内 chat **默认目标库 = 当前库**（H4-2-B） |
| **S-G4-2** | 输入「根据年假制度生成 FAQ，写入人事库」并发送 | 可选：折叠 **tool 时间线**（只读查库步）→ 助手说明文字 → **采纳卡片**（`approval_required`） |
| **S-G4-3** | 审阅草稿预览 · 点 **采纳入库** | 卡片变 **已采纳** · 展示目标库名 + 文件名 · 可选 `document_status` 整理进度 |
| **S-G4-4** | 打开目标库文档列表 | 见新 `.md` · 状态经 ingestion 变为可检索 |

### 与 G3 关系（本节摘要 · 详规见 G4-3）

| 维度 | G3（已交付） | G4-min（本交付） |
|------|--------------|------------------|
| 模式 | `fast` / `thorough` | 新增 **`edit`**（`ChatRequest.mode` 扩展） |
| Tool | 4 个 **只读** tool | 保留只读查库 + 新增 **`generate_faq_draft`**（写·待审）· **`adopt_draft_to_kb`**（写·需 approval） |
| SSE | `tool_*` → `citation` → `token` → `done` | 在 `done` **之前**插入 **`approval_required`**；用户操作后 **`approval_resolved`** + 可选 **`document_status`** |
| UI 壳 | G2 thread + `AgentModeSwitcher` + `ToolTimeline` | **复用** · 新增 **`ApprovalCard`** + **`DraftPreview`**（预览 v4.1 G4 占位为视觉 SSOT） |
| 历史回放 | 正文 + citation · **无** tool 时间线 | 同 G3 · 采纳卡片终态（已采纳/已取消）**可**在刷新后保留为消息附属 UI 状态（🟡 H4-3 下一节拍板） |
| 入口 | `/ask` + 库内 chat（精准对称） | **同左** · 库内 edit 默认采纳目标 = 路径 kb（H4-2-B） |
| 权限 | G3：Member「编辑」灰钮 disabled（G3-E-M） | **H4-1-B**：Member **可切编辑** · 可预览草稿 · **采纳仅 Admin/Owner**（HA-2-A） |

### 名词（人话）

| 名词 | 含义 |
|------|------|
| **编辑模式** | 顶栏第三档 · 可生成 **待审草稿** · 不等同于「改源 PDF」 |
| **采纳卡片** | `approval_required` 驱动的确认 UI · 含草稿预览 + 采纳入库 / 取消 |
| **FAQ 草稿** | Agent 生成的 Markdown 问答稿 · **采纳前不落库** |
| **采纳入库** | 确认后在目标 KB 创建 **新文件** · 走现有 upload/ingestion 等价路径 |
| **approval_id** | 一次待确认写操作的唯一 id · 幂等 / 审计锚点 |

<details><summary>拍板归档 · H4-1 / H4-2（2026-07-10）</summary>

| 假设 | 选定 | 后果（白话） |
|------|------|--------------|
| **H4-1** | **B** · Member 可编辑不可采纳 | 与 preview G4 占位一致 · 卡片无采纳钮 · 占同一 30/h 限流 |
| **H4-2** | **B** · `/ask` + 库内 chat | 库维护可直接在库内 chat 生成 FAQ · 默认目标库 = 当前库 |

</details>

---

## G4-2 做 / 不做边界 ✅

> **确认**：2026-07-10 · FAQ only · 新建 md · 不碰源 PDF · 无 upload/rechunk/workflow

**这节定什么**：G4-min **Implement 合同**——首场景 **只做 FAQ 草稿 → Admin 采纳入库**；写操作 **新建 `.md` 文件** · **不碰源 PDF** · **不** 开 upload / rechunk / workflow 第二条线。

### ✅ 做（G4-min 范围内）

| # | 做什么 | 人话 |
|---|--------|------|
| B1 | **编辑模式** `mode=edit` | 顶栏第三档 · `/ask` + 库内 chat（H4-2-B） |
| B2 | **FAQ 草稿** | Agent 基于只读查库生成 **Markdown 问答稿** · 采纳前 **不落库** |
| B3 | **采纳卡片** | `approval_required` UI · Admin/Owner 见「采纳入库 / 取消」· Member 仅预览 + 说明 |
| B4 | **采纳入库** | 确认后在 **目标 KB 新建 `.md` 文件**（如 `FAQ_年假_v1.md`）· 走现有 **ingestion/chunk/索引** |
| B5 | **只读查库步** | 复用 G3 四 tool（`list_knowledge_bases` / `semantic_search` / `search_documents` / `get_chunk_excerpt`） |
| B6 | **写 tool（最小集）** | `generate_faq_draft`（写·待审）· `adopt_draft_to_kb`（写·需 approval 已确认） |
| B7 | **SSE 扩展** | `approval_required` · `approval_resolved` · 可选 `document_status`（整理进度） |
| B8 | **审计** | 记 approval_id、thread_id、目标 kb_id、文件名、操作者 · **不记** 草稿全文 / 用户问题全文 |
| B9 | **OrgScope** | 目标 kb 须在 `visible_kb_ids` 且角色具备 **kb write** · 不信模型传的 kb_id |
| B10 | **引用溯源** | 草稿生成依据的 citation chip **仍展示** · 入库后新 md 可被快速/精准检索 |

### ❌ 不做（本波明确排除）

| # | 不做什么 | 为什么 / 归哪 |
|---|----------|---------------|
| N1 | **摘要草稿**第二条线 | 用户拍板首场景 **FAQ only** · 摘要进 backlog / G5 |
| N2 | **`propose_upload` / `upload_document`** | 不做用户上传新 PDF/Word · 仅 **Agent 生成 md 采纳** |
| N3 | **改源 PDF / 覆盖真源** | 北极星 · 写操作 = **新文件或 draft** · 源文件版本化另立项 |
| N4 | **`suggest_rechunk` / `apply_rechunk`** | G5 Defer · 不重切片建议/执行 |
| N5 | **`enqueue_workflow` / 触发器 / 自动化模式** | G6 Defer · 不做「入库后自动摘要」flow |
| N6 | **G7 Webhook / 外联** | HA-3-C · 不做 |
| N7 | **联网搜索** | 主 PRD §14 · 仍不做 |
| N8 | **无引用纯聊天** | 北极星不变 · FAQ 须基于库内检索 |
| N9 | **Member 采纳入库** | HA-2-A · Member 无 kb write approval |
| N10 | **对话内多轮上下文记忆** | 与 G3 相同 · 另立项 |
| N11 | **自动切编辑 / 意图驱动升档** | HA-4-A · 须用户 **手动** 切编辑 |
| N12 | **历史 tool 时间线回放** | 延续 H3-2-B · 刷新后无 trace · 采纳终态见 🟡 H4-3 |
| N13 | **`get_document_metadata` tool** | 仍 Defer（与 G3 一致 · G4 前可补 · 非 G4-min 阻塞） |
| N14 | **BA-FINAL M1～M12 重跑** | G4-min 仅 **1 条 smoke** + A 层 · 全模块验收仍属 plan BA-FINAL |
| N15 | **preview HTML 真交互** | 本线为 P 关 · V 关再动 `preview-agent-platform.html` |

### 与 platform-plan 极限清单对照

| Tool / 能力 | 极限愿景 | G4-min |
|-------------|----------|--------|
| `generate_faq_draft` | G4 | ✅ |
| `adopt_draft_to_kb` | G4 | ✅ |
| `generate_summary_draft`（等） | G4/G5 | ❌ |
| `propose_upload` / `upload_document` | G4 | ❌ |
| `suggest_rechunk` / `apply_rechunk` | G5 | ❌ |
| `enqueue_workflow` | G6 | ❌ |
| `webhook_emit` | G7 | ❌ |

### 写库形态（硬约束）

```
用户确认采纳
  → 目标 KB 下 CREATE 新 documents 行（.md）
  → 内容 = FAQ 草稿 Markdown
  → 触发既有 ingestion pipeline（chunk · embed · index）
  → 源 PDF / 已有文档 metadata **不变**
```

**文件名**：Agent 提议 + 采纳卡展示 · Admin 确认前可见 · 冲突策略见 G4-4（同名 E 表）。

---

## G4-3 Tool · SSE · 采纳卡片 · 写库数据流 ✅

> **拍板**：**H4-3-B** · 刷新后保留采纳终态（`chat_messages` 附属） · **H4-4-A** · adopt 异步返回 `processing`

**这节定什么**：编辑模式 **技术契约**——Agent 怎么查库生成 FAQ 草稿、SSE 何时弹采纳卡、用户点采纳后 **写哪张表 / 调哪条 ingestion 路径**；与 G3 Research §2/§3 **同构扩展**。

### 3.1 编辑模式 Tool 清单（G4-min）

| Tool | 类型 | 谁调用 | 何时 | 权限 |
|------|------|--------|------|------|
| G3 四只读 | 读 | Agent 循环 | 编辑模式查库步 | 同 TECH-7 §7.3 |
| **`generate_faq_draft`** | 写·待审 | Agent 循环 | 只读步有足够依据后 **1 次** | 目标 `kb_id` ∈ visible 且 **kb write**（Admin/Owner）· Member 可调 tool 但 **approval 不可 adopt** |
| **`adopt_draft_to_kb`** | 写 | **服务端**（非模型） | 用户 POST **resolve adopt** 后 | 同上 · 须 `approval_id` 状态 = pending |

**分工硬规则**：

1. **`generate_faq_draft`**：产出 Markdown 草稿 + 创建 **`agent_approvals`** 行（`status=pending`）· **不** CREATE `documents`。  
2. **`adopt_draft_to_kb`**：**仅** 在用户确认后由 `services/agent/approvals.py` 调用 · 模型 **不得** 在 ReAct 循环里直接 adopt。  
3. 不信模型 `kb_id`：与 `visible_kb_ids` 求交 · 库内 chat **默认目标 kb = 路径 kb**（H4-2-B）· `/ask` 可由问题解析或 tool 参数指定（须在 visible 内）。

#### `generate_faq_draft` 契约（草案）

| 项 | 内容 |
|----|------|
| **人话** | 基于已检索片段，生成 FAQ Markdown 草稿，等待人工采纳。 |
| **入参** | `{ "kb_id": uuid, "filename": string, "source_chunk_ids": uuid[]?, "title": string? }` · `filename` 须 `.md` 后缀 |
| **出参（tool_result 摘要）** | `{ "ok": true, "approval_id": uuid, "filename", "kb_name", "draft_chars": int, "citation_count": int }` · **不含** 草稿全文（全文走 SSE `approval_required`） |
| **副作用** | INSERT `agent_approvals` · 草稿正文存 `payload_json`（或 `document_drafts` 关联表 · L 窗定一） |
| **无命中依据** | `ok=false` · 不创建 approval · 助手应拒答或说明「库内无足够依据」（对齐 G3-E6 精神） |

#### `adopt_draft_to_kb` 契约（草案 · 服务端）

| 项 | 内容 |
|----|------|
| **人话** | 把已确认的 FAQ 草稿写成目标库 **新 md 文件** 并触发整理。 |
| **入参** | `{ "approval_id": uuid }` · 从 JWT 取 `user_id` |
| **出参** | `{ "document_id": uuid, "kb_id", "filename", "status": "processing" }` · **H4-4-A** · 不阻塞等 ingestion 完成 |
| **现网映射** | 等价 **`upload_documents`** 的 **文本/md 创建路径**（非用户 multipart 上传）→ `process_document_ingestion` 异步 |
| **幂等** | 同一 `approval_id` 重复 adopt → **409** 或返回已有 `document_id`（G4-4 E 表） |

### 3.2 编辑模式步数与 Runtime

| 项 | 规则 |
|----|------|
| **步数上限** | 独立于精准 5 步 · 建议 **只读 ≤2 + `generate_faq_draft` ×1 = 最多 3 步**（预览 v4.1 占位 **2** · L 窗可微调） |
| **`agent_run`** | 编辑模式 **创建** · `mode=edit` |
| **Planner** | 先只读 tool · 末步必须 `generate_faq_draft` 或拒答 · **无** adopt tool 给模型 |
| **拒答** | 全无命中 / 无 write 权限 → **无** `approval_required` · 仅 citation+说明或拒答文案 |

### 3.3 SSE 事件序列（`mode=edit`）

继承 G3 硬约束：**tool 块在首条 citation 前** · **citation 在首条 token 前** · G4 新增 **`approval_required` 在 `done` 前**。

```
(tool_start → tool_result → agent_budget)*     // 含 generate_faq_draft
→ citation × N
→ token × M                                  // 助手说明「已生成草稿，请审阅下方卡片」
→ approval_required { … }                      // 采纳卡片数据源
→ done { message_id, citations, agent_run_id, approval_id, approval_status: "pending" }
```

**用户点采纳/取消**（**新 HTTP** · 非原 SSE 续流）：

```
POST /api/v1/agent/approvals/{approval_id}/resolve
  body: { "action": "adopt" | "cancel" }
  → adopt: adopt_draft_to_kb → document 创建 → 202/200 + document_id
  → cancel: approval status=cancelled
  → 前端更新 ApprovalCard 终态
  → 可选：轮询 GET document → 展示 document_status（processing → ready）
```

#### 事件载荷（草案）

| 事件 | `data` 形状 | UI |
|------|-------------|-----|
| `approval_required` | `{ approval_id, draft_type:"faq", filename, kb_id, kb_name, draft_preview, citations[], can_adopt: bool }` | **`ApprovalCard`** · Admin `can_adopt=true` 见双钮 · Member `false` 见说明文案 |
| `approval_resolved` | （G4-min **可选 SSE** · 默认 **HTTP 响应驱动 UI**） | 卡片变已采纳/已取消 |
| `document_status` | `{ document_id, status, progress? }` | 「整理中 → 可检索」（**可选** · 可改为轮询 documents API） |

**不发（G4-min）**：`propose_upload` 相关 · 摘要 draft 类型 · workflow 事件。

### 3.4 采纳卡片 UI（对齐 preview v4.1 G4 占位）

| 区域 | 内容 |
|------|------|
| 标题 | 「生成 FAQ 并写入 {kb_name}？」 |
| **DraftPreview** | 文件名（如 `FAQ_年假_v1.md`）+ 草稿摘要（Q/A 片段 · 可折叠全文） |
| 引用 | 下方 **citation chips**（与助手消息 R4-4 一致 · 草稿依据） |
| Admin/Owner | **采纳入库**（primary）· **取消** |
| Member（H4-1-B） | 无按钮 · 「Member 可预览草稿 · 采纳需 Admin/Owner」 |
| 已采纳 | 「✓ 已采纳 · {filename} → {kb_name} · 整理中/可检索」 |
| 已取消 | 「已取消 · 草稿未入库」 |

**布局**：助手消息 card 内 · **Tool 时间线之上或之下** 与 preview 一致（trace → action-card → 正文 → citations）。

### 3.5 写库数据流（8 步 · 工作区 `/ask`）

```
① Admin/Member 切「编辑」· POST .../chat { message, mode:"edit" }
② dispatch → OrgScope · 生成锁 · 限流 30/h（1 发送=1 计数）
③ stream_agent_*_edit_events → ReAct（只读步 + generate_faq_draft）
④ SSE tool_* → ToolTimeline + budget-chip
⑤ merge hits → citation* → token*（说明文字）
⑥ generate_faq_draft 成功 → INSERT agent_approvals(pending) → SSE approval_required
⑦ save chat turn · finish agent_run · done(approval_id)
⑧ 用户点 adopt → POST .../approvals/{id}/resolve {action:"adopt"}
   → adopt_draft_to_kb → CREATE documents(.md) → enqueue process_document_ingestion
   → audit（approval_id, document_id, kb_id, filename · 无草稿全文）
```

**库内 chat**：③ 换 `stream_agent_kb_edit_events` · 默认 `kb_id=路径 kb` · citation 无库名前缀（同 G3-E9）。

### 3.6 数据模型增量（PRD 级 · TECH-8 详写）

| 实体 | 用途 |
|------|------|
| `agent_approvals` | `id`, `run_id`, `thread_id`, `user_id`, `kind=adopt_faq`, `status=pending\|adopted\|cancelled\|expired`, `kb_id`, `filename`, `payload_json`（草稿）, `document_id?`, `resolved_at?` |
| `agent_runs.mode` | 扩展枚举 **`edit`** |
| `chat_messages` | **`approval_id` + `approval_status`** 附属 JSON（H4-3-B）· GET messages 回放卡片终态 |

<details><summary>拍板归档 · H4-3 / H4-4（2026-07-10）</summary>

| 假设 | 选定 | 后果（白话） |
|------|------|--------------|
| **H4-3** | **B** · 落库附属状态 | F5 后仍见已采纳/已取消 · GET messages 需带 approval 字段 |
| **H4-4** | **A** · adopt 异步 | 立刻返回 document_id + processing · 卡片「整理中」· 轮询或列表看终态 |

</details>

---

## G4-4 权限 · 审计 · 乱操作表 ✅

> **拍板**：**H4-5-B** · 创建者本人 + Admin/Owner 可取消 · **H4-6-A** · 同名 md 自动 `_v2` 后缀

**这节定什么**：谁能生成/采纳 · audit 记什么 · **E 表**（Member 硬闯、重复采纳、取消、grant 撤销、无库 400 等）——Implement 与 pytest 对齐 SSOT。

### 4.1 权限矩阵

| 动作 | Member | Admin/Owner | 服务端校验 |
|------|--------|-------------|------------|
| 切 **编辑** 模式 | ✅（H4-1-B） | ✅ | `mode=edit` 合法枚举 |
| 发编辑模式 chat | ✅ | ✅ | 同 G3 · 可见库非空 · 30/h 限流 |
| 触发只读 tool | ✅ | ✅ | OrgScope visible 求交 |
| **`generate_faq_draft`** | ✅ · 可生成预览 | ✅ | 目标 kb **read** 即可生成 · 若 kb 不可见 → tool `ok=false` |
| 见 **采纳卡片** 预览 | ✅ | ✅ | SSE `approval_required` · Member `can_adopt=false` |
| 点 **采纳入库** | ❌ UI 无钮 | ✅ | resolve adopt · 须 **kb write** + Admin/Owner 角色 |
| 点 **取消** | ✅ · **仅本人** pending 卡（H4-5-B） | ✅ | resolve cancel · 须 `approval.user_id == 当前用户` 或 Admin/Owner |
| 硬闯 resolve adopt API | **403** | ✅（有 write） | JWT + kb write + `approval.user_id` 归属 |

**与 HA-2-A**：Member **永不可** 写库 adopt · 与现网 Member 只读一致。

### 4.2 审计事件（摘要 · 无草稿/问题全文）

| 事件 | action | metadata 示例 |
|------|--------|---------------|
| 编辑 run 开始 | `agent.run_started` | run_id, thread_id, mode=edit |
| 草稿生成 | `agent.approval_created` | approval_id, kb_id, filename, draft_chars |
| 越权 kb（tool） | `agent.tool_denied` | run_id, tool, reason=forbidden_kb |
| 用户采纳 | `agent.approval_adopted` | approval_id, document_id, kb_id, filename, resolver_user_id |
| 用户取消 | `agent.approval_cancelled` | approval_id, resolver_user_id |
| adopt 被拒 | `agent.approval_denied` | approval_id, reason=member_forbidden \| grant_revoked \| not_pending |
| 文档创建 | `document.created`（若现网已有） | document_id, kb_id, source=agent_adopt |

### 4.3 乱操作表（E · G4-min SSOT）

| ID | 乱操作 | 系统怎么处理 | 你怎么验 |
|----|--------|--------------|----------|
| **G4-E1** | **Member 硬闯** `POST .../resolve {adopt}` | **403** · audit `approval_denied` | member JWT + curl/pytest |
| **G4-E2** | **Member UI** 点采纳 | **无采纳钮** · 有 **取消**（本人卡 · H4-5-B）· 说明「采纳需 Admin」 | member 浏览器 |
| **G4-E3** | **重复采纳** 同一 `approval_id` | **409**「已处理」· 或幂等返回原 `document_id`（不二次 CREATE） | 连点采纳入库 |
| **G4-E4** | 已 **取消** 后再点 adopt | **409** · status=cancelled | cancel → 再 adopt |
| **G4-E5** | 已 **采纳** 后再点 cancel | **409** · status=adopted | adopt → 再 cancel |
| **G4-E6** | 点 **取消** | approval=cancelled · 卡片终态 · **无** document · messages 附属更新（H4-3-B） | 取消后刷新仍见「已取消」 |
| **G4-E7** | **无可见库** 发编辑 chat | **400**（同 G3-E3） | 无 grant 账号 |
| **G4-E8** | 目标 kb **无 write**（Admin 被降级前已开卡） | resolve adopt → **403** grant_revoked | 采纳前撤 write grant |
| **G4-E9** | **grant 撤销** 后 Member 仍见旧卡片 | 刷新 GET messages 仍显示终态 · **新** adopt 403 | 撤 grant + 硬闯 API |
| **G4-E10** | 模型传 **越权 kb_id** | tool `ok=false` · 无 approval · 不 500 | pytest · 同 G3-E2 |
| **G4-E11** | **全无命中** 仍要 FAQ | 无 `approval_required` · 拒答/说明 | 无关问题 · 空库 |
| **G4-E12** | **连点发送** / 并行 POST chat | **409**（同 G3-E7） | 流式中再发 |
| **G4-E13** | **发送中切模式** | Abort SSE（同 G3-E1） | 编辑流式中切快速 |
| **G4-E14** | 空 message | **422** | 空框发送 |
| **G4-E15** | 他人 thread 的 `approval_id` | **404** 或 **403** | 改 UUID 硬闯 |
| **G4-E16** | **同名文件** 已存在于目标 kb | adopt 时 **自动后缀** `_v2`、`_v3`…（H4-6-A）· 不 409 | 库内已有 `FAQ_年假_v1.md` → 采纳得 `_v2` |
| **G4-E17** | **31 次/h** 编辑发送 | **429**（1 发送=1 计数 · Member 草稿也计） | 连问 31 次 |
| **G4-E18** | F5 **刷新** 后卡片 | GET messages 带 `approval_status` · 终态仍在（H4-3-B） | adopt/cancel 后刷新 |
| **G4-E19** | 库内 edit 目标库 | 默认 **路径 kb** · 模型传别库 id 被截断 | 库内 chat 编辑 |
| **G4-E20** | `mode=edit` 非法 / 旧客户端 | **422** | 硬闯 body |

<details><summary>拍板归档 · H4-5 / H4-6（2026-07-10）</summary>

| 假设 | 选定 | 后果（白话） |
|------|------|--------------|
| **H4-5** | **B** · 创建者 + Admin 可取消 | Member 卡片有取消无采纳 · 不能撤他人 pending |
| **H4-6** | **A** · 自动 `_v2` | 采纳不因重名失败 · 列表可能出现多版本 FAQ |

</details>

---

## G4-5 验收口径草案（A 层 + 1 条 smoke）✅

**这节定什么**：G4-min Implement 后 **怎么算过关**——A 层命令门槛 · **1 条浏览器 smoke** · **不要求** BA-FINAL M1～M12 重跑。

### 5.1 浏览器 smoke（S-G4-smoke · 每 I 窗建议 1 条）

| # | 步骤 | 期望 |
|---|------|------|
| **S-G4-smoke** | ① `demo_admin` 登录 → `/ask` 切 **编辑** ② 问「根据年假制度生成 FAQ，写入人事库」 ③ 见 **采纳卡片** + 草稿预览 ④ 点 **采纳入库** ⑤ 打开 **人事库** 文档列表 | 卡片「已采纳 · 整理中/可检索」· 列表出现新 **`.md`**（或 `_v2`）· F5 刷新卡片终态仍在（H4-3-B） |

**可选加测（非 smoke 阻塞）**：`demo_member` 同流程 · 无采纳钮 · 可取消 · G4-E1 硬闯 403。

**预览对标**：Implement 前 V 关更新 `preview-agent-platform.html` G4 真交互 · 本 P 关不动 preview。

### 5.2 自动化门槛（A 层 · 每 I 窗必绿）

| # | 项 | 期望 |
|---|-----|------|
| **A-G4-1** | G3 回归 | `test_agent_*.py` 全绿 · `golden_agent_qa.json` **15/15** 不回退 |
| **A-G4-2** | 检索 golden | `test_retrieval_golden` **12/12** |
| **A-G4-3** | G4 边界 pytest | `test_agent_g4_*.py`（或 plan 命名）覆盖 **G4-E1/E3/E7/E10/E16** 等核心 E |
| **A-G4-4** | approval resolve API | adopt/cancel 403/409 路径绿 |
| **A-G4-5** | R4-4 + edit SSE 序 | citation 先于 token · `approval_required` 在 `done` 前 |
| **A-G4-6** | 前端 | `npm run build` 绿 · `AgentModeSwitcher` 含编辑 · `ApprovalCard` 渲染 |
| **A-G4-7** | audit | `test_agent_audit` 或等价 · 含 `approval_*` · **无** 草稿全文 |

**命令草案**（Implement 后 · Windows）：

```powershell
cd D:\MyPrograms\rag-knowledge-platform\backend
py -3.11 -m pytest tests/test_agent_*.py tests/test_retrieval_golden.py -q
py -3.11 -m pytest tests/test_agent_g4_*.py -q
cd ..\frontend; npm run build
```

### 5.3 明确不要求（本波）

| 项 | 说明 |
|----|------|
| **BA-FINAL M1～M12 全勾** | G4-min 不触发全模块重验收 · 仍属 enterprise plan 末关 |
| **摘要草稿 / upload / rechunk / workflow** | G4-2 N 表 · 不测 |
| **G3 浏览器表 §8 重勾** | G3 已过 S3～S5 · G4 仅 **回归 A 层** + 上 smoke |
| **agent golden 扩 15+ 题** | L 窗定是否增 FAQ adopt 题 · P 关不阻塞 |

### 5.4 P 关 DoD（G4-min PRD）

| # | 条件 | 状态 |
|---|------|------|
| P1 | G4-1～G4-5 用户分步确认 | ✅ 2026-07-10 |
| P2 | 全文落盘本文 | ✅ 2026-07-10 |
| P3 | H4-1～H4-6 拍板归档 | ✅ |
| P4 | 30 秒口播可讲清采纳链 | ✅ 见下 |

---

## 文档关单（G4-min P · ✅ 2026-07-10）

- **G4-P** ✅ 本文 G4-1～G4-5 · H4-1～H4-6 全拍板
- **G4-V** ✅ `preview-agent-platform.html` v4.2 · 编辑可点 · 采纳卡真交互 · S-G4-smoke · G4-E1/E2/E6 · V2 冻结 2026-07-10
- **下一关** **R** · `discovery-agent-g4-write-research.md`（tool/SSE/approval API 对照现网 upload）

### 答辩 30 秒

「G4-min 只做一条 FAQ 采纳链：Admin 在编辑模式让 Agent 查库生成 FAQ 草稿，SSE 弹采纳卡片；点采纳后在目标库 **新建 md 文件**，异步走 ingestion，**不碰源 PDF**。Member 也能进编辑预览草稿，但没有采纳钮，只能自己取消 pending 卡。复用 G3 的 thread 和 SSE 壳，新增 approval 事件和 resolve API；同名文件自动 _v2，刷新后卡片终态落库可回放。」

---

**P 关 DoD 已满足** · 不写代码 · 不改 preview · 不开 Implement。
