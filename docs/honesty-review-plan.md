# 睿阁 RAG 诚实性修复计划（阶段二 · 重排序版）

> 基于 2026-07-19 全系统诚实性审查结果
> 原则：分步修复，每一步完成后验证再走下一步
> 重排序理由：先清测试集再建门禁最后啃硬骨头

---

## 真实状态总览

```
生产链路：  文档解析(真) → 切片(真) → 嵌入fastembed(真) → 向量+FTS+RRF(真但权重靠拍)
                                                                         ↓
                                                                rerank(默认关闭)
                                                                         ↓
                                                                 生成(真DeepSeek)
                                                                         ↓
                                                                Faithfulness(同一模型，有偏差)

CI/测试：   pytest → mock嵌入(SHA256哈希) → 测的是FTS，不是语义检索 ✓完全虚假
                                                                         ↓
           benchmark.yml(默认mock) / regression.yml(硬编码mock) / nightly(跳过生成)

评测：      Golden QA(真但有20%免费分+1条重复题) / Enterprise QA(循环验证,虚高18pp)
           外部基准(全部手动下载，从未跑过)
```

---

## 修复顺序

### 第一步：Golden QA 清理 ← 先做

**目标**：消除测试集中的明显脏数据，使 Golden QA 基线可信。

**改动**：
- 删除 GQ-9（与 GQ-1 完全重复：query="年假有多少天？"，expect 相同）
- 拒答题从 Hit@K 计算中排除，改为独立的 `correct_rejection_rate` 报告
- 不改动现有题目的 query/expect（保持向后兼容）

**验证标准**：109 题（去重后），拒答题独立报告，Hit@3 可能有微小下降。

**工作量**：2 小时

**前置依赖**：无

---

### 第二步：CI 真实嵌入 job

**目标**：让 PR CI 使用真实 fastembed 嵌入跑检索测试，作为质量门禁。

**改动**（3 个文件）：
- `test_retrieval_golden.py:65-68` → mock fixture 加 `RAG_REAL_EMBEDDING=1` 跳过条件
- `ci.yml` → 新增 `rag-real-embedding` job，失败即阻断 CI
- `conftest.py:129-136` → 已有 `RAG_REAL_EMBEDDING` 检查，无需改动

**验证标准**：新 job 在 PR CI 中必须通过，否则 CI 标红。

**工作量**：半天

**前置依赖**：无（独立于 Golden QA 清理）

---

### 第三步：Enterprise QA 重建

**目标**：打破 content_contains 循环验证，拿到真实中文检索基线。

**改动**：
- 对 6 份 acme_*.md 文档，人工编写独立于 chunk 内容的 content_contains
- 确保预期答案片段的文字仅出现在目标章节，不在多个位置重复
- 重新运行 Enterprise QA 基线

**验证标准**：新测试集下 Hit@3 ≈ 实际检索能力（预期 60-80%），不再有假阳性。

**工作量**：半天到一天（需人工）

**前置依赖**：第一步（Golden QA 清理）已完成，确保测试集编撰标准一致。

---

### 第四步：Expense QA 精确匹配

**问题**：原始基线 41%，通过修断言格式跳到 92%。系统能力未变。

**修复**：
- 改用精确匹配或格式化匹配，不依赖文档原文的排版格式
- 记录 41% 为真实基线
- 或改用外部标准测试集替代

**工作量**：2 小时

---

### 第五步：外部基准接入

**问题**：CRAG、RAGBench、RAGEval、MIRAGE 加载器全部标记 TODO，从未在 CI/Nightly 中跑过。

**修复**：
- 完成 CRAG 数据集的自动下载逻辑
- 将 CRAG 英文检索加入 nightly pipeline
- 移除永远不实现的基准加载器死代码

**工作量**：1 天

---

### 第六步：评测报告完整性

**问题**：所有评测报告只报告均值，无置信区间、无失败数。

**修复**：
- `RetrievalMetrics` 增加 `std_*` 字段
- `GenerationMetrics` 增加 `failed_queries` 计数
- 报告模板中包含置信区间行

**工作量**：半天

---

### 第七步：RRF 权重验证 + Rerank 启用

**问题**：RRF 权重 `1.0:1.2` 无 ablation 数据。Rerank 默认关闭/默认 mock。

**修复**：
- 在 Golden QA 上做 RRF 权重扫描（0.5~2.0）
- 生产默认启用 rerank（bge-reranker-v2-m3 via ONNX）
- 移除 mock rerank 代码

**工作量**：1 天（含 ablation 实验）

---

## 当前完成状态

| 步骤 | 工作量 | 前置依赖 | 状态 |
|------|--------|----------|------|
| ① Golden QA 清理 | 2 小时 | 无 | ⏳ 待执行 |
| ② CI 真实嵌入 job | 半天 | 无 | ⏳ 待执行 |
| ③ Enterprise QA 重建 | 半天~1天 | ① 完成 | ⏳ 待执行 |
| ④ Expense QA 精确匹配 | 2 小时 | — | ⏳ 待执行 |
| ⑤ 外部基准接入 | 1 天 | — | ⏳ 待执行 |
| ⑥ 评测报告完整性 | 半天 | — | ⏳ 待执行 |
| ⑦ RRF 权重 + Rerank | 1 天 | — | ⏳ 待执行 |

---

## 附录：已完成的审计交付物

| 文档 | 内容 |
|------|------|
| `docs/data-honesty-report.md` | 8 大水分来源详细分析 |
| `docs/real-baseline-2026-07-19.md` | 所有测试集真实嵌入基线数据 |
| `docs/postmortem-2026-07-19.md` | 四层根因复盘 |
| `docs/honesty-review-plan.md`（本文） | 重排序后的分步修复计划 |
| `docs/step1-ci-real-embedding-plan.md` | 第②步 CI job 详细实施方案 |

## 附录：已修复的代码

| 文件 | 修复 |
|------|------|
| `backend/tests/benchmark/runner.py` | correct_rejection_rate 分母、total_relevant 去重、NDCG 标准 log2 |
| `backend/tests/benchmark/schemas.py` | RetrievalResult 增加 expect_rejection 字段 |
| `backend/tests/golden_qa_loader.py` | heading_path_contains 大小写归一化 |
