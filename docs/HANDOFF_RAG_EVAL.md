# 睿阁 RAG 系统 — 全量评测交接文档

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
| `eval_golden.py` | Hit@3 + MRR 报告（mock 向量） | 25 题，输出格式化表格 |
| `eval_golden_real.py` | 通义真实 embedding 评测 + DeepSeek LLM-as-Judge | 25 题全链路，需要 `RUN_GENERATION=1` |
| `eval_full.py` | 综合评测：Precision/F1/NDCG/MAP + 成本 + 行业对比 | 最全面的评测脚本 |
| `benchmark_hyde.py` | Baseline vs Multi-Query vs HyDE 三路对比 | 数据驱动决策 |
| `rrf_grid_search.py` | RRF 权重 Grid Search | mock 下无差异 |

### 评测结果

| 指标 | 值 |
|------|-----|
| Hit@3 | 92-100%（取决于测试集） |
| MRR | 0.9000-1.000 |
| Precision@3 | 0.31 |
| F1@3 | 0.46 |
| NDCG@3 | 0.9052 |
| 生成质量 | 4.47/5 (LLM-as-Judge) |
| 平均检索延迟 | ~593ms |
| 万次查询成本 | ~75 元（embedding 为主） |

### 关键发现

1. **中文 golden QA 已趋近天花板**（Hit@3=92-100%）
2. **Multi-Query 和 HyDE 在中文场景下无额外收益**，但成本涨 6-8 倍 → 不使用
3. **PDF 英文测试用例已修好**（内容充实 + 大小写不敏感匹配）
4. **切片策略已升级**（英文句点识别 + 20% 软上限）

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
docker exec zhiku-api touch /tmp/tests/__init__.py

# 2. 跑评测
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
| PDF 测试依赖文件 | ⚠️ 需复现 | eval_full.py 不生成 PDF 文档，GQ-4/GQ-10 需额外处理 |
| 测试账户密码 | ⚠️ 注意 | `demo_admin` 密码 `password123` 不符合新密码策略（未改） |
| Golden QA 数据集 | 🟡 可扩展 | 当前 25 题，每个问题只有 1 条相关文档标注 |

---

## 关键文件索引

| 文件 | 说明 |
|------|------|
| `docs/RAG_EVALUATION_REPORT.md` | 中文检索质量+生成质量报告 |
| `docs/FULL_EVALUATION_REPORT.md` | 英文全量报告（含 Precision/F1/NDCG/MAP） |
| `docs/TEST_ACCOUNTS.md` | 测试账号说明 |
| `docs/DEPLOY.md` | 部署说明 |
| `backend/tests/fixtures/golden_qa.json` | 25 题 golden 测试集 |
| `backend/tests/fixtures/golden_handbook.md` | 测试用员工手册 |
| `backend/tests/test_retrieval_golden.py` | Golden QA 测试 |
| `backend/scripts/` | 所有评测脚本 |

---

## 后续可做方向

1. **Golden QA 扩题**（当前 25 → 100+，标注多相关文档）
2. **负面测试用例**（测试拒答率）
3. **在线评测 Dashboard**
4. **用户反馈闭环**（点赞/点踩）
5. **A/B 测试基础设施**
