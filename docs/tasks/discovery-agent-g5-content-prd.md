# 发现层 · 内容智能 Agent PRD（G5 · W3）

> **状态**：✅ **P 关**（2026-07-11）· G5-1～G5-5 分步确认 · 下一 **V 关**（preview G5 交互）  
> **背景**：G4-min 整线 ✅（FAQ 草稿 + approval + adopt/cancel + SSE + 审计 · 后端 183 passed · 前端 25 passed）· 用户选定下一线 **G5（W3 · 内容智能）**  
> **依赖**：G1 ✅ · G2 ✅ · G3 ✅ · G4-min ✅ · HA-2-A 已拍板 · Plan 总图 `discovery-agent-platform-plan.md` §W3  
> **G5 定位**：G4-min 已打通 FAQ 草稿 → adopt 单线；G5 **扩第二条线（摘要草稿）+ 新增建议类能力（rechunk · 标签 · 质量评分）**，复用 G4 的 approval 门禁模式，不做自动执行。

---

## 索引

| 节 | 内容 | 状态 |
|----|------|------|
| **G5-1** | 用户故事 · 四条能力线 · 与 G4-min 关系摘要 | P 关待确认 |
| **G5-2** | 做 / 不做边界 | P 关待确认 |
| **G5-3** | Tool 白名单扩展 · SSE 事件对齐 · 数据流 | P 关待确认 |
| **G5-4** | 权限 · 审计 · 乱操作表 | P 关待确认 |
| **G5-5** | 验收口径草案（A 层 + smoke） | P 关待确认 |

**关联文档**：G4 PRD `discovery-agent-g4-write-prd.md` · TECH `TECH.md` TECH-7/8 · 总图 `discovery-agent-platform-plan.md` · 主 PRD `docs/PRD.md` §5.6

---

## G5-1 用户故事 · 四条能力线 · 与 G4-min 关系

**这节定什么**：G5 四条内容智能能力——**摘要草稿**（G4-min FAQ 之后的第二条 draft 线）、**rechunk 建议**、**标签自动建议**、**质量评分**——每条一个用户故事，说明复用 G4 的 approval 门禁模式。

### G5 总览：四条能力线

```
G4-min（已完成）                     G5（本线）
┌──────────────────┐              ┌──────────────────────────┐
│ FAQ 草稿 → adopt │              │ 摘要草稿 → adopt          │  ← 第二条 draft 线
│                  │              │ rechunk 建议 → apply      │  ← 新增建议类
│                  │              │ 标签建议 → apply          │  ← 新增建议类
│                  │              │ 质量评分（只读·无 adopt）  │  ← 新增只读
└──────────────────┘              └──────────────────────────┘
       复用 ──────────────────────→ approval 门禁 · SSE 壳 · 审计
```

### 用户故事（主角色 · Admin/Owner）

#### 线 A：摘要草稿（G4-min 第二条 draft 线）

| # | 作为… | 我想… | 以便… |
|---|--------|--------|--------|
| US-A1 | 制度库 Admin | 在编辑模式让 Agent 对**指定文档**生成摘要草稿 | 长文档有一句话/一段话摘要，入库后可用 |
| US-A2 | Admin | 审阅摘要草稿后点 **采纳入库** | 摘要作为文档 **metadata 附属**或**独立 .md** 存入目标库，可被检索 |
| US-A3 | Admin | 对**多个文档**生成批量摘要 | 库内文档批量文档化，提升检索效率 |
| US-A4 | Admin | 摘要采纳后**不覆盖**源文档 | 与 G4 FAQ 一致：新建或 metadata 追加，不改源 PDF |

**与 G4-min FAQ 线的差异**：

| 维度 | G4-min FAQ | G5 摘要 |
|------|-----------|---------|
| 输入 | 基于库内**检索片段**生成 QA 对 | 基于**指定文档全文**生成段落摘要 |
| 输出形态 | Q/A Markdown 列表 | 一句话摘要 + 可选扩展段落 |
| 入库方式 | 新建独立 `.md` 文件 | **新建 .md** 或 **写入文档 metadata.description**（L 窗定一） |
| Tool | `generate_faq_draft` | `generate_summary_draft` |
| Adopt | `adopt_draft_to_kb` | `adopt_summary_draft_to_kb`（复用 approval 模式） |

#### 线 B：Rechunk 建议

| # | 作为… | 我想… | 以便… |
|---|--------|--------|--------|
| US-B1 | Admin | 让 Agent **分析**某文档的当前切片质量并**给出建议** | 了解哪些 chunk 过长/过短/语义断裂 |
| US-B2 | Admin | 在建议卡片上看到 chunk 边界对比（当前 vs 建议） | 审阅后判断是否采纳 |
| US-B3 | Admin | 点 **应用重切片** | 系统对目标文档重新 chunk + embed + 索引，旧 chunks 标记 stale |
| US-B4 | Admin | **不采纳**建议 | 卡片取消 · 文档 chunk 不变 · 建议信息可回看 |

**Rechunk 硬约束**：
- `suggest_rechunk` = **只读建议**，不修改任何数据
- `apply_rechunk` = **写操作**，须 approval 卡片确认
- 重切片后文档 citation 可能变化——前端应能处理「chunk 已更新」标记
- **不**做全库自动重切片（G6 触发器线可能触及，本波不做）

#### 线 C：标签自动建议

| # | 作为… | 我想… | 以便… |
|---|--------|--------|--------|
| US-C1 | Admin | 让 Agent **分析**文档内容并**建议标签** | 文档自动分类，增强筛选/检索 |
| US-C2 | Admin | 在建议卡片上看到建议标签列表 + 置信度/理由 | 人工判断标签是否合理 |
| US-C3 | Admin | 勾选部分标签 → 点 **应用标签** | 选中的标签写入文档 metadata |
| US-C4 | Admin | 点 **取消** | 标签不写入 · 卡片终态「已取消」 |

**标签建议硬约束**：
- 标签写入文档 **metadata.tags** 字段（若现网已有 tags 系统则对齐，若无则扩 metadata JSON）
- 建议标签不与现有标签重复（服务端去重）
- 标签值须合法（无特殊字符、长度限制）
- **不**自动应用（须 approval 确认）

#### 线 D：质量评分（只读）

| # | 作为… | 我想… | 以便… |
|---|--------|--------|--------|
| US-D1 | Admin/Member | 让 Agent 对**指定文档**做质量评分 | 快速定位需要优化/补充的文档 |
| US-D2 | 用户 | 看到评分维度（完整性/可读性/时效性）+ 总分 + 改进建议 | 了解文档质量短板，有的放矢 |
| US-D3 | Admin | 评分结果**不自动**触发任何写操作 | 分数仅供参考，人工决策 |

**质量评分硬约束**：
- `score_quality` = **纯只读 tool**，无 approval 卡片，无副作用
- 评分结果在助手回复正文展示（复用 token SSE 通道）
- 评分维度草案（L 窗可调）：**完整性**（是否覆盖关键主题）· **可读性**（段落结构/格式）· **时效性**（最后更新距今）

### 与 G4-min 关系摘要

| 维度 | G4-min（已完成） | G5（本交付） |
|------|-----------------|-------------|
| 模式 | `edit`（已有） | **复用** `edit` · 不新增模式 |
| Draft 类型 | FAQ 一种 | 新增 **摘要**（第二条线） |
| 建议类 tool | 无 | **3 个建议 tool**：rechunk · 标签 · 质量评分 |
| 只读 tool | 4 个 G3 tool | 复用 + 新增 `score_quality` |
| 写 tool | `generate_faq_draft` + `adopt_draft_to_kb` | 新增 `generate_summary_draft` + `adopt_summary_draft_to_kb` + `apply_rechunk` + `apply_tags` |
| Approval 模式 | `approval_required` → adopt/cancel | **完全复用** · 建议类 tool 不触发 approval（`suggest_rechunk` / `suggest_tags` / `score_quality`） |
| SSE | `approval_required` · `approval_resolved` · `document_status` | **复用** · 无新增事件类型（建议结果走 `tool_result` + 正文 token） |
| UI 壳 | `ApprovalCard` + `DraftPreview` | **复用** · rechunk 建议卡需 **对比视图**（当前 vs 建议）· 标签建议卡需 **多选勾选** |
| 历史回放 | 卡片终态落 `chat_messages`（H4-3-B） | **同** G4 |
| 步数 | 编辑模式 ≤3 步 | 建议 ≤4 步（含 1 个 suggest tool + 1 个 apply tool 机会 · **apply 在 approval 后走 resolve API**） |

### 名词（人话）

| 名词 | 含义 |
|------|------|
| **摘要草稿** | 基于指定文档全文生成的摘要文本 · 采纳前不落库 |
| **Rechunk 建议** | Agent 分析当前切片质量后产出的「建议切片边界」· 不修改数据 |
| **应用重切片** | 用户确认建议后，服务端重新执行 chunk → embed → index |
| **标签建议** | Agent 分析文档后推荐的分类标签 · 不修改数据 |
| **应用标签** | 用户勾选确认后，标签写入文档 metadata |
| **质量评分** | 纯只读评分（完整性/可读性/时效性）· 无副作用 · 无 approval |
| **建议类 tool** | `suggest_rechunk` / `suggest_tags`：**只产出建议**、不写库、不弹 approval、结果在 tool_result + 正文展示 |
| **apply 类 tool** | `apply_rechunk` / `apply_tags` / `adopt_summary_draft_to_kb`：**写操作**、服务端 resolve 时调用、须 approval 已确认 |

---

## G5-2 做 / 不做边界

**这节定什么**：G5 **Implement 合同**——四条能力线**全做**（摘要 / rechunk / 标签 / 质量评分）· 写操作沿用 G4 的 approval 门禁 · **不**做自动执行 · **不**拆线（四条线一起出 PRD，Implement 时再议分批）。

### ✅ 做（G5 范围内）

| # | 做什么 | 人话 |
|---|--------|------|
| B1 | **摘要草稿** `generate_summary_draft` | 基于**指定文档 ID** 生成摘要 · 采纳前不落库 |
| B2 | **摘要采纳** `adopt_summary_draft_to_kb` | 确认后写库 · 新建 `.md` 或写入 metadata（L 窗定） |
| B3 | **Rechunk 建议** `suggest_rechunk` | 只读分析当前切片质量 · 产出边界建议 · **不修改数据** |
| B4 | **应用重切片** `apply_rechunk` | approval 确认后执行 re-chunk → embed → index · 旧 chunks 标记 stale |
| B5 | **标签建议** `suggest_tags` | 只读分析内容 · 产出标签列表 + 置信度 · **不修改数据** |
| B6 | **应用标签** `apply_tags` | approval 确认后 · 标签写入文档 metadata · 服务端去重/合法性校验 |
| B7 | **质量评分** `score_quality` | 纯只读评分 + 改进建议 · 无 approval · 无副作用 |
| B8 | **Approval 门禁复用** | 三条写线（摘要/重切片/标签）全部走 `approval_required` → adopt/cancel |
| B9 | **SSE 兼容** | G4 SSE 事件全复用 · 无新增事件类型 |
| B10 | **审计** | 记 approval_id、action、目标 doc/kb、操作者 · **不记** 草稿全文 |
| B11 | **OrgScope** | 目标文档/kb 须在可见范围 · 不信模型传的 id |
| B12 | **引用溯源** | 摘要/评分依据仍展示 citation · rechunk 建议展示原 chunk 引用 |
| B13 | **G4 只读 tool 复用** | 编辑模式下仍可用 G3 四 tool 查库（`list_knowledge_bases` / `semantic_search` / `search_documents` / `get_chunk_excerpt`） |
| B14 | **UI 扩展（新卡片型）** | rechunk 建议卡：当前 vs 建议对比视图 · 标签建议卡：多选勾选 |

### ❌ 不做（本波明确排除）

| # | 不做什么 | 为什么 / 归哪 |
|---|----------|---------------|
| N1 | **自动重切片/重索引** | 必须 approval 门禁（用户要求 · 沿用 G4 模式） |
| N2 | **全库批量 rechunk** | G6 触发器线可能触及 · 本波仅单文档 |
| N3 | **自动标签应用** | 须 approval 确认 · 无静默写入 |
| N4 | **质量评分触发写操作** | `score_quality` 纯只读 · 不接任何后续写流 |
| N5 | **多文档批量摘要**（UI 交互） | 第一条线先做**单文档摘要** · 批量进 backlog / G5.x |
| N6 | **FAQ 线改动** | G4-min FAQ 已封板 · G5 不动 FAQ tool/Schema |
| N7 | **`propose_upload` / `upload_document`** | G4 N2 延续 · G5 不碰用户上传 |
| N8 | **改源 PDF** | 北极星不变 · 摘要/标签/评分均不改源 |
| N9 | **`enqueue_workflow` / 触发器** | G6 Defer · 不做「评分低于 X 自动建议 rechunk」 |
| N10 | **G7 Webhook** | HA-3-C · 不做 |
| N11 | **联网搜索** | 主 PRD §14 · 仍不做 |
| N12 | **无引用纯聊天** | 北极星不变 · 摘要/评分须基于文档内容 |
| N13 | **Member 写库** | HA-2-A · Member 可看建议/评分 · 不可 adopt/apply |
| N14 | **自动切编辑模式** | HA-4-A · 须手动切 |
| N15 | **历史 tool 时间线回放** | 延续 H3-2-B |
| N16 | **新增模式** | 复用 `edit` 模式 · G5 不新增第五模式 |
| N17 | **BA-FINAL M1～M12 重跑** | G5 仅 A 层 + smoke · 全模块仍属 enterprise plan |
| N18 | **G4 回归改动** | G4-min FAQ 线零变动 · approve 逻辑不改 |

### 与 platform-plan 极限清单对照

| Tool / 能力 | 极限愿景 | G4-min | **G5** |
|-------------|----------|--------|--------|
| `generate_faq_draft` | G4 | ✅ | —（不动） |
| `adopt_draft_to_kb` | G4 | ✅ | —（不动） |
| `generate_summary_draft` | G4/G5 | ❌ | **✅** |
| `adopt_summary_draft_to_kb` | G4/G5 | ❌ | **✅** |
| `suggest_rechunk` | G5 | ❌ | **✅** |
| `apply_rechunk` | G5 | ❌ | **✅** |
| `suggest_tags` | G5（新增） | ❌ | **✅** |
| `apply_tags` | G5（新增） | ❌ | **✅** |
| `score_quality` | G5（新增） | ❌ | **✅** |
| `propose_upload` | G4 | ❌ | ❌ |
| `enqueue_workflow` | G6 | ❌ | ❌ |
| `webhook_emit` | G7 | ❌ | ❌ |

### 写操作形态（硬约束 · 对齐 G4 §G4-2）

```
摘要采纳：
  用户确认采纳
    → 目标 KB 下 CREATE 新 .md 或 UPDATE metadata.description
    → 内容 = 摘要文本
    → 触发既有 ingestion pipeline（若新建 .md）
    → 源文档 metadata 不变

重切片应用：
  用户确认应用
    → 目标文档重新 chunk（新边界）
    → 旧 chunks 标记 stale（软删/status 标记）
    → 新 chunks → embed → index
    → 文档 citation 可能漂移

标签应用：
  用户确认应用
    → 目标文档 metadata.tags = 新标签列表
    → 服务端去重 + 合法性校验
    → 无 ingestion 触发
```

---

## G5-3 Tool 白名单扩展 · SSE 事件对齐 · 数据流

**这节定什么**：G5 **技术契约**——哪些 tool 进入白名单、每个 tool 的入参/出参/副作用、SSE 如何对齐 G4、数据流如何走。

### 3.1 G5 Tool 完整白名单（编辑模式 · `mode=edit`）

| Tool | 类型 | 来自 | 谁调用 | 权限 |
|------|------|------|--------|------|
| G3 四只读 | 读 | G3 | Agent 循环 | 同 TECH-7 §7.3 |
| `generate_faq_draft` | 写·待审 | G4-min | Agent 循环 | kb write |
| `adopt_draft_to_kb` | 写 | G4-min | 服务端 resolve | approval 已确认 |
| **`generate_summary_draft`** | 写·待审 | **G5 新增** | Agent 循环 | kb write |
| **`adopt_summary_draft_to_kb`** | 写 | **G5 新增** | 服务端 resolve | approval 已确认 |
| **`suggest_rechunk`** | 建议 | **G5 新增** | Agent 循环 | kb read（仅建议） |
| **`apply_rechunk`** | 写 | **G5 新增** | 服务端 resolve | admin + approval |
| **`suggest_tags`** | 建议 | **G5 新增** | Agent 循环 | kb read（仅建议） |
| **`apply_tags`** | 写 | **G5 新增** | 服务端 resolve | kb write + approval |
| **`score_quality`** | 读 | **G5 新增** | Agent 循环 | kb read |

**白名单硬规则**（对齐 G4-3 §3.1）：

1. **建议类 tool**（`suggest_rechunk` / `suggest_tags`）：**只产出建议** · 不写库 · 不创建 approval · 建议内容在 `tool_result` + 正文 token 中展示。
2. **apply 类 tool**（`apply_rechunk` / `apply_tags` / `adopt_summary_draft_to_kb`）：**仅**服务端在用户 POST resolve 后调用 · **模型不得在 ReAct 循环中直接调用 apply 类 tool**。
3. **draft 类 tool**（`generate_summary_draft`）：与 `generate_faq_draft` 同模式——产出草稿 + INSERT `agent_approvals`(pending) · **不** CREATE documents。
4. `score_quality`：纯只读 · 结果在正文展示 · 无 approval · 无副作用。
5. 所有 tool 不信模型传的 id：OrgScope 校验 · 求交 `visible_kb_ids` / `visible_doc_ids`。

#### `generate_summary_draft` 契约（草案）

| 项 | 内容 |
|----|------|
| **人话** | 基于指定文档全文生成摘要草稿，等待人工采纳。 |
| **入参** | `{ "document_id": uuid, "kb_id": uuid, "filename": string?, "length": "short"|"medium"|"long"? }` · `filename` 须 `.md` 后缀（若入库为独立文件） |
| **出参（tool_result 摘要）** | `{ "ok": true, "approval_id": uuid, "document_id", "filename", "kb_name", "summary_chars": int, "length": string }` · **不含**摘要全文（全文走 SSE `approval_required`） |
| **副作用** | INSERT `agent_approvals`（`kind=adopt_summary`）· 摘要正文存 `payload_json` |
| **无权限** | `ok=false` · 不创建 approval |

#### `adopt_summary_draft_to_kb` 契约（草案 · 服务端）

| 项 | 内容 |
|----|------|
| **人话** | 把已确认的摘要草稿写入目标库。 |
| **入参** | `{ "approval_id": uuid }` |
| **出参** | `{ "document_id"?: uuid, "kb_id", "status": "success"|"processing" }` |
| **入库方式** | 二选一（L 窗定）：**A** 新建 `.md` 文件 → 走 ingestion · **B** 写入目标文档 `metadata.description` → 无 ingestion |
| **幂等** | 同一 `approval_id` 重复 adopt → **409** 或返回已有结果 |

#### `suggest_rechunk` 契约（草案）

| 项 | 内容 |
|----|------|
| **人话** | 分析文档的当前切片质量，产出改进建议。 |
| **入参** | `{ "document_id": uuid, "kb_id": uuid }` |
| **出参** | `{ "ok": true, "document_id", "current_chunks": int, "suggested_chunks": int, "issues": [{ "chunk_index", "issue": "too_long"|"too_short"|"semantic_break", "suggestion" }], "split_suggestions": [{ "position": int, "reason": string }] }` |
| **副作用** | **无** · 不创建 approval · 不修改数据 |
| **无文档/无权限** | `ok=false` |

#### `apply_rechunk` 契约（草案 · 服务端）

| 项 | 内容 |
|----|------|
| **人话** | 按确认的 rechunk 建议重新切片。 |
| **入参** | `{ "approval_id": uuid }` + `{ "chunk_boundaries"? }` 可选（覆盖建议） |
| **出参** | `{ "document_id": uuid, "old_chunks": int, "new_chunks": int, "status": "reindexing" }` |
| **副作用** | 旧 chunks → stale · 新 chunks → embed → index · audit |

#### `suggest_tags` 契约（草案）

| 项 | 内容 |
|----|------|
| **人话** | 分析文档内容，建议标签分类。 |
| **入参** | `{ "document_id": uuid, "kb_id": uuid, "max_tags"?: int }` · 默认 max=10 |
| **出参** | `{ "ok": true, "document_id", "existing_tags": string[], "suggested_tags": [{ "tag": string, "confidence": float, "reason": string }] }` |
| **副作用** | **无** · 不创建 approval · 不修改数据 |

#### `apply_tags` 契约（草案 · 服务端）

| 项 | 内容 |
|----|------|
| **人话** | 把用户勾选的标签写入文档 metadata。 |
| **入参** | `{ "approval_id": uuid, "selected_tags": string[] }` · 仅写入勾选的标签 |
| **出参** | `{ "document_id": uuid, "applied_tags": string[], "skipped_duplicates": string[] }` |
| **副作用** | UPDATE `documents.metadata.tags` · service 去重 · 校验非法字符 |

#### `score_quality` 契约（草案）

| 项 | 内容 |
|----|------|
| **人话** | 对指定文档做质量评分（完整性/可读性/时效性）。 |
| **入参** | `{ "document_id": uuid, "kb_id": uuid }` |
| **出参** | `{ "ok": true, "document_id", "scores": { "completeness": float, "readability": float, "timeliness": float, "overall": float }, "suggestions": string[] }` · 每项 0～100 |
| **副作用** | **无** · 无 approval · 纯读 |
| **无文档** | `ok=false` |

### 3.2 编辑模式步数与 Runtime（G5 扩展）

| 项 | 规则 |
|----|------|
| **步数上限** | 编辑模式建议 **≤4 步**（G4-min 为 3 步 · G5 加 1 步给建议类 tool） |
| **`agent_run`** | `mode=edit`（复用 · 不新增模式） |
| **Planner** | 先只读查库（可选）→ 建议/suggest tool → 生成/评分 tool · **末步为 draft/suggest/score 之一** · **无** apply/adopt tool 给模型 |
| **拒答** | 全无命中 / 无权限 → 无 `approval_required` · 仅拒答文案 |

### 3.3 SSE 事件序列（`mode=edit` · G5 扩展）

**G5 无新增 SSE 事件类型**。完全复用 G4 事件。建议类 tool 结果走 `tool_result`，正文走 `token`。

#### 摘要草稿流（同 G4 FAQ 流）

```
(tool_start → tool_result)*               // 可选只读查库
→ tool_start → tool_result                // generate_summary_draft
→ citation × N
→ token × M                               // 助手说明
→ approval_required { ... }               // 采纳卡片
→ done { message_id, citations, approval_id }
```

#### Rechunk 建议流

```
tool_start → tool_result                  // suggest_rechunk（含建议 JSON）
→ citation × N                            // 引用的原 chunks
→ token × M                               // 助手解读建议 + 说明
→ approval_required {                     // "应用重切片？"卡片
    approval_id,
    kind: "apply_rechunk",
    document_id,
    current_chunks: 15,
    suggested_chunks: 12,
    changes_summary: "合并 3 个短 chunk · 拆分 1 个长 chunk",
    can_adopt: bool
  }
→ done
```

#### 标签建议流

```
tool_start → tool_result                  // suggest_tags（含标签列表 JSON）
→ citation × N
→ token × M
→ approval_required {                     // "应用标签？"卡片
    approval_id,
    kind: "apply_tags",
    document_id,
    suggested_tags: [{ tag, confidence, reason }],
    existing_tags: [...],
    can_adopt: bool
  }
→ done
```

#### 质量评分流（无 approval！）

```
tool_start → tool_result                  // score_quality
→ citation × N
→ token × M                               // 评分 + 建议在正文展示
→ done { message_id }                     // 无 approval_required
```

#### 用户 resolve 流（同 G4）

```
POST /api/v1/agent/approvals/{approval_id}/resolve
  body: { "action": "adopt"|"cancel" [, "selected_tags": [...] ] }
  → adopt: apply_* / adopt_* → 202/200
  → cancel: approval status=cancelled
  → 前端更新 ApprovalCard 终态
```

#### 事件载荷扩展（草案）

| 事件 | `data` 新增字段（G5 扩展） | 说明 |
|------|--------------------------|------|
| `approval_required` | `kind` 枚举扩：`"adopt_faq"`（G4）→ 新增 `"adopt_summary"` `"apply_rechunk"` `"apply_tags"` | 前端按 kind 渲染不同卡片形态 |
| `approval_required` | `changes_summary`（rechunk 专用） | 简短的人话变更说明 |
| `approval_required` | `suggested_tags: [{tag, confidence, reason}]`（标签专用） | 标签列表 + 置信度 |
| `approval_required` | `existing_tags`（标签专用） | 已有关联标签，前端可标记重复 |

**不发（G5）**：`propose_upload` 类 · workflow 事件 · 新增 SSE type。

### 3.4 采纳卡片 UI 扩展（对齐 G4 v4.2 + G5 新卡片型）

#### 摘要采纳卡（同 G4 FAQ 模式）

| 区域 | 内容 |
|------|------|
| 标题 | 「生成摘要并写入 {kb_name}？」 |
| DraftPreview | 文档名 + 摘要文本（可折叠） |
| 引用 | 原文档 citation |
| 按钮 | Admin：采纳入库 / 取消 · Member：无采纳钮 + 说明 |

#### Rechunk 建议卡（新）

| 区域 | 内容 |
|------|------|
| 标题 | 「应用重切片建议？」 |
| 变更摘要 | 「合并 3 个短 chunk · 拆分 1 个长 chunk」（来自 `changes_summary`） |
| 对比视图 | **左侧**「当前」：chunk 数 + 边界图示 · **右侧**「建议」：新 chunk 边界 + 变化高亮 |
| 按钮 | Admin：**应用重切片**（primary）· 取消 · Member：无钮 + 说明 |
| 已应用 | 「✓ 已应用 · 15→12 chunks · 重新索引中」 |
| 已取消 | 「已取消 · 切片未变更」 |

#### 标签建议卡（新 · 多选）

| 区域 | 内容 |
|------|------|
| 标题 | 「应用标签建议？」 |
| 标签列表 | **多选 checkbox**：每行 = 标签名 + 置信度 + 理由（可选展示）· 已存在的标签灰色标记 |
| 按钮 | Admin：**应用选中标签**（primary）· 取消 · Member：无钮 + 说明 |
| 已应用 | 「✓ 已应用 {n} 个标签 · {m} 个重复跳过」 |
| 已取消 | 「已取消 · 标签未变更」 |

### 3.5 数据流（概要 · L 窗详写）

#### 摘要采纳链（同 G4 FAQ 模式）

```
Admin 切编辑 → POST chat { mode:"edit" }
→ ReAct（可选只读 + generate_summary_draft）
→ SSE tool_result + approval_required
→ 用户点 adopt → POST resolve { action:"adopt" }
→ adopt_summary_draft_to_kb
   → 方式 A：CREATE documents(.md) → enqueue ingestion
   → 方式 B：UPDATE documents.metadata.description
→ audit(approval_id, document_id, kb_id, action)
```

#### Rechunk 链

```
Admin 切编辑 → POST chat { mode:"edit" }
→ ReAct（suggest_rechunk）  // 只读建议
→ SSE tool_result + approval_required(kind=apply_rechunk)
→ 用户点应用 → POST resolve { action:"adopt" }
→ apply_rechunk
   → 旧 chunks → stale
   → 新 chunk 边界 → embed → index
→ audit(approval_id, document_id, old_count, new_count)
```

#### 标签应用链

```
Admin 切编辑 → POST chat { mode:"edit" }
→ ReAct（suggest_tags）  // 只读建议
→ SSE tool_result + approval_required(kind=apply_tags)
→ 用户勾选标签 → POST resolve { action:"adopt", selected_tags: [...] }
→ apply_tags
   → 去重：skip = selected ∩ existing
   → UPDATE documents.metadata.tags
→ audit(approval_id, document_id, applied_tags, skipped)
```

### 3.6 数据模型增量（PRD 级 · TECH-8 扩）

| 实体 | G5 增量 |
|------|---------|
| `agent_approvals` | `kind` 枚举扩：`adopt_summary` `apply_rechunk` `apply_tags` · `payload_json` 存储草稿正文/建议详情 |
| `agent_runs.mode` | `edit`（复用 · 不变） |
| `chat_messages` | `approval_id` + `approval_status`（G4 H4-3-B 复用） |
| `documents.chunks` | `status` 字段或 `is_stale` 标记（rechunk 用） |
| `documents.metadata` | 扩展 `tags: string[]` 字段（若现网尚无） |

---

## G5-4 权限 · 审计 · 乱操作表

**这节定什么**：G5 四条线的权限矩阵 · audit 记录 · **E 表**（越权、重复操作、刷新、冲突等）——对齐 G4-4 §4.3 模式。

### 4.1 权限矩阵

| 动作 | Member | Admin/Owner | 服务端校验 |
|------|--------|-------------|------------|
| 切 **编辑** 模式 | ✅ | ✅ | 同 G4 |
| 发编辑 chat | ✅ | ✅ | 同 G4 · 30/h |
| 触发只读 tool（含 G3 四 tool） | ✅ | ✅ | OrgScope |
| **`generate_summary_draft`** | ✅ · 可生成预览 | ✅ | 目标文档 **read** 即可 |
| **`suggest_rechunk`** | ✅ · 可看建议 | ✅ | 目标文档 **read** |
| **`suggest_tags`** | ✅ · 可看建议 | ✅ | 目标文档 **read** |
| **`score_quality`** | ✅ · 可看评分 | ✅ | 目标文档 **read** |
| 见采纳/应用卡片 | ✅ · `can_adopt=false` | ✅ | SSE `approval_required` |
| 点 **采纳入库**（摘要） | ❌ UI 无钮 | ✅ | resolve adopt_summary · kb write + Admin |
| 点 **应用重切片** | ❌ UI 无钮 | ✅ | resolve apply_rechunk · admin + approval |
| 点 **应用标签** | ❌ UI 无钮 | ✅ | resolve apply_tags · kb write + Admin |
| 硬闯 resolve API | **403** | ✅ | JWT + 角色 + kb write/admin |

### 4.2 审计事件（摘要 · 无草稿/问题全文）

| 事件 | action | metadata 示例 |
|------|--------|---------------|
| 编辑 run 开始 | `agent.run_started` | run_id, thread_id, mode=edit |
| 摘要草稿生成 | `agent.approval_created` | approval_id, kind=adopt_summary, document_id, kb_id, summary_chars |
| 摘要采纳 | `agent.approval_adopted` | approval_id, kind=adopt_summary, document_id, new_document_id? |
| 摘要取消 | `agent.approval_cancelled` | approval_id, kind=adopt_summary |
| rechunk 建议 | `agent.suggestion_created` | run_id, tool=suggest_rechunk, document_id, old_chunks, suggested_chunks |
| rechunk 应用 | `agent.approval_adopted` | approval_id, kind=apply_rechunk, document_id, old_count, new_count |
| 标签建议 | `agent.suggestion_created` | run_id, tool=suggest_tags, document_id, suggested_count |
| 标签应用 | `agent.approval_adopted` | approval_id, kind=apply_tags, document_id, applied_count, skipped_count |
| 质量评分 | `agent.tool_completed` | run_id, tool=score_quality, document_id, scores |
| 越权 | `agent.approval_denied` | approval_id, reason |
| 文档重索引 | `document.reindexed`（或扩现网） | document_id, old_chunks, new_chunks |

### 4.3 乱操作表（E · G5 SSOT）

| ID | 乱操作 | 系统怎么处理 | 你怎么验 |
|----|--------|--------------|----------|
| **G5-E1** | **Member 硬闯** `POST .../resolve {adopt}`（摘要/rechunk/标签） | **403** · audit `approval_denied` | member JWT + pytest |
| **G5-E2** | Member 看建议/评分 UI | 卡片可见 · `can_adopt=false` · 无操作钮 | member 浏览器 |
| **G5-E3** | **重复采纳** 同一 `approval_id` | **409**「已处理」· 幂等 | 连点采纳 |
| **G5-E4** | **已取消** 后再 adopt | **409** · status=cancelled | cancel → adopt |
| **G5-E5** | **已采纳** 后再 cancel | **409** · status=adopted | adopt → cancel |
| **G5-E6** | 采纳后取消 | approval=cancelled · 卡片终态 · 无副作用 | 取消后刷新仍见「已取消」 |
| **G5-E7** | **无可见库** 发编辑 chat | **400**（同 G3-E3） | 无 grant 账号 |
| **G5-E8** | grant 撤销后 resolve | **403** grant_revoked | 采纳前撤 grant |
| **G5-E9** | 模型传 **越权 document_id** | tool `ok=false` · 不创建 approval | pytest |
| **G5-E10** | **无目标文档** 请求摘要/rechunk/评分 | tool `ok=false` · 助手拒答/说明 | 不存在的 doc id |
| **G5-E11** | 连点发送 | **409**（同 G3-E7） | 流式中再发 |
| **G5-E12** | 流中切模式 | Abort SSE（同 G3-E1） | 编辑流中切快速 |
| **G5-E13** | 空 message | **422** | 空框发送 |
| **G5-E14** | 他人 thread 的 `approval_id` | **404** 或 **403** | 改 UUID 硬闯 |
| **G5-E15** | **同名摘要文件** 冲突 | 自动 `_v2` 后缀（同 G4 H4-6-A） | 库内已有同名 |
| **G5-E16** | **31 次/h** 编辑发送 | **429** | 连问 31 次 |
| **G5-E17** | F5 刷新 | GET messages 带 `approval_status` · 终态仍在（同 H4-3-B） | adopt/cancel 后刷新 |
| **G5-E18** | rechunk 中**并发查询**文档 | 旧 chunks 仍可检索 · 新 chunks 逐步就绪 · citation 可能漂移 | rechunk 中搜文档 |
| **G5-E19** | 标签包含**非法字符** | apply_tags **服务端校验** · 拒绝非法标签 · 返回 `rejected_tags: [...]` | 传入 `<script>`, emoji |
| **G5-E20** | 标签建议**全重复**（全部已在 metadata） | suggest_tags 返回 `suggested_tags: []` · 无 approval 卡片 | 文档已有所有建议标签 |
| **G5-E21** | 评分请求无内容文档 | `score_quality` `ok=false` · 说明「文档无足够内容评分」 | 空文档/极短文档 |
| **G5-E22** | rechunk 建议无改进空间 | `suggest_rechunk` `ok=true` · `issues: []` · `suggested_chunks = current_chunks` · 无 approval 卡片 | 已是最优切片 |
| **G5-E23** | Member 取消**自己的 pending 卡** | ✅ · 同 G4 H4-5-B · 可取消 | member cancel |
| **G5-E24** | 摘要采纳写入的 **metadata 字段冲突** | 服务端决定策略：覆盖/追加/拒绝（L 窗定） | metadata.description 已有值 |

---

## G5-5 验收口径草案（A 层 + smoke）

**这节定什么**：G5 Implement 后怎么算过关——A 层命令门槛 · 浏览器 smoke · **不要求** BA-FINAL 重跑。

### 5.1 浏览器 smoke（S-G5 · 每 I 窗建议）

| # | 步骤 | 期望 |
|---|------|------|
| **S-G5-1**（摘要） | ① `demo_admin` → 编辑模式 ② 输入「为文档 X 生成摘要」③ 见摘要草稿 + 采纳卡 ④ 点采纳入库 ⑤ 检查目标库 | 卡片「已采纳」· 目标库出现新 .md 或 metadata 更新 · F5 卡片终态仍在 |
| **S-G5-2**（rechunk） | ① `demo_admin` → 编辑模式 ② 输入「分析文档 Y 的切片质量」③ 见对比视图 + 应用卡 ④ 点应用重切片 | 卡片「已应用」· 文档 chunks 数量变化 · citation 可检索 |
| **S-G5-3**（标签） | ① `demo_admin` → 编辑模式 ② 输入「为文档 Z 建议标签」③ 见多选标签卡 ④ 勾选 2 个 → 点应用 | 卡片「已应用」· 文档 metadata.tags 含新标签 · 重复标签被跳过 |
| **S-G5-4**（评分） | ① `demo_admin` → 编辑模式 ② 输入「对文档 W 做质量评分」③ 见评分 + 改进建议 | 正文展示三个维度 + 总分 · **无** 采纳卡 · 无副作用 |
| **S-G5-5**（Member） | ① `demo_member` → 编辑模式 ② 同 S-G5-1～4 ③ 看建议/评分 · 无采纳/应用钮 | 卡片 `can_adopt=false` · E1 硬闯 403 |

### 5.2 自动化门槛（A 层 · 每 I 窗必绿）

| # | 项 | 期望 |
|---|-----|------|
| **A-G5-1** | G3 + G4-min 回归 | `test_agent_*.py` 全绿 · `golden_agent_qa.json` 不回退 · FAQ 线不减分 |
| **A-G5-2** | 检索 golden | `test_retrieval_golden` 12/12 |
| **A-G5-3** | G5 边界 pytest | `test_agent_g5_*.py` 覆盖 **G5-E1/E3/E7/E9/E10/E15/E19/E22** 等核心 E |
| **A-G5-4** | resolve API（四种 kind） | adopt_summary/apply_rechunk/apply_tags 的 adopt/cancel/403/409 全路径 |
| **A-G5-5** | SSE 序 | `approval_required` 在 `done` 前 · `score_quality` 无 `approval_required` |
| **A-G5-6** | suggestion tool 副作用 | `suggest_rechunk` / `suggest_tags` 不创建 approval · 不写库 |
| **A-G5-7** | 前端 build | `npm run build` 绿 · rechunk 对比视图渲染 · 标签多选渲染 |
| **A-G5-8** | audit | 含 `adopt_summary` / `apply_rechunk` / `apply_tags` · **无**草稿全文 |

### 5.3 明确不要求（本波）

| 项 | 说明 |
|----|------|
| **BA-FINAL M1～M12 全勾** | G5 不触发全模块重验收 |
| **FAQ 线改动** | G4-min FAQ 封板 · G5 不测 FAQ 回归（但 A-G5-1 保证不倒退） |
| **批量摘要** | US-A3 进 backlog · 首版仅单文档摘要 |
| **G3/G4 浏览器表重勾** | 仅 G5 smoke 新路径 |
| **agent golden 新题** | L 窗定是否增 G5 题 · P 关不阻塞 |

### 5.4 P 关 DoD（G5 PRD）

| # | 条件 | 状态 |
|---|------|------|
| P1 | G5-1～G5-5 完成 | ✅ 2026-07-11 |
| P2 | 全文落盘本文 | ✅ 2026-07-11 |
| P3 | Tool 白名单明确（10 tool） | ✅ 见 §3.1 |
| P4 | 与 G4-min 不冲突 | ✅ FAQ 线零变动 |
| P5 | SSE 事件对齐（无新增类型） | ✅ 见 §3.3 |
| P6 | 30 秒口播可讲清四条线 | ✅ 见下 |

---

## 文档关单（G5 P · ✅ 2026-07-11）

- **G5-P** ✅ 本文 G5-1～G5-5 · 四条能力线定义 · Tool 白名单 · SSE 对齐 · E 表 24 条
- **下一关** **V** · 更新 `preview-agent-platform.html` G5 交互（rechunk 对比卡 · 标签多选卡 · 评分展示）
- **Implement** 留待 V → R → L → I 窗（若 W3 解 Defer）

### 答辩 30 秒

「G5 在 G4-min 的 FAQ 采纳链上扩第二条线——摘要草稿生成与采纳，完全复用 G4 的 `approval_required` → adopt/cancel 模式。同时新增三个建议类能力：rechunk 建议和标签建议都是只读产出建议、用户确认后 apply 类 tool 才写库；质量评分纯只读，展示在正文，无 approval 卡片。四条线共用 `edit` 模式、同一个 SSE 壳、同一套审核/审计机制。所有写操作必须人工 approval 确认，不做自动执行。」

---

**P 关 DoD 已满足** · 不写代码 · 不改 G4 · 不改 preview · 不开 Implement。
