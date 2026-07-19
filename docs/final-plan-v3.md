# 睿阁 RAG — 最终改进计划 v3

> 基线：Golden QA 95.6% · Expense QA ~92% · Enterprise QA 98% · Faithfulness 94%

---

## 问题清单

### A. 评测可信度（最致命）
1. **测试集校准有方法论问题** — Enterprise QA 的 content_contains 是从 chunk 直接取的，可能语义不匹配
2. **Citation Accuracy = 0%** — SYSTEM_PROMPT 要求 [片段N] 但 DeepSeek 不遵守，产品核心卖点不可证明
3. **evaluation_runs 半空表** — 一半字段是 None，CI 没跑过 runner 管道
4. **评测脚本 20+ 个无统一入口** — 该跑哪个、什么时候跑、结果怎么看，没人知道

### B. 工程健壮性
5. **Docker 单点依赖阿里云 mirror** — 如果阿里云挂了下游全断
6. **工程实践缺失** — 无 pre-commit、PR 模板、changelog、提交规范

### C. 跨领域泛化
7. **CRAG 英文 45%** — 唯一的真实悬崖

---

## 改进计划

### 1. 建统一评测入口（2 天）

目标：解决 #3、#4、部分 #1

- 创建 `scripts/run_benchmark.py`，接受三个参数：
  - `--dataset`：golden_qa | expense_qa | enterprise_qa | all
  - `--mode`：retrieval | generation | full
  - `--output`：json | md | html
- 用 BenchmarkRunner（`tests/benchmark/runner.py`）驱动，不再手写独立脚本
- runner 自动填充 `evaluation_runs` 表的所有字段（含 NDCG + breakdown）
- 删除 `tests/benchmark/tests/_*.py` 中的 15+ 个一次性调试脚本
- ✅ 验证：`python scripts/run_benchmark.py --all --mode retrieval` 一次跑通三套测试集

### 2. 修 Citation Accuracy（2 天）

目标：解决 #2

- 增强 SYSTEM_PROMPT：添加更明确的引用格式要求 + 更具体的 few-shot 示例
- 加 post-processing：如果回答中缺少 [片段N]，在 response 中注入引用信息
- 创建 `test_citation_accuracy.py`：10 次对话，验证 [片段N] 出现率 ≥ 90%
- ✅ 验证：Citation Accuracy ≥ 80%

### 3. 加固 Docker 构建（0.5 天）

目标：解决 #5

- 在 Dockerfile 中增加 PyPI 官方源作为 pip fallback
- 示例：`pip install --index-url https://mirrors.aliyun.com --extra-index-url https://pypi.org/simple -r requirements.txt`
- ✅ 验证：`docker compose build api` 在阿里云不通时自动 fallback

### 4. CRAG 英文修复（2 天）

目标：解决 #7

- 诊断 CRAG 失败模式（用 `jinaai/jina-embeddings-v2-base-zh` 768-dim 对比）
- 替换 embedding provider 或加 query 翻译层
- 重跑 CRAG 基线：目标 ≥ 70%
- ✅ 验证：CRAG Hit@3 ≥ 70%（当前 45%）

### 5. 工程实践基建（1 天）

目标：解决 #6

- 添加 `.pre-commit-config.yaml`：black + ruff + trailing-whitespace
- 创建 `CHANGELOG.md`
- ✅ 验证：`git commit` 触发 pre-commit 检查

### 6. 测试集可信度修复（1 天）

目标：解决 #1

- 对 Enterprise QA 的剩余 ~10 题表格类问题，人工审核 content_contains 语义
- 添加校验规则：content_contains 不能是纯标点/数字/符号组合
- ✅ 验证：所有 108 题的 content_contains 长度 ≥ 4 个中文字符

---

## 执行顺序

```
Week 1: 评测入口 + Citation Accuracy（1+2）
Week 2: Docker + CRAG + 工程基建（3+4+5）
Week 3: 测试集审计 + 收尾（6）
```
