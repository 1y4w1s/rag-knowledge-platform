# kb-pages-polish — Research

> **状态**：✅ 调研完成（2026-07-04）  
> **依据**：PRD §5.3～5.4、DESIGN-5 ③④、`design-preview.html`、现有代码  
> **边界**：不含 Wave 5.3 账号 / 5.4 成员组织、⌘K 搜索、Dashboard 全量、支付/OCR/KB ACL

---

## 1. 现状摘要（已实现）

| 域 | 已有 | 文件 |
|----|------|------|
| 列表壳 | `page-hd`、kb-grid 两列、新建弹窗、加载 skeleton、单按钮空态 | `KnowledgeBasesPage.tsx` |
| 列表数据 | `document_count` 聚合（非 N+1 二次查询） | `crud.py` `_document_counts_for_kbs` |
| 重名 | 同用户/组织 KB 名 409；前端 `parseApiError` 有文案 | `names.py` + `CreateKnowledgeBaseDialog` |
| 详情壳 | 顶栏 breadcrumb（shell）、页内 h2+描述、上传+对话、空态、2.5s 轮询 | `KnowledgeBaseDetailPage.tsx` |
| 文档表 | 文件名链预览、格式/大小/切片数/状态 badge、行 hover | `DocumentTable.tsx` |
| 上传 | 多文件、同名 409、BackgroundTasks 入库 | `upload.py` |
| 权限后端 | member 禁 POST kb / PATCH / DELETE kb / POST upload（403） | `crud.py`、`upload.py`、pytest 绿 |
| PATCH 库 | API 有，**前端无改名/改描述 UI** | `knowledge-base-api.ts` 缺 `updateKnowledgeBase` |

---

## 2. Gap 对照（PRD / DESIGN / preview）

### 2.1 列表页 ③

| 要求 | 现状 | Gap |
|------|------|-----|
| 文档数 | ✅ API + 卡片 | — |
| **最近更新时间** | 卡片用 `created_at`「今天创建」 | ❌ PRD 要「最近更新」；preview「今天更新 / 3 天前」 |
| 就绪/整理中状态点 | 无 | ❌ DESIGN 去重原则：KB 卡「文件数 + 状态点」 |
| 空态三步引导 | 单段文案 + 一按钮 | ❌ 用户要求三步（建库→上传→对话） |
| 409 重名 UX | 弹窗内 alert | ✅ 可微调样式（暖色 err token） |
| member 删库 | 按钮可见，点后 403 | ❌ 需隐藏或禁用 + 友好说明 |
| 错态/加载 | 有 skeleton + 红条 | ⚠️ 系统红，未统一 DESIGN 暖色 token |

### 2.2 详情页 ④

| 要求 | 现状 | Gap |
|------|------|-----|
| 文档表列 | ✅ 上传时间 + 操作列（1.4） | ⚠️ 删确认仍浏览器弹窗 → 1.7 Dialog |
| 失败重试 | ✅ API + 前端（1.3/1.4） | — |
| 删除文档 | ✅ API + 前端（1.3/1.4） | ⚠️ 确认 UX → 1.7 |
| 重复上传 | 仅**同名** 409（`upload.py`） | ❌ 改文件名可传同内容 → **3E-7 内容指纹** |
| `?status=` 筛选 | Dashboard CTA 已规划 | ❌ 详情页未读 query → **1.6** |
| **库内搜文件名** | 无搜索框 | ❌ PRD P1；**1.7 前端 MVP**；全文 → §Plan-10 |
| **资料库列表搜索** | 无 | ❌ 库多时难找 → **1.7** |
| **文档表排序** | 固定 API 顺序 | ❌ → **1.7** 表头排序 |
| member 上传 | 按钮仍渲染，仅小字提示 | ❌ 应 `disabled` + 403 toast/alert |
| 改名/改描述 | PATCH 有，无 UI | ❌ |
| 页内信息架构 | h2 与顶栏 breadcrumb 略重复 | ⚠️ 可保留 h2 去副标题重复 |

### 2.3 后端

| 字段/接口 | 现状 | 建议 |
|-----------|------|------|
| KB `updated_at` | `knowledge_bases` 表无此列 | **聚合** `GREATEST(kb.created_at, MAX(doc.updated_at))`，免迁移 |
| `processing_count` / `failed_count` | 无 | 列表 API 同次 GROUP BY 聚合，与 Dashboard 口径一致（按 doc.status） |
| DELETE document | 无 | 删 storage + chunks + pgvector（pipeline 已有 chunk 关联） |
| POST retry | 无 | 仅 `failed` → 重置 status → BackgroundTasks 重跑 pipeline |
| 上传去重 | 仅 `filename` 同库 409 | **3E-7**：`content_sha256` 同库 409；migration 009+ |
| 列表排序 | `created_at DESC` | 改 **`updated_at DESC`**（聚合后）更贴 PRD |

### 2.4 文件行数（Implement 前估）

| 文件 | 行数 | 风险 |
|------|------|------|
| `KnowledgeBaseDetailPage.tsx` | ~222 | 近软上限；加筛选/删文档/403 需拆 hooks 或子组件 |
| `KnowledgeBasesPage.tsx` | ~132 | 安全 |
| `DocumentTable.tsx` | ~58 | 加操作列后仍安全，逻辑可抽 `DocumentRowActions.tsx` |
| `crud.py` | ~175 | 加聚合仍安全 |

---

## 3. 最大风险

1. **详情页功能堆在同一文件** — `KnowledgeBaseDetailPage.tsx` 已 222 行，补 retry/delete/筛选/403 易超限；Implement 前须拆 plan。  
2. **文档 DELETE 须级联** — 需同步删 `document_chunks`、pgvector 点、磁盘文件；漏一步会 SA-3 / 脏数据。  
3. **列表「最近更新」无 DB 列** — 必须用文档 `updated_at` 聚合，且与 Dashboard「处理中/失败」计数口径一致，避免两页数字打架。

---

## 4. 建议原子任务顺序（供 plan 分节）

| # | 任务 | 依赖 |
|---|------|------|
| **1.1** | 后端：列表 API 扩展 `updated_at` + `processing_count` + `failed_count` + pytest | — |
| 1.2 | 前端：列表卡片「最近更新」+ 状态点 + member 隐藏删除 | 1.1 |
| 1.3 | 后端：文档 DELETE + POST retry + pytest | — |
| 1.4 | 前端：文档表操作列（重试/删除/上传时间）+ 轮询联动 | 1.3 |
| 1.5 | 前端：库改名/改描述对话框（PATCH） | — |
| 1.6 | 前端：空态三步、错态暖色 token、`?status=` 筛选 | 1.4 |
| **1.7** | 前端：**库内/列表文件名搜索** + 表头排序 + `?q=` | 1.6 |
| 1.8 | 前端：member 403 统一 UX + **删文档 Dialog 卡片** | 1.2, 1.4 |
| 1.9 | cockpit 同步 + build/pytest 全绿验收 | 1.6～1.8 |
| **§Plan-10** | 顶栏 ⌘K · 后端全文搜 · 分页（PRD P1） | 1.9 后 |
| **3E-7** | 后端：上传 **内容指纹 SHA-256** 同库去重 + pytest + 前端 409 文案 | 1.8 后；答辩可选亮点 |

---

## 5. 测试基线

- `backend/tests/test_knowledge_bases.py` — 12 用例（CRUD、409、SA-1、member 403）
- `backend/tests/test_upload.py` — 含 `test_org_member_cannot_upload_document`
- 无前端单测；验收靠 `npm run build` + 人工路径
