# EW-E1 · Plan-RAG R1-1 跨库文件名搜索 · Research

> **状态**：✅ Research 已确认（2026-07-06）  
> **依据**：`enterprise-wave-plan.md` §6 · `rag-optimization-plan.md` §4 R1-1 · `kb-pages-polish-plan.md` Plan-10  
> **边界**：**只做跨库文件名**（L3 第一层）；不含正文搜（R1-2）· 不含分页（R1-3/EW-E2）· 不含顶栏 ⌘K

---

## §1 三句话摘要（门禁用）

1. **今天**：库内文件名搜是详情页**前端 filter**（`filterDocumentsByQuery`），须先进某个库；**没有**跨库 API，也**没有** `/search` 路由。  
2. **EW-E1 目标**：新增 `GET /api/v1/search/documents?q=&workspace=`，在当前 workspace 下按文件名子串聚合所有库的文档；Dashboard **内容区**加搜索入口，结果展示文件名 + 所属库名 + 可点跳转。  
3. **风险点**：必须复用 `resolve_workspace` fail-closed（缺 workspace → 403）；SQL 须 JOIN `knowledge_bases` 用 `scope.kb_owner_clause()`，防跨空间泄漏；**不动** RAG 检索链路，**不必**跑 `test_retrieval_golden`。

---

## §2 现状盘点（代码位置）

### 2.1 搜索能力分层（与 Plan-RAG §1 对齐）

| 层 | 页面 | 实现 | 文件 |
|----|------|------|------|
| L1 找库 | `/knowledge-bases` | 前端 `?q=` 过滤库名/描述 | `kb-list-utils.ts` · `KnowledgeBasesPage.tsx` |
| L2 库内文档 | `/knowledge-bases/:id` | 前端 `?q=` 过滤 `filename` | `document-list-utils.ts` · `DocumentListToolbar.tsx` |
| **L3 跨库** | **无** | **缺口** | — |

L2 过滤逻辑（Implement 应对齐）：

```35:44:rag-knowledge-platform/frontend/src/lib/document-list-utils.ts
export function filterDocumentsByQuery(
  documents: Document[],
  query: string,
): Document[] {
  const needle = query.trim().toLowerCase();
  if (!needle) return documents;
  return documents.filter((doc) =>
    doc.filename.toLowerCase().includes(needle),
  );
}
```

### 2.2 后端：文档与权限

| 项 | 现状 |
|----|------|
| 文档表 | `documents`：`kb_id` + `filename`（512）+ `status`；索引仅 `ix_documents_kb_id`、`ix_documents_status` — **无 filename 索引** |
| 单库列表 | `GET /knowledge-bases/{kb_id}/documents` → `list_documents` + `require_kb_access(read)` |
| 工作区 scope | `resolve_workspace` → `WorkspaceScope.kb_owner_clause()` 用于 list/stats/create |
| 跨库 API | **不存在**；`main.py` 无 `search` router |

### 2.3 前端：Dashboard 与路由

| 项 | 现状 |
|----|------|
| Dashboard | `DashboardPage.tsx`：Zone A（快捷提问）+ Banner + Stats + RAG metrics；**无**跨库搜区块 |
| 路由 | `routes/index.tsx` 九页；**无** `/search` |
| 可复用 UI | `KbSearchInput`（库列表/详情已用）；`appendWorkspaceQuery` 模式与 `dashboard-api.ts` 一致 |
| DESIGN | DESIGN-5 顶栏 ⌘K → `/search` 标 🟡 Wave 5+；Plan-RAG 明确 **入口在内容区，非顶栏** |

### 2.4 测试基线

| 套件 | 用途 |
|------|------|
| `test_workspace_scope.py` | workspace 403 / personal vs org 隔离 — **EW-E1 须仿此模式** |
| `test_knowledge_bases.py` | `require_kb_access` / SA-1 跨库 403 |
| `test_retrieval_golden.py` | RAG Hit@3 — **本任务不触发**（不改 retrieval/ingestion） |

---

## §3 目标 API 草图（调研结论，非最终实现）

### 3.1 路由

```
GET /api/v1/search/documents?q={substring}&workspace={personal|org_uuid}&limit=50
Authorization: Bearer …
```

| 参数 | 规则 |
|------|------|
| `workspace` | **必填**；缺省 → 403 `缺少工作区参数`（与 list/stats 一致） |
| `q` | 必填；trim 后长度 **≥1**；空 → 400 |
| `limit` | 可选；默认 50；最大 50（防一次拉爆） |

### 3.2 响应（建议 schema）

```json
{
  "items": [
    {
      "document_id": "uuid",
      "filename": "员工手册.pdf",
      "file_type": "pdf",
      "status": "completed",
      "kb_id": "uuid",
      "kb_name": "人事制度库",
      "created_at": "2026-07-01T12:00:00Z"
    }
  ],
  "query": "手册",
  "total": 1
}
```

### 3.3 SQL 思路（单查询，无新表）

```sql
SELECT d.*, kb.name AS kb_name
FROM documents d
JOIN knowledge_bases kb ON d.kb_id = kb.id
WHERE <scope.kb_owner_clause on kb>
  AND d.filename ILIKE '%' || :q || '%'
ORDER BY d.created_at DESC
LIMIT :limit
```

- 匹配规则：**ILIKE 子串、大小写不敏感** — 与 L2 前端 `includes` 语义对齐  
- 状态：**不过滤 status**（整理中/失败也可见，列表展示 status badge；用户找得到「那份文件在哪」）  
- 性能：触发条件库 ≥5；无 filename 索引可接受；EW-E2/R1-3 再评估分页与索引

### 3.4 权限与乱操作

| 乱操作 | 系统怎么处理 | 验收 |
|--------|--------------|------|
| 缺 `workspace` | 403 | pytest 仿 T-missing |
| 伪造他人 `org_id` | 403 `无权访问该工作区` | pytest 仿 forged org |
| `q` 空/纯空格 | 400 | pytest |
| 个人空间搜 | 仅 `owner_user_id=me` 的库内文档 | 团队库文档不出现 |
| 团队空间 member 搜 | 仅该 org 库内文档 | 个人库文档不出现 |
| 硬闯 API 无 token | 401 | 现有 auth 中间件 |
| 超长 `q`（如 600 字） | 400 或截断 — **见 H2** | pytest 一条 |

**不做审计**：只读搜索，非 P0 审计事件（与 list 同级）。

---

## §4 UI 方案对比（Implement 前拍板）

### H1 · 入口放哪

| 选项 | 人话 | 选这个的后果（白话） | 默认 |
|------|------|----------------------|------|
| **H1-A Dashboard 内容区** | 概览页 Zone A 下方加「找文档」搜索框 + 结果列表 | 用户登录后首页就能搜；**不用**新路由；改 `DashboardPage` + 新子组件；九页路由表不变 | ✅ **推荐** |
| **H1-B 独立 `/search` 页** | 单独一页，Dashboard 放链接跳过去 | 多一个路由 + 面包屑；以后 ⌘K 可指向这里；**本波工作量更大** | — |

### H2 · 超长关键词

| 选项 | 后果（白话） | 默认 |
|------|--------------|------|
| **H2-A 拒绝** `len(q)>200` → 400 | 前后端一致拦脏输入；用户看到「关键词过长」 | ✅ **推荐** |
| **H2-B 静默截断到 200** | 用户不知道被截断，可能搜不到以为没文件 | — |

### H3 · 点击结果跳哪

| 选项 | 后果（白话） | 默认 |
|------|--------------|------|
| **H3-A 库详情 + `?q=`** | 跳到 `/knowledge-bases/{kb_id}?q=文件名`；与 L2 一致，用户在该库列表里看到高亮/filter 行 | ✅ **推荐** |
| **H3-B 直接预览** | 仅 `completed` 可点；`processing/failed` 要分支处理；跳 `/knowledge-bases/{kb_id}/documents/{docId}` | — |

---

## §5 建议文件清单（Implement 预估）

| 文件 | 动作 | 预估行数 |
|------|------|----------|
| `backend/app/api/search.py` | 新建路由 | ~40 |
| `backend/app/services/search/documents.py` | 新建查询 service | ~60 |
| `backend/app/schemas/search.py` | 响应模型 | ~35 |
| `backend/app/main.py` | `include_router` | +2 |
| `backend/tests/test_search_documents.py` | 新测试 | ~180 |
| `frontend/src/lib/search-api.ts` | API client | ~50 |
| `frontend/src/components/dashboard/DashboardDocumentSearch.tsx` | UI 区块 | ~120 |
| `frontend/src/pages/DashboardPage.tsx` | 挂载组件 | +5 |

**行数**：均低于 AGENTS 软上限；**不需拆文件计划**。

---

## §6 Research 退出 DoD

- [ ] §1 三句话你能复述  
- [ ] H1～H3 已读「后果」并拍板（或接受默认列）  
- [ ] `ew-e1-plan.md` 已确认 → 才可开 I 窗  
