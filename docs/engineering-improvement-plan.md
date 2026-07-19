# 睿阁工程化改进计划

> 版本: v1 · 2026-07-18
> 基于 P9 架构评审的 8 项改进

---

## 优先级总览

| 优先级 | 项 | 耗时 | 风险 |
|--------|----|------|------|
| **P0** | Docker 健康检查修复 | 10min | 零 |
| **P0** | `retrieval.py` 拆模块 | 2h | 中 |
| **P0** | CI 门禁正式启用 | 1h | 低 |
| **P1** | CRLF → LF 全局规范 | 30min | 低 |
| **P1** | RRF 融合参数调优 | 1h | 低 |
| **P1** | Prompt 增加 few-shot | 30min | 低 |
| **P1** | 核心 pipeline 测试补充 | 3h | 低 |
| **P2** | 迁移 squashing | 1h | 中 |
| **P2** | 代码行尾规范化 | 30min | 低 |

---

## Phase 1: P0 紧急修复（半天）

### 1.1 Docker 健康检查修复

**问题**：`docker compose up -d postgres` 后 healthcheck 一直 `unhealthy`，导致 postgres 的 `depends_on` 永远不满足，api 容器无法正常启动。只能 `docker start` 暴力启动。

**根因**：`docker-compose.yml:40` 的 healthcheck 命令 `pg_isready -U ruige -d ruige` 在容器内找不到数据目录。因为容器内 `PGDATA=/var/lib/postgresql/data`，但 `pg_isready` 默认查找 `/var/lib/postgresql/16/main/`。

**修复**：
```yaml
# docker-compose.yml:40
# 改前
test: ["CMD-SHELL", "pg_isready -U ruige -d ruige"]
# 改后
test: ["CMD-SHELL", "pg_isready -h localhost -U ruige -d ruige"]
```

加 `-h localhost` 让 `pg_isready` 通过 TCP 连接（不走 Unix socket），绕过数据目录查找问题。

**验证**：`docker compose up -d postgres` 后 10 秒内 `docker inspect ruige-postgres --format '{{.State.Health.Status}}'` 返回 `healthy`。

---

### 1.2 retrieval.py 拆模块

**问题**：`retrieval.py` 620 行，21 个函数，涵盖 4 个互不相关的职责：
1. 向量召回（`_vector_recall` + `_vector_recall_workspace`）
2. 全文检索（`_fts_recall` + `_fts_recall_workspace`）
3. RRF 融合 + rerank（`retrieve_chunks` + `retrieve_workspace_chunks`）
4. 工具函数（`_excerpt`、`_exclude_parent_chunks` 等）

两个变体（KB/workspace）各有独立的 `_vector_recall` + `_fts_recall` + `_enforce`，代码重复 70%。

**拆分方案**：

```
app/services/rag/
├── retrieval.py          # 保留：retrieve_chunks, retrieve_workspace_chunks（~200 行）
├── vector_recall.py      # 新增：_vector_recall（KB + workspace 合并为统一函数）
├── fts_recall.py         # 新增：_fts_recall（KB + workspace 合并）
├── scope.py              # 新增：_enforce_kb_scope, _enforce_workspace_scope
├── recall_types.py       # 新增：_RecallRow, 工具函数
```

**改动方式**：
1. 新建 `vector_recall.py`：提取 `_vector_recall` 和 `_vector_recall_workspace` 合并为统一 `vector_recall(db, kb_id_or_scope, query_vec, limit, visible_kb_ids)`
2. 新建 `fts_recall.py`：同上合并两个变体
3. `retrieval.py` 从新模块 import，保留 `retrieve_chunks` 和 `retrieve_workspace_chunks`
4. 因为只是搬代码+改 import，改完后跑 Golden QA 296 题验证回归

**验证**：Golden QA 296 题 Hit@3 不变（86.5%）。

---

### 1.3 CI 门禁启用

**问题**：`.github/workflows/regression.yml` 写好了但从来没在 PR 上跑过。`docs/baseline.json` 建了但改代码后全靠手动跑。

**修复**：
1. 确认 `regression.yml` 的 trigger 配置正确（`pull_request → paths → backend/app/services/rag/**`）
2. 在 mock 模式下测试 workflow（提交一个空 PR 看 CI 触发）
3. CI 跑 50 题抽样子集（零费用，~30 秒），结果写 PR comment

**验证**：CI 在 PR 提交后 2 分钟内完成回归检测并 comment。

---

## Phase 2: P1 重要改进（1 天）

### 2.1 CRLF → LF 全局规范化

**问题**：多文件编码不统一（BOM、CRLF/LF 混用），改代码时频繁出现编码错误。

**修复**：
```powershell
# 项目根目录执行
Get-ChildItem -Recurse *.py | ForEach-Object {
    $content = [System.IO.File]::ReadAllText($_.FullName)
    $content = $content.Replace("`r`n", "`n")  # CRLF → LF
    $utf8 = New-Object System.Text.UTF8Encoding $false
    [System.IO.File]::WriteAllText($_.FullName, $content, $utf8)
}
```

**验证**：`git diff --stat` 确认只有实际修改过的文件变更，无意外改动。

---

### 2.2 RRF 融合参数调优

**问题**：`DEFAULT_RRF_K = 60` 对两个通道等权处理。FTS 刚恢复但 rank 远低于向量，RRF 不感知通道质量。

**修复**：
```python
# rrf.py
# 根据最大向量相似度动态调整 RRF K 值
# 向量质量高（max_sim > 0.7）→ K=60 偏向量
# 向量质量低（max_sim < 0.5）→ K=30 偏 FTS（FTS 贡献更大）
adaptive_k = int(60 * (1 - max_sim + 0.3))  # 0.5~0.9 → 48~18
```

**验证**：Golden QA 对比 Hit@3 和 MRR。

---

### 2.3 Prompt 增加 few-shot

**问题**：当前 CoT prompt 只有指令没有示范。LLM 理解"步骤 3 验证"全靠猜测。

**修复**：在 `SYSTEM_PROMPT` 末尾增加 1 个 few-shot 示例：
```
示例：
用户：年假有多少天？
检索片段：[片段1] 员工年满一年后可享受年假10天...
步骤 1 - 提取事实：年假10天（来源：片段1）
步骤 2 - 回答：根据规定，员工每年有10天年假。
步骤 3 - 验证："10天"在片段1中有原文支持 ✅ → 输出答案
```

**验证**：LLM-as-judge 评测对比。

---

### 2.4 核心 pipeline 测试补充

**缺失的测试**：
| 测试 | 说明 | 行数 |
|------|------|------|
| `test_retrieval_concurrent.py` | 10 并发检索 + 验证结果不串 | ~100 |
| `test_long_context.py` | 10 轮对话后 context 不溢出 | ~80 |
| `test_upload_and_retrieve.py` | 上传 100 文档后检索 | ~120 |

**验证**：`pytest tests/test_retrieval_concurrent.py -v` 通过。

---

## Phase 3: P2 后续改进

### 3.1 迁移 squashing（可选）

当前 35 个 alembic 版本，前 10 个（001→010）是 MVP 早期内容，不会再回滚。考虑 squash 成 1 个初始版本。

### 3.2 行尾规范化

在 `.gitattributes` 中添加：
```
*.py text eol=lf
*.md text eol=lf
*.yml text eol=lf
```

---

## 验收标准

| 检查项 | 通过标准 |
|--------|---------|
| Docker 健康检查 | `docker compose up -d postgres` → 10s 内 healthy |
| retrieval.py 行数 | < 300 行 |
| CI 回归 | mock 模式 50 题 < 2 分钟 |
| CRLF 修复 | `git grep -I $'\r$' *.py` 返回 0 |
| RRF 调优 | Golden QA MRR >= 0.97 |
| Few-shot prompt | 评测无退化 |
| 新增测试 | 3 个测试文件，均通过 |
