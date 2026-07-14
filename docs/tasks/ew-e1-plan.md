# EW-E1 · Plan-RAG R1-1 跨库文件名 API + Dashboard 入口 · Plan

> **状态**：✅ Implement 完成（2026-07-06）  
> **Research**：`ew-e1-research.md`  
> **父 plan**：`enterprise-wave-plan.md` §6 · `rag-optimization-plan.md` §4 R1-1  
> **Implement**：你确认本节后 **单开 I 窗**，严格本 plan 原子任务

---

## §0 做 & 不做

| 做 | 不做 |
|----|------|
| `GET /search/documents` 跨库文件名 ILIKE 子串 | R1-2 正文/tsvector 搜 |
| `workspace` 必填 + scope SQL 隔离 | 顶栏常驻搜索 / ⌘K 全局面板 |
| Dashboard **内容区**搜索框 + 结果列表 | 独立 `/search` 路由（除非 H1 改选 B） |
| 结果：文件名 + 库名 + status + 跳转库详情 `?q=` | EW-E2 分页 · R1-3 limit/offset 详情表 |
| pytest 权限/隔离/空参 · `npm run build` | 改 RAG 检索 · `test_retrieval_golden` |
| 过关同步 `cockpit.html` EW-E1 ✅ | 审计日志 · API rate limit（只读 GET，沿用全局即可） |

---

## §1 默认拍板（Research H1～H3 · 你可改）

| 假设 | 默认 | 状态 |
|------|------|------|
| H1 入口 | Dashboard 内容区（Zone A 与 Banner 之间） | ✅ |
| H2 超长 q | `len>200` → 400 | ✅ |
| H3 跳转 | `/knowledge-bases/{kb_id}?q={filename}` | ✅ |

---

## §2 原子任务（I 窗按序，一次可整波做完）

### E1-1 · 后端 API + schema + service

| 项 | 内容 |
|----|------|
| **路由** | `GET /api/v1/search/documents` |
| **Query** | `q`（必填，1～200 字符）· `workspace`（必填）· `limit`（可选，默认 50，max 50） |
| **逻辑** | `resolve_workspace` → JOIN `documents` ⋈ `knowledge_bases` → `scope.kb_owner_clause()` → `filename ILIKE %q%` → `ORDER BY created_at DESC` → `LIMIT` |
| **响应** | `SearchDocumentsResponse`：`items[]`（doc_id, filename, file_type, status, kb_id, kb_name, created_at）· `query` · `total` |
| **文件** | `api/search.py` · `services/search/documents.py` · `schemas/search.py` · `main.py` 注册 |
| **验收** | `pytest tests/test_search_documents.py` 绿（见 E1-2） |

### E1-2 · pytest 场景

| ID | 场景 | 预期 |
|----|------|------|
| S1 | personal workspace，两库各 1 文档，q 命中库 A 文件名 | 200，1 条，kb_name 正确 |
| S2 | q 命中两库 | 200，≥2 条，kb_id 不同 |
| S3 | q 无匹配 | 200，`items=[]`，`total=0` |
| S4 | 缺 workspace | 403 |
| S5 | 伪造 org workspace | 403 |
| S6 | q 空字符串 | 400 |
| S7 | personal workspace 搜不到 team 库文档 | items 不含 team 文档 |
| S8 | team workspace 搜不到 personal 库文档 | items 不含 personal 文档 |

### E1-3 · 前端 Dashboard 入口

| 项 | 内容 |
|----|------|
| **组件** | `DashboardDocumentSearch.tsx`：标题「找文档」+ `KbSearchInput` placeholder「搜索文件名，跨所有资料库…」 |
| **交互** | 输入 debounce（可复用 KbSearchInput 即时 onChange + 300ms fetch）；≥1 字符才请求；loading / error / 空结果文案 |
| **结果行** | 文件名 · 所属库名 · status badge · 整行 Link → `/knowledge-bases/{kb_id}?q={encodeURIComponent(filename)}` |
| **挂载** | `DashboardPage`：Zone A 下方、Banner 上方（空态 Dashboard 也显示，引导「先建库上传」） |
| **API** | `search-api.ts`：`fetchSearchDocuments(q, workspaceGeneration)` + `appendWorkspaceQuery` |
| **样式** | 对齐 DESIGN token；内容区宽度与 Zone A 一致；**不占顶栏** |
| **验收** | `npm run build` 绿；浏览器：两库上传同名不同库 → 搜关键词两库都出现 |

### E1-4 · 文档同步

| 文件 | 更新 |
|------|------|
| `docs/cockpit.html` | EW-E1 ✅ · meta「阶段 E 进行中/完成」· checklist |
| `enterprise-wave-plan.md` §6 | EW-E1 ✅ |
| `rag-optimization-plan.md` §4 | R1-1 标 ✅（可选一行） |
| `AGENTS.md` | 「发现层」行更新为 EW-E1 ✅（若仍写 deferred） |

---

## §3 大白话（Implement 前须听懂）

**一句话**：在概览页加一个「找文档」框，输入文件名的一部分，系统在当前空间（我的空间或团队）里**所有资料库**中查找，告诉你「哪个库里有这份文件」，点一下进那个库的详情页。

| 名词 | 人话 |
|------|------|
| 跨库搜 | 不用先进某个库，一次搜全部库里的文件名 |
| workspace | 侧栏选的「我的空间」或「团队」；搜结果不会混另一个空间 |
| ILIKE | 不区分大小写的「包含」匹配，和库详情里搜文件名一样 |
| `?q=` 跳转 | 点结果后打开库详情，地址栏带搜索词，列表自动筛到那一行 |

**你怎么验**

1. `demo_admin` 登录 → 建库 A、库 B → 各上传 `合同.pdf` / `员工手册.pdf`  
2. 概览页「找文档」搜 `合同` → 只出现库 A 那条，库名对  
3. 搜 `手册` → 命中库 B；点击 → 进库 B 详情且列表筛到该文件  
4. 切团队 workspace（若有）→ 个人库的文档**不出现**  
5. 终端：`pytest` 全绿 · `npm run build` 绿  

**这回不做**：搜 PDF 里面的字、顶栏全局搜、列表分页、搜完打开预览页。

---

## §4 门禁三题（Implement 前自答）

1. **触发点**：用户在 Dashboard 输入文件名 → `GET /search/documents?q=&workspace=`  
2. **数据流**：JWT 鉴权 → `resolve_workspace` → SQL JOIN + ILIKE → JSON items → 前端渲染 → 点击 Router 跳库详情 `?q=`  
3. **怎么验**：§3 浏览器步骤 + §2 E1-2 pytest 表  

---

## §5 Plan 退出 DoD

- [x] 你已确认 §0 边界 + §1 默认假设（或写明改动）  
- [x] §3 大白话听懂  
- [x] 开 I 窗时 @ 本文件 + `ew-e1-research.md`  
- [x] I 窗完工：E1-1～E1-4 全 ✅ · pytest · build · cockpit  
