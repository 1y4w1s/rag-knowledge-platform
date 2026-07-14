# code-refactor-A · Plan

> **父 SPEC**：`docs/tasks/code-refactor-spec.md` §2 · 任务 A  
> **风险**：**高**（检索核心，改动触达 chat/search/agent 多个模块）  
> **基线**：Docker 3 services up · pytest `test_retrieval_*` 16/16 全绿 · golden 12/12 Hit@3 全绿

---

## §0 · 做什么 / 不做什么

### 做

1. **合并** `retrieval.py`（277 行）+ `retrieval_workspace.py`（275 行）→ 单一 `retrieval.py`
2. **删除** `retrieval_workspace.py`（所有 import 切换到新 `retrieval.py`）
3. **合并** `_RecallRow` 和 `_WorkspaceRecallRow` 为统一 `_RecallRow`（加可选 `kb_name` 字段）
4. **合并** `_merge_recall_rows` 和 `_merge_workspace_recall_rows` 为单一 `_merge_recall_rows`
5. **移除**重复的 `_visible_kb_clause`（两个文件完全一致，合并后留一份）
6. **保留所有公有签名不变**：`retrieve_chunks`、`retrieve_workspace_chunks`、`chunk_to_citation`、`workspace_chunk_to_citation`、`_enforce_kb_scope`、`_enforce_workspace_scope`— 全部保留为独立函数
7. **全量替换 import**：所有 `from app.services.rag.retrieval_workspace import ...` → `from app.services.rag.retrieval import ...`

### 不做

- 不改 `retrieve_chunks` / `retrieve_workspace_chunks` 的核心行为（签名、SQL、rerank、diversity 逻辑）
- 不改 `chunk_to_citation` / `workspace_chunk_to_citation` 的返回结构
- 不改 DB schema / migration
- 不改业务行为（检索结果完全一致）
- **不将两个公有 retrieve 函数合并为一个**（SQL 和参数模式本质不同，强行合并复杂度 > 收益）

---

## §1 · 改动清单

| 文件 | 操作 | 内容 |
|------|------|------|
| `backend/app/services/rag/retrieval.py` | modify | 合并 workspace 函数，net +~100 行 |
| `backend/app/services/rag/retrieval_workspace.py` | **delete** | 所有代码已移入 retrieval.py |
| `backend/app/services/agent/finalize.py` | modify | import `workspace_chunk_to_citation` → `retrieval` 而非 `retrieval_workspace` |
| `backend/app/services/agent/tools/semantic_search.py` | modify | import `retrieve_workspace_chunks` → `retrieval` 而非 `retrieval_workspace` |
| `backend/app/services/rag/chat.py` | modify | import `retrieve_workspace_chunks` + `workspace_chunk_to_citation` → `retrieval` |
| `backend/tests/test_retrieval_workspace.py` | modify | import 切换到 `retrieval` |
| 其他文件 | 不变 | 已经只从 `retrieval` import 的保持不动 |

---

## §2 · 差异分析（逐函数对比）

| 组件 | retrieval.py | retrieval_workspace.py | 合并策略 |
|------|-------------|----------------------|----------|
| `_RecallRow` | `chunk, filename, vector_similarity, fts_rank` | 同上 + `kb_name` | 统一为带 `kb_name: str \| None = None` 的 `_RecallRow` |
| `_visible_kb_clause` | ✅ 有 | ✅ 有（完全相同） | 保留一份 |
| `_vector_recall` | `kb_id` 过滤，无 kb_name | `kb_scope_clause` + JOIN KB 取 `kb_name` | 保留两个（SQL 差异大） |
| `_fts_recall` | `kb_id` 过滤，无 kb_name | `kb_scope_clause` + JOIN KB 取 `kb_name` | 保留两个 |
| `_merge_recall_rows` | 操作 `_RecallRow` | 操作 `_WorkspaceRecallRow`（结构相同） | **合并为一个**（类型统一后） |
| `_load_parent_contents` | ✅ 有 | import 自 `retrieval` | 保留一份 |
| `_enforce_kb_scope` | `kb_id` + `visible_kb_ids` 过滤 | - | 保留原名 |
| `_enforce_workspace_scope` | - | 仅 `visible_kb_ids` 过滤 | 保留原名 |
| `retrieve_chunks` | `(kb_id, query, top_k, visible_kb_ids)` | - | 保留原名 |
| `retrieve_workspace_chunks` | - | `(query, scope, org_scope, top_k)` + diversity | 保留原名 |
| `chunk_to_citation` | 6 字段 | - | 保留 |
| `workspace_chunk_to_citation` | - | 8 字段（+ kb_id, kb_name） | 保留 |
| `_excerpt` | ✅ | import | 保留一份 |
| `_exclude_parent_chunks` | ✅ | import | 保留一份 |

---

## §3 · 变更步骤

### Step 1: 在 retrieval.py 末尾追加 workspace 特有函数

追加内容（保留原名）：
- `_WorkspaceRecallRow` → 统一为 `_RecallRow(kb_name=...)`，不单独保留
- `_vector_recall_workspace` → 保留在 retrieval.py 中
- `_fts_recall_workspace` → 保留在 retrieval.py 中
- `_merge_workspace_recall_rows` → 移除，由 `_merge_recall_rows` 统一处理
- `_enforce_workspace_scope` → 保留原名
- `retrieve_workspace_chunks` → 保留原名
- `workspace_chunk_to_citation` → 保留原名

同时：
- 将 `_RecallRow` 添加 `kb_name: str | None = None`
- 将 `_merge_recall_rows` 改为兼容新 `_RecallRow`（kb_name 字段不参与合并逻辑）
- 删除 `_visible_kb_clause` 的重复定义（已经在 retrieval.py 中）
- 加入从 `retrieval_workspace.py` 带来的新 import：`KnowledgeBase`、`OrgScope`、`apply_kb_diversity`、`kb_scope_clause`、`WorkspaceScope`

### Step 2: 更新 4 个 import 方

- `finalize.py`: `from app.services.rag.retrieval import workspace_chunk_to_citation`
- `semantic_search.py`: `from app.services.rag.retrieval import ..., retrieve_workspace_chunks`
- `chat.py`: 同上
- `test_retrieval_workspace.py`: 同上

### Step 3: 删除 retrieval_workspace.py

```powershell
Remove-Item backend/app/services/rag/retrieval_workspace.py -Force
```

### Step 4: Docker rebuild + pytest 验证

```powershell
docker compose build api
docker compose up -d api
docker compose cp backend/tests api:/app/tests
docker compose exec -w /app api python -m pytest tests/test_retrieval_hybrid.py tests/test_retrieval_workspace.py tests/test_retrieval_security.py -q --no-header --tb=no --asyncio-mode=auto
docker compose exec -w /app api python -m pytest tests/test_retrieval_golden.py -q --no-header --tb=no --asyncio-mode=auto
docker compose exec -w /app/api api python -m pytest tests/test_citations.py tests/test_org_isolation.py tests/test_security_ac.py -q --no-header --tb=no --asyncio-mode=auto
```

---

## §4 · 验收强门禁

| 门禁 | 标准 |
|------|------|
| API 兼容 | 所有公有函数签名不变，所有旧 import 路径在 `retrieval.py` 中可用 |
| `retrieval_workspace.py` | 已不存在（`Remove-Item` 删除） |
| pytest A 层 | `test_retrieval_*` 4 文件 + `test_citations` + `test_org_isolation` + `test_security_ac` 全绿 |
| golden Hit@3 gate | `test_retrieval_golden.py` **12/12 全绿** |
| 人工验收 | 浏览器对话（KB 内 + workspace 各发一条验证检索结果） |

---

## §5 · 回退方案

如需回退：`git checkout -- backend/app/services/rag/retrieval.py backend/app/services/rag/retrieval_workspace.py` 恢复两个文件，然后 checkout 4 个 import 方文件。
