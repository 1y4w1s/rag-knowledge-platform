# 睿阁 RAG 真实基线记录

> 生成: 2026-07-19 · 嵌入: **bge-small-zh-v1.5 (fastembed ONNX CPU, 512-dim, 真实嵌入)**
> 评分: `scripts/run_benchmark.py` 子串匹配（与 README 宣称值用同一评分逻辑）

---

## 检索基线（Hit@3）

| 测试集 | 题数 | 命中 | Hit@3 | 宣称值 | 偏差 |
|--------|------|------|-------|--------|------|
| Golden QA | 90（排除23拒答） | 86 | **95.6%** | 95.6% | ✅ 一致 |
| Expense QA | 101（排除4拒答） | 92 | **91.1%** | ~92% | ✅ 接近 |
| Enterprise QA | 108（全部） | 86 | **79.6%** | 98% | ❌ **-18.4pp** |
| Enterprise QA（修复后）| 108（全部） | 34 | **31.5%** | 79.6% | ❌ 短值/重复值修复后真实水平 |
| CRAG English | 100（全部） | 19 | **19.0%** | 19% | ✅ 一致 |

## 已修复的评分 bug

| Bug | 文件 | 修复内容 |
|-----|------|----------|
| correct_rejection_rate 分母用错 | runner.py:281-284 | 从 `not hit_at_1` → `expect_rejection` 计数 |
| recall_at_k 分母固定为1 | runner.py:243 | `total_relevant` 去重 + 单answer上限 |
| total_relevant 多chunk重复计数 | runner.py:218-233 | `matched_expects` set 去重 |
| NDCG 非标准折扣 | runner.py:266 | `bit_length()` → `math.log2()` |
| heading_path_contains 未归一化 | golden_qa_loader.py:62,118 | 增加 `.lower()` |
| 生成 rejection_accuracy 硬编码0.0 | runner.py:380 | 依赖 rejection_scores 未填充→标记为待实现 |

## 未被修复的体系问题

| 问题 | 说明 |
|------|------|
| 子串匹配过于宽松 | `"10天"` 在任意 chunk 中出现即算命中 |
| 失败 query 静默跳过不降分 | runner.py 的容错机制，benchmark 分数不反映失败 |
| Benchmark 与生产链路脱节 | 无缓存、无改写、无补偿、无滤波 |
| CI 全用 mock 嵌入 | benchmark.yml/regression.yml/ci.yml 全部用哈希伪向量 |
| Enterprise QA content_contains 循环验证 | 从 chunk 提取答案片段→检索同一 chunk 即命中 |
