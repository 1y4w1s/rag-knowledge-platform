# 睿阁 RAG 评测基准（Benchmark）指南

> 最后更新：2026-07-20 | 对应代码基线：629f336+

## 概述

睿阁的 RAG 评测框架提供 **检索质量** 和 **生成质量** 两个维度的评测能力，覆盖 1 个外部标准集（CRAG）和 3 个自建测试集。

## 当前基线

```
| 测试集 | 类型 | 题数 | Hit@3 | 说明 |
|--------|------|------|-------|------|
| Golden QA | 自建中文员工手册 | 107 | 95.3% | 含 22 拒答题独立报告 |
| Expense QA | 自建中文费用政策 | 106 | 91.5% | 含 4 拒答题 |
| Enterprise QA | 自建中文多文档(6份) | 108 | ~25% | 诚实基线，修复短值/重复后 |
| CRAG English | 外部英文 Wikipedia | 100 | ~26% | bge-small-en-v1.5 |
| Advanced QA | 复杂场景测试 | 20 | 待测 | 跨文档推理/表格/拒答陷阱 |
```

### Golden QA 细节（107 题）

- 源文档：`golden_handbook.md`（一份自建中文员工手册，约 30 个章节）
- Domain 分布：attendance(21)/benefits(6)/career(8)/compensation(9)/cross(3)/finance(15)/performance(9)/security(8)/separation(10)
- 拒答题量：22（独立报告，不计入 Hit@3）

### Expense QA 细节（106 题）

- 源文档：`expense_policy.md`（一份自建中文费用政策文档）
- 拒答题量：4
- 含 1 题冲突测试题（EP-106：市内交通费 50 元 vs 30 元）

### Enterprise QA 细节（108 题）

- 源文档：6 份 AcmeCloud 企业文档（产品规格书/框架合同/员工手册_英文/FAQ合集/季度报告/操作手册）
- 拒答题量：16（数据不足/未言明/无法确定的问题）
- 注意：分数 ~25% 是"诚实基线"，比原始的 98% 大幅下降是因为清除了短值/作弊/答前缀
- content_contains 从实际 chunk 提取（W3 修复）

### CRAG English 细节（100 题子集）

- 源：Comprehensive RAG Benchmark（Facebook Research）
- 文档构建方式：从 Wikipedia snippet 构建单页文档
- 嵌入模型：bge-small-en-v1.5（384 dim），通过 fastembed 加载
- 中文嵌入 fallback：bge-small-en 下载失败时自动回退到 bge-small-zh
- CI 默认 sample=100（避免 2706 题超时）。夜间可使用 --sample 4409

### Advanced QA（20 题）

- 场景题 5 + 表格计算题 5 + 时效性题 5 + 拒答陷阱题 5
- 源文档：golden_handbook.md
- 待基准 Benchmark 验证

## 目录结构

```
backend/tests/benchmark/
├── __init__.py
├── schemas.py               # 统一数据模型（TestCase/RetrievalMetrics 等）
├── rate_limit.py            # RateLimitWrapper（bypass/enforce）
├── runner.py                # BenchmarkRunner 执行引擎（v1.0 加固版）
├── report.py                # ReportGenerator（JSON/MD/HTML）
├── judge.py                 # LLM-as-judge 评估器
├── run_retrieval.py         # 检索评测入口
├── run_generation.py        # 生成评测入口
├── loaders/
│   ├── crag.py              # CRAG 数据集
│   ├── enterprise.py        # EnterpriseRAG-Bench
│   └── ...
├── adapters/
│   ├── retrieval.py         # 检索适配器
│   └── generation.py        # 生成适配器
├── tests/
│   ├── run_crag_benchmark.py
│   └── _run_crag_100.py     # [DEPRECATED] 改用 run_crag.py
├── scorers/                 # W2 统一评分引擎
│   ├── base.py              # EvalScorer Protocol
│   ├── content_match.py     # content_contains 子串匹配
│   ├── answer_match.py      # answer 子串匹配
│   └── exact_match.py       # 精确匹配策略
└── faithfulness.py          # 忠实度/引用准确率评测

backend/tests/fixtures/
├── golden_qa/v1.0/          # 版本化目录
├── expense_qa/v1.0/
├── enterprise_qa/v1.0/
├── advanced_qa.json         # 复杂场景测试
├── judge_calibration.json   # LLM-as-judge 校准集(20题)
├── eval-test-case-schema.json
└── review_signoff_template.md

backend/scripts/
├── run_benchmark.py         # 一键跑所有测试集
├── run_crag.py              # CRAG 评测入口
├── ci_baseline_check.py     # CI 基线对比
├── ci_new_scorer.py         # CI 新旧评分引擎对比
├── cleanup_eval_runs.py     # 90 天清理
└── gen_golden_answers.py    # golden_answer 自动生成
```

## 目录结构

```
backend/tests/benchmark/scorers/    # W2 统一评分引擎
├── base.py                         # EvalScorer Protocol
├── content_match.py                # content_contains 子串匹配
├── answer_match.py                 # answer 子串匹配
└── exact_match.py                  # 精确匹配策略
```

### 评分策略说明

| 策略 | 适用场景 | 原理 |
|------|----------|------|
| ContentMatchScorer | 所有自建测试集 | content_contains 子串匹配 + 可选 section_title/heading_path/page_number 联合校验 |
| AnswerMatchScorer | CRAG | document answer 子串匹配 |
| ExactMatchScorer | 精确数字/代码输出 | 严格字符匹配 |

### 新旧引擎对比（W2c）

89/89 一致。2 例差异来自新引擎正确检查了 page_number 约束（旧引擎漏检）。

## 运行指南

### 本地（Docker 内）

```bash
# 一键跑所有测试集（检索）
docker exec -w /app -e PYTHONPATH=/app ruige-api \
  python scripts/run_benchmark.py --mode retrieval --output text

# 指定测试集
python scripts/run_benchmark.py --dataset golden_qa --mode retrieval --output text
python scripts/run_benchmark.py --dataset enterprise_qa --mode retrieval --output text

# 生成评测（需 DEEPSEEK_API_KEY）
python scripts/run_benchmark.py --dataset golden_qa --mode full --output text
```

### CI（GitHub Actions）

- **ci.yml**: 每次 push 跑 `rag-benchmark` job（Golden QA 109 题，真实嵌入，2% 门禁）
- **benchmark.yml**: 手动触发或夜间 cron（支持指定 datasets 和 sample 数）
- **regression.yml**: 已弃用，功能合并到 ci.yml

## W4 CI 三层门禁

| 层级 | 触发条件 | 内容 |
|------|----------|------|
| Layer 1 | 每次 push | ci.yml test job（pytest 122+） |
| Layer 2 | 每次 push | ci.yml rag-benchmark job（Golden QA，2% 退化门禁） |
| Layer 3 | 手动/夜间 | benchmark.yml（全测试集 + CRAG） |

### Secrets 要求

```
DEEPSEEK_API_KEY   # 生成评测用
RAG_TEST_PASSWORD  # 基准测试注册密码
```

## 相关文档

- [技术文档](TECH.md)
- [测试集质量优化计划](test-quality-plan.md)
- [剩余计划](remaining-plan.md)
