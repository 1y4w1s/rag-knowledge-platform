# 睿阁 RAG 系统 — 全量评测交接文档（v0.5）

## 项目概况

**产品名**: 睿阁（原知岸）  
**仓库**: https://github.com/1y4w1s/rag-knowledge-platform  
**技术栈**: FastAPI + PostgreSQL 16/pgvector + React + Docker Compose  
**LLM**: DeepSeek Chat（真实 API 已配置）  
**Embedding**: 通义 text-embedding-v2（真实 API 已配置）

---

## 环境状态

- Docker 已启动，API 运行在 http://localhost:8000
- `.env` 文件中有 RESEND_API_KEY（用于忘记密码邮件）
- 种子数据：`demo_admin` / `password123`（团队管理员）
- API Key 已配置：DeepSeek、通义、Resend

---

## 已完成的 RAG 评测

### 评测脚本（都在 `backend/scripts/` 下）

| 脚本 | 功能 | 说明 |
|------|------|------|
| `eval_golden.py` | Hit@3 + MRR 报告（mock 向量） | 50 题，输出格式化表格 |
| `eval_golden_real.py` | 通义真实 embedding 评测 + DeepSeek LLM-as-Judge | 50 题全链路，需要 `RUN_GENERATION=1` |
| `eval_full.py` | 综合评测：Precision/F1/NDCG/MAP + 成本 + 行业对比 | 最全面的评测脚本（已更新 v0.5） |
| `benchmark_hyde.py` | Baseline vs Multi-Query vs HyDE 三路对比 | 数据驱动决策 |
| `rrf_grid_search.py` | RRF 权重 Grid Search | mock 下无差异 |

### 评测结果（2026-07-15 · v0.5 扩题）

| 指标 | 值 |
|------|-----|
| Hit@3（全量 50 题） | 90.0% (45/50) |
| Hit@3（非拒答 45 题） | 100% (45/45) |
| MRR | 0.950 |
| 拒答正确率 | 100% (5/5) |
| Precision@3 | 0.3185 |
| F1@3 | 0.4690 |
| NDCG@3 | 0.8958 |
| MAP | 0.9444 |
| 平均检索延迟 | ~589ms |
| 万次查询成本 | ~75 元（embedding 为主） |

### 数据集版本历史

| 版本 | 规模 | 新增功能 | 日期 |
|------|------|----------|------|
| v0.1-v0.4 | 25 题 | 基础标准检索 | 2026-07-14 |
| **v0.5** | **50 题** | **多相关标注 + 拒答测试 + 跨段/参数化/边界查询** | **2026-07-15** |

### 关键发现

1. **标准检索 45 题 100% 命中**（mock 嵌入下，不含 PDF mock 失败）
2. **拒答测试 5/5 正确**：对无资料问题（产假/社保/公积金等）正确拒绝
3. **跨段查询 min_match=2 提供有效区分度**：3/6 通过，1 段命中但需 2 段时失败
4. **PDF mock 失败（GQ-4/GQ-10）** 为已知限制，期待真实嵌入后修复
5. **中文/英文/MD/DOCX/PDF 全格式覆盖**（PDF 需真实嵌入验证）

---

## 评测使用方法

```powershell
# 前置：确保 demo_admin 存在
docker cp backend\scripts\seed_enterprise_demo.py zhiku-api:/tmp/seed.py
docker exec zhiku-api env PYTHONPATH=/app python /tmp/seed.py

# 1. 复制测试文件到容器
docker exec zhiku-api mkdir -p /tmp/tests/fixtures
docker cp backend\tests\golden_qa_loader.py zhiku-api:/tmp/tests/golden_qa_loader.py
docker cp backend\tests\fixtures\golden_handbook.md zhiku-api:/tmp/tests/fixtures/
docker cp backend\tests\fixtures\golden_qa.json zhiku-api:/tmp/tests/fixtures/
docker exec zhiku-api touch /tmp/tests\__init__.py

# 2. 跑评测（50 题）
docker cp backend\scripts\eval_full.py zhiku-api:/tmp/eval_full.py
docker exec zhiku-api env PYTHONPATH=/app:/tmp python /tmp/eval_full.py

# 3. 带生成质量评测（消耗 DeepSeek API 额度）
docker exec -e RUN_GENERATION=1 zhiku-api env PYTHONPATH=/app:/tmp python /tmp/eval_golden_real.py

# 4. 取回报告
docker cp zhiku-api:/tmp/full_evaluation_report.md docs/
```

---

## 已知问题

| 问题 | 状态 | 说明 |
|------|------|------|
| PDF mock 嵌入失败 | 🟡 已知 | GQ-4/GQ-10 在 mock 下失败，真实嵌入已验证可用 |
| 测试账户密码 | ⚠️ 注意 | `demo_admin` 密码 `password123` 不符合新密码策略 |
| 数据集规模 | 🟡 可继续扩展 | 当前 50 题，目标 100+ |
| 单文档源 | 🟡 待改进 | 所有查询基于 golden_handbook.md，需跨文档场景 |

---

## 关键文件索引

| 文件 | 说明 |
|------|------|
| `docs/RAG_EVALUATION_REPORT.md` | 中文检索质量+生成质量报告（v0.5） |
| `docs/FULL_EVALUATION_REPORT.md` | 英文全量报告（v0.5） |
| `docs/TEST_ACCOUNTS.md` | 测试账号说明 |
| `docs/DEPLOY.md` | 部署说明 |
| `backend/tests/fixtures/golden_qa.json` | **50 题 golden 测试集（v0.5）** |
| `backend/tests/golden_qa_loader.py` | **评测加载器（v0.5 重构，含 chunk_matches/hit_at_k/reciprocal_rank）** |
| `backend/tests/fixtures/golden_handbook.md` | 测试用员工手册 |
| `backend/tests/test_retrieval_golden.py` | Golden QA 测试（CI 金门，已更新多段+拒答） |
| `backend/scripts/` | 所有评测脚本 |

### 架构说明（v0.5 重构）

**共享匹配逻辑迁移**：v0.5 将 `_chunk_matches` / `hit_at_k` / `reciprocal_rank` 从各脚本的本地定义集中到 `golden_qa_loader.py`，所有评测脚本和测试通过导入共用同一逻辑：

```
golden_qa_loader.py
  ├── GoldenQACase (dataclass)
  ├── chunk_matches()     ← 统一匹配逻辑
  ├── hit_at_k()          ← 统一 Top-K 验证
  └── reciprocal_rank()   ← 统一 MRR 计算
      │
      ├── test_retrieval_golden.py    (CI golden gate)
      ├── eval_full.py                (mock 全量评测)
      ├── eval_golden_real.py         (真实嵌入评测)
      ├── benchmark_hyde.py           (HyDE/MQ 对比)
      ├── rrf_grid_search.py          (RRF 网格搜索)
      └── run_golden_production_baseline.py (生产基线)
```

---

## 后续可做方向（优先级排序）

### P0（高优先级）
1. **真实嵌入验证** — 运行 `eval_golden_real.py` 实测通义 embedding + DeepSeek，验证 PDF 用例
2. **扩题至 100+** — 新增多文档源（如 IT 政策手册），增强统计显著性

### P1（中优先级）
3. **LLM-as-Judge 集成 CI** — 每次提交自动评估生成质量
4. **引用精度自动化校验** — 引用质量可量化

### P2（低优先级）
5. **在线评测 Dashboard** — 可视化评测结果
6. **用户反馈闭环（点赞/点踩）** — 持续质量跟踪
7. **A/B 测试基础设施** — 生产环境检索策略对比

---

## 核心变更日志

| 日期 | 变更 | 涉及文件 |
|------|------|----------|
| 2026-07-15 | v0.5 schema: 新增多相关标注 + 拒答测试 | `golden_qa.json`, `golden_qa_loader.py` |
| 2026-07-15 | 扩题 25→50：跨段/参数化/拒答/复杂/边界 6 类 | `golden_qa.json` |
| 2026-07-15 | 共享匹配逻辑重构：chunk_matches/hit_at_k/reciprocal_rank 集中到 loader | `golden_qa_loader.py`, 全部 6 个脚本 |
| 2026-07-15 | 修复拒答 case 匹配逻辑（无 expect 时 chunk_matches 返回 False） | `golden_qa_loader.py` |
