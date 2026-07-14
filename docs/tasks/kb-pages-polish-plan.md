# kb-pages-polish — Plan

> **状态**：✅ Plan-9 ✅ · ✅ 002-W5.4 ✅ · ✅ Plan-11/2C ✅ · ✅ 002-W5.5 ✅（2026-07-04）；**下一**：Plan-D8 试跑 或 Plan-11/2.15 可选  
> **Research**：`docs/tasks/kb-pages-polish-research.md`  
> **边界**：见 research § 边界；**本波 kb-pages-polish 不含** Wave 5.3/5.4 Implement（002-plan 自有）、顶栏 ⌘K、Dashboard 全量（→ `dashboard-polish-plan.md`）、支付/OCR  
> **长期目标**：企业级（Plan-3E + §Plan-10 P1 backlog）；**Plan-10/3E 仍 deferred**（1.9 书面结论）；**2.1 为 Dashboard D-2 硬前置**

### 原子任务路线图（2026-07-04 增补搜索后）

| # | 任务 | 状态 | 依赖 |
|---|------|------|------|
| 1.1～1.5 | 列表 API / 卡片 / DELETE·retry / 操作列 / 改名 | ✅ | — |
| **1.6** | 空态三步 · `?status=` · 暖色 err token | ✅ 2026-07-04 | 1.4 |
| **1.7** | **库内/列表找文档（文件名搜索 + 排序 + IME 修复）** | ✅ 2026-07-04 | 1.6 |
| **1.8** | member 403 + 删文档 Dialog | ✅ 2026-07-04 | 1.2、1.4 |
| **1.9** | 收尾验收 · 评估 3E / P1 | ✅ 2026-07-04 | 1.6～1.8 |
| **§Plan-11** | UX 补强 2.x（**2.1 ✅ · 2A ✅ · 2B+2D ✅ · 2C ✅**） | W6 ✅ | 1.9；2.1 ✅ → D-2 可开 |
| **§Plan-10** | 跨库找文档 · 全文搜 · 分页（PRD P1） | 📋 deferred | 1.9 |
| **§Plan-3E** | 审计 · 清盘 · 去重 · 软删… | 📋 deferred | 1.9 |

---

## Plan-1 · 原子任务 1.1 — 后端列表 API 扩展 ✅ 已完成（2026-07-04）

**这节定什么**：让 `GET /knowledge-bases` 返回 PRD 列表卡片所需的「最近更新」与整理/失败计数，一次 SQL 聚合，不加表迁移。

**做什么**

| 项 | 内容 |
|----|------|
| Schema | `KnowledgeBaseResponse` 增：`updated_at: datetime`、`processing_count: int`、`failed_count: int`（默认 0） |
| 聚合逻辑 | 每库 `updated_at = GREATEST(kb.created_at, COALESCE(MAX(doc.updated_at), kb.created_at))` |
| 计数 | `processing_count = queued + processing`；`failed_count = status=failed`（与 Dashboard `documents_by_status` 口径一致） |
| 排序 | 列表改按 `updated_at` 降序 |
| 测试 | `test_knowledge_bases.py` 补 3 用例 |

**验收**

- [x] `pytest tests/test_knowledge_bases.py -q` → 15 passed
- [x] 空库 `updated_at == created_at`；上传后 `updated_at` 更新
- [x] queued+processing → `processing_count`；failed → `failed_count`

---

## Plan-2 · 原子任务 1.2 — 前端列表卡片 UI ✅ 已完成（2026-07-04）

**做什么**

| 项 | 内容 |
|----|------|
| API 类型 | `KnowledgeBase` 增 `updated_at` / `processing_count` / `failed_count` |
| 卡片 meta | `N 篇文档 · 今天更新 / 3 天前`（用 `updated_at`，fallback `created_at`） |
| 状态点 | 标题旁 6px 圆点：就绪 `#A68B6B` · 整理中 `#CB6B3D` · 失败 `#B85A2E`（失败优先） |
| member 删库 | `canDeleteKb` 与新建同权（企业 member 不渲染删除按钮） |
| 删库确认 | `window.confirm` → `DeleteKnowledgeBaseDialog`（与新建弹窗同壳） |

**改动文件**

| 文件 | 约行数 |
|------|--------|
| `frontend/src/lib/knowledge-base-api.ts` | ~95 |
| `frontend/src/components/knowledge-bases/KnowledgeBaseCard.tsx` | ~95 |
| `frontend/src/components/knowledge-bases/DeleteKnowledgeBaseDialog.tsx` | ~85（新建） |
| `frontend/src/pages/KnowledgeBasesPage.tsx` | ~155 |

**验收**

- [x] 卡片 meta：`N 篇文档 · 今天更新/3 天前`
- [x] processing/failed 暖色状态点
- [x] 企业 member 看不到删库按钮
- [x] `npm run build` 绿

---

## Plan-3 · 原子任务 1.3 — 后端文档 DELETE + retry ✅ 已完成（2026-07-04）

**这节定什么**：资料库详情「删文档 / 失败重试」的**后端 API**；先交付 MVP 闭环（1.3→1.4 可点可用），企业级加固单列 **Plan-3E**，等 1.4～1.9 基本页面功能完成后再按优先级升级。

**长期目标**：企业级（可审计、状态机严谨、存储一致、引用可解释）。**当前阶段**：MVP 够用版，不阻塞 1.4 前端操作列。

---

### 阶段策略（MVP 现在 · 企业级后补）

| 阶段 | 何时做 | 交付什么 | 不做什么 |
|------|--------|----------|----------|
| **Plan-3A MVP** | ✅ 2026-07-04 | DELETE + retry API + pytest + 权限 SA-1 | 审计、软删、回收站、分布式锁 |
| **Plan-1.4～1.9** | 3A 之后 | 操作列、改名、空态/状态筛选、**文件名搜索**、member UX、全绿验收 | 企业级加固 |
| **Plan-3E 企业级** | 1.9 基本功能验收通过后 | 见下文 §Plan-3E | 与 Wave 5.3～5.5 并行时只挑 P0 项 |

**决策原则**：演示路径（上传→对话→删/重试）不通 → 修 3A/1.4；旧引用 404、无审计 → 记 Plan-3E，答辩前挑 1～2 条做。

---

### Plan-3A · MVP Implement ✅ 已完成（2026-07-04）

**做什么**

| 项 | 内容 |
|----|------|
| DELETE | `DELETE /knowledge-bases/{kb_id}/documents/{doc_id}` → **204**；`KbAction.write`（personal / org_admin ✅，member ❌） |
| 级联 | DB 删 `documents` 行 → FK **CASCADE** 删 `document_chunks`（含 pgvector 向量）；应用层删 `upload_dir/{kb_id}/{doc_id}/` 磁盘文件 |
| DELETE 状态 | 允许 `queued` / `processing` / `completed` / `failed`（用户可删卡住的文档） |
| 磁盘失败 | DB 仍提交；`logger.warning` 记录路径（避免「DB 无、盘有」与回滚更乱） |
| POST retry | `POST .../documents/{doc_id}/retry` → **200** + `DocumentResponse`；**仅** `status=failed`，否则 **400** |
| retry 重置 | `queued`；清 `error_message` / `chunk_count` / `processing_*`；`BackgroundTasks` → `process_document_ingestion` |
| 404 | doc 不存在或 `doc.kb_id != kb_id` |
| 403 | 无 kb 归属（SA-1）或 org member |

**不做什么**

- Plan 1.4～1.8 前端、Plan 1.9 全量验收（本任务只后端）
- audit_logs、软删除、回收站、引用失效 UI
- DELETE 禁止 `processing`（企业级见 Plan-3E）
- 删整库时清盘（老 gap，Plan-3E-4 统一 `StorageCleaner`）
- Wave 5.3～5.5、Dashboard 全量

**改动文件**

| 文件 | 动作 | 约行数 |
|------|------|--------|
| `backend/app/services/documents/lifecycle.py` | 新建 | ~115 |
| `backend/app/api/documents.py` | 增 DELETE + POST retry | ~88 |
| `backend/tests/test_documents.py` | 新建 8 用例 | ~365 |

**数据流（Implement 对照）**

```
DELETE:
  JWT → require_kb_access(write) → SELECT doc(id+kb_id)
  → 记 storage_path → DELETE documents + commit（CASCADE chunks/向量）
  → unlink 文件 + rmtree 文档目录 → 204

POST retry:
  JWT → require_kb_access(write) → SELECT doc → status!=failed → 400
  → 重置 queued + 清错误字段 → commit → BackgroundTasks(pipeline) → 200 JSON
```

**pytest（`test_documents.py`）**

| # | 用例 |
|---|------|
| 1 | 上传 completed → DELETE → documents/chunks 空 + 磁盘无文件 |
| 2 | org member DELETE / retry → 403 |
| 3 | SA-1 删他人库文档 → 403 |
| 4 | 删不存在 doc → 404 |
| 5 | failed doc → retry → completed + chunk_count>0 |
| 6 | completed doc retry → 400 |

**验收**

- [x] DELETE 级联干净（storage + chunks + pgvector）
- [x] POST retry 仅 failed → 重置 → BackgroundTasks 重跑
- [x] `pytest tests/test_documents.py -q` → 8 passed；全量 **91 passed**

---

### Plan-3 · 风险登记（MVP 接受 vs 企业级消除）

| ID | 风险（大白话） | MVP | 企业级消除（Plan-3E） |
|----|----------------|-----|------------------------|
| R-1 | 磁盘文件不会随 DB 自动删 | 3A 单文档 DELETE 手动清目录 | 3E-4 统一 `StorageCleaner`；删库同级联 |
| R-2 | 旧对话 citation 里 doc/chunk 已删，点引用可能 404 | 接受；excerpt 仍在 JSON | 3E-3 解析时标「源文档已删除」；或冗余校验 |
| R-3 | 删 `processing` 文档与后台 pipeline 极小竞态 | 接受；pipeline 见 doc=None 则退出 | 3E-2 状态机 + 409 或 generation 锁 |
| R-4 | retry 后 chunk_id 全变，旧 citation 永久失效 | 接受 | 3E-3 同上 |
| R-5 | 无删文档审计 | 接受 | 3E-1 `audit_logs` |
| R-6 | 删 KB 不清盘（既有 gap） | 不在 1.3 范围 | 3E-4 与 R-1 一并修 |
| R-7 | 改文件名可传相同内容（仅拦同名） | 接受；`upload.py` 只比 `filename` | 3E-7 内容指纹 SHA-256 同库去重 |

**P0（3A 必须挡）**：SA-1 跨库、org member 403 — pytest 四象限覆盖。

---

### Plan-3E · 企业级完善（Wave B / TECH-SEC P1）🟡 待 1.9 后

> **触发**：Plan 1.4～1.9 浏览器验收通过；或答辩/demo 暴露 R-x 需修。  
> **目标**：TECH-SEC P1「可审计、可运营」+ 存储一致 + 状态机可解释。

| ID | 项 | 做什么 | 解决啥 | 验收 |
|----|-----|--------|--------|------|
| **3E-1** | 审计 | `audit_logs` 记 DELETE doc / retry；**查询 API** `GET /admin/audit-logs`（Admin · limit/offset · action/kb_id/时间）；**审计页** `/admin/audit` | R-5 追责 | admin 可查 ✅ · UI ✅ |
| **3E-2** | 状态机 | DELETE：`processing` → **409**「整理中请稍后再删」；或 `processing_generation` 版本号 | R-3 竞态 | 并发 pytest / 压测脚本 |
| **3E-3** | 引用失效 | 预览/对话解析 citation：doc 不存在 → UI「源文档已删除」；可选保留 excerpt | R-2 R-4 | 删 doc 后旧消息点引用不 500 ✅ |
| **3E-4** | 存储一致 | `services/storage/cleaner.py`：删 doc 目录、删 kb 整树；删 KB 时调用 | R-1 R-6 | 删库后 `upload_dir` 无残留 |
| **3E-5** | 软删 + 回收站 | `documents.deleted_at`；回收站列表 / 恢复 / 定期硬删 | 误删恢复 | PRD Wave B；需迁移 |
| **3E-6** | 可观测 | 指标：ingestion 失败率、retry 次数、DELETE 磁盘失败计数 | 运营 | Dashboard 或日志聚合 |
| **3E-7** | 内容去重 | `documents.content_sha256`；上传时算哈希；**同资料库**内重复 → **409**「文件内容已存在」+ 指向已有文档名；pytest：同内容不同文件名 | R-7 改扩展名绕过 | 答辩/demo 可讲 L2 企业做法 |

**建议实施顺序**：3E-4（清盘）→ 3E-1（审计）→ **3E-7（内容去重，答辩亮点可选）** → 3E-2（状态机）→ 3E-3（引用 UI）→ 3E-5（软删，工作量大，可答辩后）。

> **3E-7 大白话**：不只比文件名，比文件「指纹」；内容一模一样、只改 `.pdf`→`.md` 也会拦住。  
> **不做（Wave B+）**：L3「仍要上传？」、L4 版本管理、L5 近似重复检测。

**与 TECH 对齐**：`TECH.md` §3.4 文档 API、§4.8 失败重试、TECH-SEC P1、`TECH-5` member 禁删文档。

---

## Plan-4 · 原子任务 1.4 — 前端文档表操作列 ✅ 已完成（2026-07-04）

**做什么**：`DocumentTable` 增上传时间列；失败行「重试」、完成行「预览·删除」；调 1.3 API；轮询联动。  
**验收**：浏览器删/重试可走通；`npm run build` 绿。  
**企业级**：删除前对 `processing` 禁用按钮（即使 3A 后端允许删，UI 可提前对齐 3E-2）。

**改动文件**

| 文件 | 动作 | 约行数 |
|------|------|--------|
| `frontend/src/lib/document-api.ts` | 增 `deleteDocument` / `retryDocument` | ~170 |
| `frontend/src/components/knowledge-bases/DocumentRowActions.tsx` | 新建 | ~90 |
| `frontend/src/components/knowledge-bases/DocumentTable.tsx` | 上传时间 + 操作列 | ~105 |
| `frontend/src/pages/KnowledgeBaseDetailPage.tsx` | 删/重试 handler + member 权限 | ~265 |

**验收**

- [x] 文档表有上传时间列
- [x] 失败行「重试」、完成行「预览·删除」可用
- [x] 删/重试后列表与 2.5s 轮询联动
- [x] `demo_member` 操作列仅预览（删/重试不显示）
- [x] `npm run build` 绿

**已知 gap（记入 Plan-8）**：删文档确认暂用浏览器 `window.confirm`，与删资料库 `DeleteKnowledgeBaseDialog` 不一致 → **1.8 换自定义 Dialog 卡片**。

---

## Plan-5 · 原子任务 1.5 — 库改名/改描述 ✅ 已完成（2026-07-04）

**这节定什么**：详情页 + 列表卡片均可编辑资料库名称/描述（企业级双入口），接已有 PATCH API；409 字段级提示；member 无写入口。

**做什么**

| 项 | 内容 |
|----|------|
| API | `updateKnowledgeBase` → `PATCH /knowledge-bases/{id}` |
| Dialog | `EditKnowledgeBaseDialog`（与新建同壳；409 显示在名称字段下） |
| 详情入口 | 顶栏「编辑」（admin/personal）；保存后同步 h2、描述、面包屑、`document.title` |
| 列表入口 | 卡片「编辑」按钮（与「进入·删除」并列）；保存后刷新卡片标题/描述 |
| member | 列表/详情均不渲染编辑；详情只读说明含「修改资料库」 |
| 清空描述 | PATCH `description: ""` → 详情恢复默认占位文案 |

**改动文件**

| 文件 | 动作 | 约行数 |
|------|------|--------|
| `frontend/src/lib/knowledge-base-api.ts` | 增 `updateKnowledgeBase` | ~115 |
| `frontend/src/components/knowledge-bases/EditKnowledgeBaseDialog.tsx` | 新建 | ~175 |
| `frontend/src/pages/KnowledgeBaseDetailPage.tsx` | 编辑入口 + Dialog | ~290 |
| `frontend/src/pages/KnowledgeBasesPage.tsx` | 列表编辑 + Dialog | ~185 |
| `frontend/src/components/knowledge-bases/KnowledgeBaseCard.tsx` | 卡片「编辑」 | ~110 |

**验收**

- [x] 详情页可改名称和描述
- [x] 列表卡片可编辑（复用同一 Dialog）
- [x] 重名 409 名称字段下友好提示
- [x] `demo_member` 无编辑按钮
- [x] `npm run build` 绿

---

## Plan-6 · 原子任务 1.6 — 空态/状态筛选/错态 token ✅ 已完成（2026-07-04）

**这节定什么**：新用户知道「建库→上传→对话」三步；Dashboard 点「去处理」能筛失败/整理中文档；错误提示不用系统红。

**做什么**

| 项 | 内容 |
|----|------|
| 空态三步 | 列表无库、详情无文档：`KbOnboardingSteps`（建库→上传→对话）；member 变体文案 |
| **`?status=`** | `processing` = queued+processing；`failed` = 失败；表上方筛选条 +「清除筛选」；与 Dashboard Banner CTA 对齐 |
| 暖色 err | `--status-err-*` + `AlertBanner`；替换 KB 列表/详情 + 建库/编辑 Dialog 的 `red-*` |
| 组件拆分 | 筛选条、空态、filter 工具抽子模块，控制 `KnowledgeBaseDetailPage` 行数 |

**不做什么（留给 1.7）**

- 按**文件名**搜索、表头排序、资料库列表搜名字

**改动文件**

| 文件 | 动作 | 约行数 |
|------|------|--------|
| `frontend/src/index.css` | 增 err token + `.alert-warm-err` | ~295 |
| `frontend/src/components/ui/AlertBanner.tsx` | 新建 | ~28 |
| `frontend/src/components/knowledge-bases/KbOnboardingSteps.tsx` | 新建 | ~115 |
| `frontend/src/lib/document-status-filter.ts` | 新建 | ~35 |
| `frontend/src/components/knowledge-bases/DocumentStatusFilterBar.tsx` | 新建 | ~58 |
| `KnowledgeBasesPage.tsx` | 改 | ~188 |
| `KnowledgeBaseDetailPage.tsx` | 改 | ~305 |
| `CreateKnowledgeBaseDialog.tsx` / `EditKnowledgeBaseDialog.tsx` | 暖色 err | ~125 / ~175 |

**验收**

- [x] 列表/详情空态三步引导（建库→上传→对话）
- [x] 详情读 `?status=processing|failed` 筛文档 + 清除
- [x] 错态统一暖色 token（非系统红）
- [x] `demo_member` 行为不退化
- [x] `npm run build` 绿

**大白话**：1.6 解决「不知道下一步干啥」和「只看失败/整理中」——**还不能按文件名搜**。

**审查 gap（2026-07-04 · 只读审查，待新对话修复）**

| ID | 严重度 | 问题 | 建议 |
|----|--------|------|------|
| ✅ P1-1 | P1 | 空库 + `?status=`：筛选条与 onboarding 三步同时出现，未走 `DocumentFilterEmptyPanel` | ✅ 2.1 调整 `KnowledgeBaseDetailPage` 渲染分支顺序 |
| 🟡 P1-2 | P1 | `KnowledgeBaseDetailPage.tsx` ~380 行，超页面软上限 200 | **1.7 开工前**拆 hook/子模块（删文档自愈、轮询等） |
| 🟡 | P2 | Dashboard Banner「去处理」→ `?status=` 未落地 | DESIGN 🟡；不挡 1.7 |

---

## Plan-7 · 原子任务 1.7 — 库内/列表查找 MVP ✅ 已完成（2026-07-04）

**这节定什么**：文档/资料库多了以后**不用肉眼翻**；先做**前端过滤 + 排序**（半天～1 天量级），对齐 PRD P1「库内搜索」的**最小可用版**，全文检索留给 §Plan-10。

> **UI/UX 定稿（2026-07-04 · 用户确认）**：**不放 AppShell 顶栏**（52px 面包屑条）。顶栏只做导航 + 用户菜单；搜索属于**当前页内容区**，紧挨要筛的列表/表格，避免和全站层级抢视线、也避免 L5 暖白壳被 Dashboard 式 ⌘K 条带破坏。

### UI/UX 布局（Implement 必须遵守）

| 页 | 搜索放哪 | 长什么样 |
|----|----------|----------|
| **④ 库详情** | **标题区下方、文档表/空态上方** — `DocumentListToolbar` 一行 | 左：圆角搜索框（`max-w-sm`～`360px`）+ 内嵌放大镜 icon；右：排序「上传时间 ↓ / 文件名 A→Z」用 **outline 胶囊** 或 segmented，与「上传/对话」按钮**不同行**（操作在上、筛选在下） |
| **③ 资料库列表** | **page-hd（标题+新建）下方、卡片 grid 上方** — `KbListSearchBar` | 同系搜索框 `max-w-md`；无卡片时不占位过高 |
| **与 1.6 筛选条** | 同一 toolbar 内：**上**状态筛选 pill（有 `?status=` 时），**下**或**左**搜索；或合并为一行「筛选 chip + 搜索框」，总高 ≤ 单行 + 可选第二行 chip |

**视觉 token（对齐 DESIGN-2，不用 Dashboard 预览里的顶栏搜样式）**

| 项 | 规格 |
|----|------|
| 输入框 | 白底 · 暖边框 `var(--line2)` · 圆角 `10px` · focus 环用 `--action` 淡色（与登录页一致，**不**用 cold zinc 默认） |
| 占位符 | 「搜索文件名…」/「搜索资料库…」· `--mut` |
| 图标 | Lucide `Search` · `#71717A` · 左侧内嵌，**不要** ⌘K 角标（那是 §Plan-10 全局搜的事） |
| 空结果 | 虚线卡片内 serif 标题 + 清除按钮 · 与 1.6 空态同壳 |

**不做（美观 + 范围）**

- ❌ `AppTopbar` / 全站壳顶栏加 search input
- ❌ 搜索与「编辑 / 上传 / 开始对话」挤在同一行（窄屏会乱）
- ❌ 搜文档正文、对话、⌘K 全局（→ §Plan-10）

**做什么**

| 项 | 内容 |
|----|------|
| **详情 · 搜文件名** | 文档表上方搜索框，placeholder「搜索文件名…」；实时 filter（大小写不敏感、子串匹配） |
| **`?q=` URL** | 与 `?status=` **可叠加**（例：`?status=failed&q=合同`）；刷新保留；「清除搜索」 |
| **详情 · 排序** | 表头可切换：上传时间（默认新→旧）、文件名 A→Z；前端 sort，不改 API |
| **列表 · 搜资料库** | `/knowledge-bases` 在 page-hd 下增搜索框，按名称/描述 filter 卡片 grid |
| **无结果空态** | 「没有匹配的文档/资料库」+ 一键清除搜索/筛选 |
| **member** | 搜索/排序只读，与 admin 同 UI（仍不能删/传/改库） |
| **IME 修复** | `KbSearchInput`：`compositionstart/end` + `isComposingRef`；中文输入法组字期间不触发 filter（red-team 审查发现） |

**不做什么**

- 搜文档**正文**、搜对话记录（→ §Plan-10 后端全文 API）
- 顶栏 **⌘K 全局搜索**、**AppShell 顶栏 search**（→ §Plan-10；且与本文「内容区搜索」分工）
- 后端分页 / 虚拟滚动（文档 **>50 篇**再评估 §Plan-10-3）
- 后端新接口（本任务 **零后端**）

**改动文件（估）**

| 文件 | 动作 | 约行数 |
|------|------|--------|
| `frontend/src/lib/document-list-utils.ts` | 新建：filterByQuery、sortDocuments | ~60 |
| `frontend/src/lib/kb-list-utils.ts` | 新建：filterKnowledgeBases | ~35 |
| `frontend/src/components/knowledge-bases/DocumentListToolbar.tsx` | 新建：搜索框 + 排序控件 | ~85 |
| `frontend/src/components/knowledge-bases/KbListSearchBar.tsx` | 新建 | ~45 |
| `KnowledgeBaseDetailPage.tsx` | 挂 toolbar；传已 filter+sort 的 documents | ~300 |
| `KnowledgeBasesPage.tsx` | 挂列表搜索 | ~210 |
| `DocumentTable.tsx` | 可选：表头排序 click 回调 | ~115 |

**改动文件**

| 文件 | 动作 | 约行数 |
|------|------|--------|
| `frontend/src/lib/document-list-utils.ts` | 新建 | ~65 |
| `frontend/src/lib/kb-list-utils.ts` | 新建 | ~45 |
| `frontend/src/components/knowledge-bases/KbSearchInput.tsx` | 新建 | ~35 |
| `frontend/src/components/knowledge-bases/DocumentListToolbar.tsx` | 新建 | ~130 |
| `frontend/src/components/knowledge-bases/KbListSearchBar.tsx` | 新建 | ~60 |
| `KnowledgeBaseDetailPage.tsx` | 改 | ~405 |
| `KnowledgeBasesPage.tsx` | 改 | ~210 |

**验收**

- [x] 搜索框在**内容区**（非顶栏），详情在表上方、列表在 grid 上方
- [x] 窄屏下 toolbar 可折行，但不与主 CTA 按钮同排拥挤
- [x] `?q=` 与 `?status=` 可同时生效；清除后恢复
- [x] 上传时间 / 文件名排序可切换
- [x] 资料库列表可按名称搜到卡片
- [x] 无匹配时有空态 + 清除
- [x] `demo_member` 可搜可看，权限不退化
- [x] 中文 IME 组字时不误筛（`KbSearchInput` composition 处理）
- [x] `npm run build` 绿

**大白话**：1.7 才是你问的「搜索栏」——**只搜名字，不搜 PDF 里面的字**；且**必须先进入某个资料库**才能搜该库里的文件名。不知道文档在哪个库 → 见 §Plan-10「跨库找文档」场景。

---

## Plan-8 · 原子任务 1.8 — member 403 + 删文档 Dialog ✅ 已完成（2026-07-04）

**这节定什么**：危险操作与权限的**统一体验**——成员点不到写操作；删文档用与删资料库同款的**圆角 Dialog**，告别浏览器灰框。

**做什么**

| 项 | 内容 |
|----|------|
| `DeleteDocumentDialog` | 复用 `DeleteKnowledgeBaseDialog` 壳；文案「确定删除「{filename}」？…」；暖色确认钮 |
| `DocumentRowActions` | `window.confirm` → 打开 Dialog；删中 disabled |
| member UX | 上传/删库/删文档/改名 disabled + toast（403 或说明文案） |
| 整理中删文档 | 操作列「—」已做；可选 toast 对齐 3E-2 文案 |

**改动文件**

| 文件 | 动作 | 约行数 |
|------|------|--------|
| `frontend/src/components/knowledge-bases/DeleteDocumentDialog.tsx` | 新建 | ~85 |
| `frontend/src/components/knowledge-bases/DocumentRowActions.tsx` | 改 | ~105 |
| `frontend/src/components/knowledge-bases/DocumentTable.tsx` | 改 | ~115 |
| `frontend/src/pages/KnowledgeBaseDetailPage.tsx` | 改 | ~480 |
| `frontend/src/components/ui/Toast.tsx` | 新建 | ~55 |
| `frontend/src/lib/member-write-message.ts` | 新建 | ~5 |

**不做什么**：toast 组件大重构、后端 3E-2、内容去重（→ 3E-7）

**验收**

- [x] 删文档为圆角 Dialog，风格与删资料库一致
- [x] `demo_member` 写操作 disabled + 友好提示
- [x] `npm run build` 绿

---

## Plan-9 · 原子任务 1.9 — 收尾验收 ✅ 已完成（2026-07-04）

**做什么**

| 项 | 内容 |
|----|------|
| 全绿 | `pytest` + `npm run build` |
| 人工路径 | `demo_admin` / `demo_member` 走 PRD §5.3～5.4 + 搜索/筛选/删库 Dialog |
| cockpit | 1.6～1.8 标 ✅，下一项指向 §Plan-10 或 3E |
| 评估 | 是否启动 **3E-4 清盘**；文档数是否接近 50 → 是否排 **§Plan-10-3 分页** |

**验收**

- [x] pytest 全绿（**91 passed**）
- [x] `npm run build` 绿
- [x] cockpit / plan 状态一致
- [x] 书面结论：3E 首项 + P1 搜索下一跳

---

## Plan-10 · kb 页 P1 backlog（1.9 之后 · 并进 Plan-RAG R1）

> **定位**：企业级「好找、扛量」；与 **Plan-3E**（好管、可追溯）互补。  
> **2026-07-05**：整体路线图见 **[`rag-optimization-plan.md`](./rag-optimization-plan.md)**（R0～R5）；本节 Plan-10 明细 = **Plan-RAG §4 R1**。

### 用户场景：不知道文档在哪个资料库

**这节定什么**：1.7 只能「进了库再搜文件名」；用户只记得「有个叫合同的 PDF」，不知道它在「人事库」还是「法务库」——**跨库定位**是 Plan-10 的主场景，不是 1.7 范围。

| 块 | 内容 |
|----|------|
| **用户怎么说** | 「我忘了这份文件在哪个资料库里」 / 「全站有没有叫 xxx 的文档？」 |
| **MVP 缺口（1.7 后仍存在）** | 列表页只能搜**资料库名称**；详情页只能搜**当前库内文件名**；**无跨库文件名索引** |
| **现在能用的权宜之计** | ① 列表搜库名（若库名含关键词）；② 逐个进库用 1.7 文件名搜；③ 进某库「开始对话」问 AI（依赖 RAG，适合记内容不记得文件名） |
| **正解路径** | **10-1** 跨库按文件名搜 → 结果带 `kb_name` + 跳转详情/预览；**10-2** 库内/跨库正文全文；**10-3** 单库文档多了再分页 |
| **UX 决策（与 1.7 一致）** | **不放 AppShell 52px 顶栏**；入口在 **Dashboard 内容区** 或独立 **`/search`**；可选 ⌘K 唤起面板，但不占顶栏常驻 input |
| **优先级怎么选** | 痛点是「**哪个库有这份文件**」→ 先做 **10-1**；痛点是「**PDF 里某段话在哪**」→ 先做 **10-2**（或继续用对话+引用） |
| **何时开工（触发条件）** | ① 1.9 验收后书面评估；② demo/答辩反复出现「找不到在哪个库」；③ 资料库 **≥5 个** 且单库文档不多（逐个进库不可接受）；④ 单库 **>30 篇** 时 10-1 常与 **10-3** 一并排 |

**1.9 评估时要写的结论（模板）**：跨库找文件名痛不痛？→ 是则 10-1；单库是否 >50 篇卡顿？→ 10-3；要不要不聊天搜正文？→ 10-2。

---

| ID | 项 | 做什么 | 解决啥 | 何时考虑 |
|----|-----|--------|--------|----------|
| **10-1** | **跨库文件名搜索** | `GET /search/documents?q=`（或等价）按 filename 聚合；结果：文件名 + 所属库 + 跳转；UI：**Dashboard 内容区或 `/search`** + 可选 ⌘K；**不在 AppShell 顶栏** | 「不知道在哪个库」；DESIGN-5 跨库找文档 | **1.9 后首选**（若跨库定位是主痛点）；库 **≥5** 或 demo 反复踩坑 |
| **10-2** | 库内/跨库全文搜索 API | `GET .../documents?q=` 或 dedicated search；pg **tsvector** / 标题+摘要+chunk 片段 | PRD P1「库内搜索（不通过聊天）」；「记得内容不记得文件名」 | 单库 **>30 篇**且前端 filter 不够；或明确要「搜 PDF 里的字」 |
| **10-3** | 文档列表分页 | API `limit/offset` 或 cursor + 表虚拟滚动 | 一次拉全表慢、内存涨 | 单库 **>50 篇**或 demo 卡顿；与 10-1 常同批 |
| **10-4** | 列表高级筛选 ✅ | 按格式 PDF/DOCX、日期范围、多 status 组合 | 运营/管理员批量处理 | 10-2 之后 · **R1-4 ✅ 2026-07-06** |
| **10-5** | 上传进度条 | multipart 百分比 | PRD P1 | 大文件 demo 需要时 |

**明确仍不做（PRD §14 / Wave 2+）**：支付积分 · OCR · KB 级 ACL · Agent 联网

**与 1.7 的分工**

| 能力 | 1.7 MVP | Plan-10 |
|------|---------|---------|
| 库内搜文件名 | ✅ 前端 filter（须先进库） | 10-1 跨库；10-2 可后端+高亮 |
| 跨库搜文件名 | ❌ | **10-1** |
| 搜正文 | ❌ | 10-2 |
| 全局搜入口 | ❌ | 10-1（Dashboard / `/search`，非顶栏） |
| 排序 | ✅ 前端两列 | 10-4 可扩展 |
| 分页 | ❌ | 10-3 |

---

## §Plan-11 · UX 补强 2.x（1.9 后 · Dashboard 衔接）

> **定位**：修 1.6～1.9 审查 gap + 用户反馈；**不替代** Dashboard 桥（`dashboard-polish-plan.md`）。  
> **PM 合议顺序**：W0 **2.1** → W4 **2A（2.2+2.7）** → W6 **2B+2D** → W8 **2.15 可选**；**2C 权限**与 002-W5.4 共享测试心智。  
> **硬门禁**：**2.1 ✅ 前禁止 Implement Dashboard D-2**（Banner 外链 `?status=` 会暴露 P1-1）。

### Plan-11 路线图

| ID | 任务 | 波次 | 状态 | 依赖 |
|----|------|------|------|------|
| **2.1** | 空库 + `?status=` 叠层 bug（P1-1） | **W0** | ✅ 2026-07-04 | — |
| **2.2** | 筛选 pill 视觉 polish | W4 · 2A | ✅ 2026-07-04 | 2.1；D-2 Banner token |
| **2.7** | KB/Dashboard 错误文案统一 | W4 · 2A | ✅ 2026-07-04 | D-7 |
| **2B** | 信息层：空态/无结果 copy 统一 | W6 | ✅ 2026-07-04 | W4 |
| **2C** | 权限 UX 补漏（member 说明一致性） | W5～W6 | ✅ 2026-07-04 | ✅ 002-W5.4 |
| **2D** | 小 polish（间距、hover、aria） | W6 | ✅ 2026-07-04 | 2B |
| **2.15** | 拆 `KnowledgeBaseDetailPage`（P1-2 ~480 行） | W8 可选 | 📋 | 2.1～2.7 稳定后 |

**依赖注（PM 评审）**

- Dashboard Banner / 统计卡外链 `?status=` 落地前，**2.1 必须 ✅**
- **2.15 文件拆分**不得在 2.1～2.7 **同一对话**并行（防改同一巨文件撞车）
- Plan-10、Plan-3E bulk **仍 deferred**；答辩前最多挑 **3E-7** 一条亮点

---

## Plan-11-1 · 原子任务 2.1 — 空库 + `?status=` 叠层修复 ✅ 已完成（2026-07-04）

**这节定什么**：修审查 gap **P1-1**——资料库**没有文档**但 URL 带 `?status=processing|failed`（例如 Dashboard Banner「去处理」）时，只显示**筛选空态**，不要和 onboarding 三步引导**同时出现**。

**根因（现状）**

```411:429:frontend/src/pages/KnowledgeBaseDetailPage.tsx
      {documents.length === 0 ? (
        <KbOnboardingEmptyPanel ... />
      ) : (
        <>
          <DocumentListToolbar ... />
          {statusFilter && statusFilteredDocuments.length === 0 ? (
            <DocumentFilterEmptyPanel ... />
```

分支按 `documents.length === 0` 一刀切 → 有 `?status=` 时也走 onboarding，筛选条与 `DocumentFilterEmptyPanel` 永远进不了。

**做什么**

| 项 | 内容 |
|----|------|
| 分支顺序 | 先读 `statusFilter`（来自 `?status=`）：**有 status 且无文档** → 渲染 `DocumentListToolbar` + `DocumentFilterEmptyPanel` |
| 真·空库 | 无 `?status=` 且无文档 → 保持 `KbOnboardingEmptyPanel` |
| 有文档 | 逻辑不变（toolbar + 表 / 搜索空态 / 筛选空态） |
| member | 行为不退化；筛选条只读 |

**不做什么**

- Dashboard Banner（→ `dashboard-polish-plan` D-2）
- 筛选 pill 视觉（→ 2.2）
- 拆文件 2.15（→ W8）
- 后端改动

**改动文件（估）**

| 文件 | 动作 | 约行数 |
|------|------|--------|
| `frontend/src/pages/KnowledgeBaseDetailPage.tsx` | 调整渲染分支 | ~490（仅小改分支，不整文件重构） |

**验收**

- [x] 空库直接打开详情 → 仍显示 onboarding 三步
- [x] 空库打开 `/knowledge-bases/{id}?status=failed` → **仅**筛选条 +「没有失败的文档」空态，**无** onboarding
- [x] 空库 `?status=processing` 同上
- [x] 有文档 + `?status=failed` 且全成功 → `DocumentFilterEmptyPanel`（1.6 回归）
- [x] `demo_member` 路径不退化
- [x] `npm run build` 绿

**大白话**：Dashboard 以后会说「你有失败文件，点我去处理」——若库其实是空的，详情页应说「这里没有失败的文档」，而不是又弹一套「请先上传」教程。

**完成后**：cockpit W0 ✅；方可开 `dashboard-polish-plan` **W3 D-2**。

---

## Plan-11-2A · 原子任务 2.2 + 2.7 — 筛选 pill 视觉 + 错误文案统一 ✅ 已完成（2026-07-04）

**这节定什么**：W4 视觉与错态收口——库详情 `?status=` 筛选 pill 与 Dashboard Banner **同一套暖色 token**；KB/Dashboard API 层统一把 FastAPI 原始 `Not Found` 翻成中文，错态条不再露英文。

**做什么**

| 项 | 内容 |
|----|------|
| **2.2 pill** | `DocumentStatusFilterBar` 改为圆角胶囊 + 6px 状态点；`processing` → `status-filter-pill-proc`（对齐 Banner 整理中）；`failed` → `status-filter-pill-err`（对齐失败 Banner） |
| **2.2 去重** | `DocumentListToolbar` 复用 `DocumentStatusFilterBar`，删除内联重复条 |
| **2.7 共享层** | 新建 `lib/api-error.ts`：`normalizeDetailMessage` / `readApiErrorDetail` / `statusFallbackMessage` |
| **2.7 接入** | `knowledge-base-api` / `document-api` / `dashboard-api` 的 `parseApiError` 走共享层；保留 document DELETE/retry 旧后端探测文案 |
| **2.7 页面** | `KnowledgeBaseDetailPage` 删除逻辑去掉对 raw `Not Found` 的分支 |

**不做什么**

- 2B 空态 copy 统一、2D 间距/hover/aria（→ W6）
- 002-W5.3 改密、chat/auth 全站 err（本波仅 KB + Dashboard API）
- 2.15 拆 `KnowledgeBaseDetailPage`

**改动文件**

| 文件 | 动作 | 约行数 |
|------|------|--------|
| `frontend/src/index.css` | 增 `status-filter-pill-proc/err` | ~320 |
| `frontend/src/components/knowledge-bases/DocumentStatusFilterBar.tsx` | pill 视觉 + 状态点 | ~95 |
| `frontend/src/components/knowledge-bases/DocumentListToolbar.tsx` | 复用 FilterBar | ~95 |
| `frontend/src/lib/api-error.ts` | 新建共享 err 文案 | ~70 |
| `frontend/src/lib/knowledge-base-api.ts` | parseApiError 接入 | ~95 |
| `frontend/src/lib/document-api.ts` | parseApiError 接入 | ~175 |
| `frontend/src/lib/dashboard-api.ts` | parseApiError 接入 | ~55 |
| `frontend/src/pages/KnowledgeBaseDetailPage.tsx` | 删 Not Found 分支 | ~490 |

**验收**

- [x] `?status=processing` → 暖褐 pill + `#CB6B3D` 点；`?status=failed` → 暖红 err pill + `#B85A2E` 点
- [x] 404/错态无 raw「Not Found」（资料库不存在 / 文档不存在 / 无法加载统计数据）
- [x] `demo_member` 筛选只读、预览不退化
- [x] `npm run build` 绿

**大白话**：从 Dashboard 点「去处理」进库详情，顶上筛选标签的颜色和 Dashboard 横幅是一套暖色；加载失败时看到的是「资料库不存在」而不是英文 Not Found。

**完成后**：cockpit W4 ✅；下一 **W6 Plan-11/2B+2D** 或并行 **002-W5.3**。

---

## Plan-11-2B+2D · 原子任务 2B + 2D — 空态 copy 统一 + 间距/hover/aria ✅ 已完成（2026-07-04）

**这节定什么**：W6 信息层收口——库列表/库详情所有「无结果」空态用**同一套标题句式 + 虚线卡片壳**；筛选空态标题对齐 2.1（「没有失败的文档」）；排序 pill、清除钮补 hover/focus/aria。

**做什么**

| 项 | 内容 |
|----|------|
| **2B 共享 copy** | 新建 `lib/kb-empty-copy.ts`：筛选 / 库内搜 / 列表搜三类标题+说明 |
| **2B 筛选标题** | `failed` →「没有失败的文档」；`processing` →「没有整理中的文档」 |
| **2B 搜索标题** | 保持「没有匹配的文档/资料库」；说明统一「试试其他关键词，或清除搜索查看全部」 |
| **2B 共享壳** | 新建 `KbResultEmptyPanel`；筛选/搜索空态 + onboarding 空态共用 `.kb-result-empty` |
| **2D 间距** | 空态 `py-14`、`mt-3` 说明、`mt-6` CTA（4/8 节奏） |
| **2D hover** | `.kb-result-empty-clear`、排序 `.kb-sort-pill-*` 200ms 过渡 |
| **2D aria** | 空态 `role="region"` + `aria-labelledby/describedby`；筛选无结果 `aria-live="polite"`；清除筛选 `aria-label` |

**不做什么**

- 002-W5.3 改密、002-W5.4 成员页（→ 002-plan）
- 2C 权限 UX、2.15 拆详情页（→ W8 可选）
- Dashboard / chat 空态（本波仅 KB 列表+详情）

**改动文件**

| 文件 | 动作 | 约行数 |
|------|------|--------|
| `frontend/src/lib/kb-empty-copy.ts` | 新建统一 copy | ~35 |
| `frontend/src/components/knowledge-bases/KbResultEmptyPanel.tsx` | 新建共享壳 | ~45 |
| `frontend/src/index.css` | `.kb-result-empty` / sort pill token | ~350 |
| `DocumentStatusFilterBar.tsx` | 接共享壳+copy+aria | ~100 |
| `DocumentListToolbar.tsx` | 搜索空态+sort pill class | ~115 |
| `KbListSearchBar.tsx` | 列表搜索空态 | ~65 |
| `KbOnboardingSteps.tsx` | onboarding 共用壳+aria | ~135 |

**验收**

- [x] 空库 `?status=failed` → 标题「没有失败的文档」+「清除筛选」钮
- [x] 库内搜无匹配 →「没有匹配的文档」+ 说明含关键词 +「清除搜索」
- [x] 列表搜无匹配 →「没有匹配的资料库」+ 同上句式
- [x] onboarding / 筛选 / 搜索空态视觉同一虚线卡片壳
- [x] 排序 pill 有 hover + focus ring；筛选清除有 `aria-label`
- [x] `demo_member` 筛选只读、预览不退化
- [x] `npm run build` 绿

**大白话**：搜不到或筛不到时，三处空态长得一样、读起来一样顺；从 Dashboard 点「去处理」进空库，会看到「没有失败的文档」而不是绕口的「没有失败状态的文档」。

**完成后**：cockpit W6 ✅；下一 **002-W5.3** 改密 或 **Plan-11/2C** 权限 UX。

---

## Plan-11-2C · 原子任务 2C — 企业成员权限 UX 全站一致 ✅ 已完成（2026-07-04）

**这节定什么**：002-W5.4 后端 RBAC 已绿，但前端各页对 `demo_member` 的 **隐藏 vs 禁用** 策略不一致（文档表仍露灰「删除/重试」、Dashboard 仍露「创建资料库」、组织页无路由守卫、对话/预览仍用系统红错态）。本波统一权限 UX，共享文案与 helper，**不动** chat 流式逻辑与后端 API。

**全站策略（hide / disable 二选一，禁止混用）**

| 策略 | 适用场景 | 页面表现 |
|------|----------|----------|
| **hide** | 成员**不应看到**的管理/破坏性入口 | 不渲染按钮/链接/侧栏项 |
| **disable + toast** | 成员需知道「有此能力但无权限」的写操作 | 灰色按钮可点 → Toast 说明联系管理员 |
| **只读 + 提示条** | 成员主工作区 | 一行 `MemberReadOnlyHint` 说明边界 |

**逐页 hide / disable 定稿**

| 页面 / 区域 | demo_admin / 个人版 | demo_member | 策略 |
|-------------|---------------------|-------------|------|
| 侧栏 · 成员管理 / 组织设置 | 显示 | **hide** | hide |
| 路由 `/organization/*` | 可进 | **重定向** `/dashboard` | hide（`OrgAdminGuard`） |
| 资料库列表 · 新建 | 显示 | **hide** | hide（已有，回归） |
| 资料库列表 · 卡片编辑/删除 | 显示 | **hide** | hide（已有，回归） |
| 资料库列表 · 成员提示 | — | 有库时显示 hint | 只读提示 |
| 资料库详情 · 上传 / 编辑库 | 可用 | **disable + toast** | disable |
| 资料库详情 · 文档表删/重试 | 显示 | **hide**（仅「预览」） | hide |
| 资料库详情 · 成员提示 | — | 显示 hint | 只读提示 |
| Dashboard ZoneA · 创建资料库 | 显示 | **hide** | hide |
| Dashboard ZoneA · 上传文档 | 链最近库 | **改为「查看资料库」** | hide 写入口 |
| Dashboard 失败 Banner 副文案 | 重试/重新上传 | **联系管理员** | copy 分支 |
| 对话 / 预览 · 加载错态 | 暖色 `AlertBanner` | 同左 | 2.7 延伸（禁系统红） |
| 账号设置 | 全功能 | 只读组织信息 | 已有 |

**文案清单（`lib/member-write-message.ts` + 新增 copy）**

| key / 用途 | 文案 |
|------------|------|
| `MEMBER_WRITE_BLOCKED_MESSAGE` | 企业成员仅可查看与对话，上传、删除等写操作需联系管理员。 |
| `PERMISSION_DENIED_MESSAGE` | 没有权限执行此操作，请联系企业管理员。 |
| `MemberReadOnlyHint`（详情/列表） | 企业成员仅可查看文档与对话；上传、删除文档、修改资料库需联系管理员。 |
| Dashboard 失败 Banner（member） | 请在资料库中查看失败项，如需重试请联系管理员。 |
| Dashboard 失败 Banner（admin） | 请在资料库中查看失败项并重试或重新上传。 |
| OrgAdminGuard（无 toast） | —（静默回概览） |

**做什么**

| 项 | 内容 |
|----|------|
| **共享 helper** | 新建 `lib/org-permissions.ts`：`isEnterpriseMember` / `canWriteKnowledgeBase` |
| **共享 hint** | 新建 `MemberReadOnlyHint.tsx` |
| **路由守卫** | 新建 `OrgAdminGuard`；`/organization/members`、`/organization/settings` 包裹 |
| **文档表** | `DocumentRowActions`：member 失败行「—」、成功行仅「预览」；移除 `MemberBlockedAction` |
| **Dashboard** | `DashboardZoneA` 收 `canWriteKb`；member 隐藏创建、上传改查看 |
| **Dashboard Banner** | `DashboardStatusBanner` 失败副文案按角色分支 |
| **错态** | `ChatPage` / `DocumentPreviewPage` 系统红 → `AlertBanner` |
| **详情/列表** | 用 helper 替换内联 `canUploadDocuments`；列表有库时 member 显示 hint |

**不做什么**

- Plan-10、3E、D-5/D-6、2.15 拆详情页、Banner redo、002-W5.5 demo 脚本
- chat `parseApiError` 接共享层（可后续小 PR；本波仅页面错态 visual）
- 后端 RBAC 改动（002-W5.4 已覆盖）
- auth 表单系统红（登录页独立域，不在本波）

**改动文件**

| 文件 | 动作 | 约行数 |
|------|------|--------|
| `frontend/src/lib/org-permissions.ts` | 新建权限 helper | ~25 |
| `frontend/src/components/knowledge-bases/MemberReadOnlyHint.tsx` | 新建提示条 | ~15 |
| `frontend/src/components/layout/OrgAdminGuard.tsx` | 新建 admin 路由守卫 | ~15 |
| `frontend/src/routes/index.tsx` | org 路由包裹 Guard | ~95 |
| `frontend/src/components/knowledge-bases/DocumentRowActions.tsx` | member hide 删/重试 | ~90 |
| `frontend/src/components/knowledge-bases/DocumentTable.tsx` | 移除 `onMemberWriteBlocked` | ~110 |
| `frontend/src/pages/KnowledgeBaseDetailPage.tsx` | helper + hint | ~490 |
| `frontend/src/pages/KnowledgeBasesPage.tsx` | helper + 列表 hint | ~225 |
| `frontend/src/components/dashboard/DashboardZoneA.tsx` | member CTA | ~115 |
| `frontend/src/components/dashboard/DashboardStatusBanner.tsx` | member copy | ~185 |
| `frontend/src/pages/DashboardPage.tsx` | 传 `canWriteKb` | ~130 |
| `frontend/src/pages/ChatPage.tsx` | AlertBanner 错态 | ~165 |
| `frontend/src/pages/DocumentPreviewPage.tsx` | AlertBanner 错态 | ~180 |

**验收**

- [x] `demo_member`：侧栏无组织菜单；直输 `/organization/members` → 回概览
- [x] `demo_member`：列表无新建/编辑/删库；详情上传/编辑灰钮 + toast；文档操作列**仅预览**
- [x] `demo_member`：Dashboard 无「创建资料库」；CTA 为「查看资料库」；失败 Banner 文案含「联系管理员」
- [x] `demo_admin`：上述写操作均可用，无退化
- [x] 对话/预览加载失败为暖色 `AlertBanner`，无 `border-red-200`
- [x] `npm run build` 绿 · `pytest` 绿（112）
- [x] `cockpit.html` / `TEST_ACCOUNTS.md` 同步

**大白话**：成员登录后，全站「不能点的 destructive 按钮」都**看不见**；「上传/改库名」这种要让他知道「有这功能但没权限」的，保留灰色按钮一点就 Toast；Dashboard 不再骗他去「创建资料库」；对话页报错也不再是刺眼的系统红。

**完成后**：cockpit Plan-11/2C ✅；下一 **002-W5.5** demo 或 **Plan-11/2.15**（可选拆分）。

---

## Plan-W5.5 · 002-W5.5 — 企业双账号 15 分钟答辩脚本 ✅ 已完成（2026-07-04）

**这节定什么**：`002-plan.md` Wave 5.5 交付物——可计时、可脱稿的企业 admin/member 现场操作稿；与 `dashboard-polish-plan.md` Plan-D8 合并验收（脚本先就绪，D-8 再计时试跑）。

**做什么**

| 项 | 内容 |
|----|------|
| 文档 | `docs/ENTERPRISE_DEMO_SCRIPT.md` |
| 账号 | `demo_admin` / `demo_member`，与 `docs/TEST_ACCOUNTS.md` 一致 |
| 主线 | admin：Dashboard → 组织/成员 → 建库上传 → 预览 → 对话引用 + AC-4 → member：只读权限 UX →（可选）member 对话 |
| 演示文档 | `backend/tests/fixtures/golden_handbook.md`（对齐 `golden_qa.md`） |
| 计时 | §3 主流程约 15 分钟；改密见附录（不打断主线） |

**不做什么**

- 代码改动、Plan-10/3E/D-5/D-6、2.15 拆文件、Banner redo
- 现场真实改密（除非附录单独演示 W5.3）

**验收**

- [x] 脚本覆盖 admin 写路径：Dashboard、组织设置、成员管理、建库上传、预览、对话引用
- [x] 脚本覆盖 member 只读路径：Dashboard CTA、列表 hint、详情灰钮、操作列仅预览、OrgAdminGuard
- [x] 与 `TEST_ACCOUNTS.md` 凭证与角色一致
- [x] 含 15 分钟计时表 + AC-2/3/4/5/6 对照 + D-8 试跑记录表
- [x] `cockpit.html` / `AGENTS.md` 同步

**大白话**：答辩当天照着脚本点——先管理员秀「上传+AI 带引用」，再换成员账号秀「看得到、改不了」；15 分钟内讲完企业版故事。

**完成后**：下一 **Plan-D8** 按脚本计时试跑，或 **Plan-11/2.15**（可选拆分）。
