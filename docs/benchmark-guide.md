# 睿阁 RAG 评测基准（Benchmark）指南

## 概述

睿阁的 RAG 评测框架提供**检索质量**、**生成质量**、**限流行为**和**性能基线**四个维度的评测能力，覆盖 6 个公开数据集。

## 目录结构

```
backend/tests/benchmark/
├── __init__.py              # 包文档
├── base.py                  # BenchmarkDataset 基类
├── schemas.py               # 统一数据模型
├── rate_limit.py            # RateLimitWrapper（bypass/enforce）
├── runner.py                # BenchmarkRunner 执行引擎
├── report.py                # ReportGenerator（JSON/MD/HTML）
├── judge.py                 # LLM-as-judge 评估器
├── run_retrieval.py         # 检索评测入口
├── run_generation.py        # 生成评测入口
├── loaders/
│   ├── __init__.py          # 加载器注册表
│   ├── crag.py              # CRAG 数据集
│   ├── liverag.py           # LiveRAG 数据集
│   ├── rageval.py           # RAGEval 框架适配
│   ├── ragbench.py          # RAGBench 数据集
│   ├── mirage.py            # MIRAGE 医疗数据集
│   └── enterprise.py        # EnterpriseRAG-Bench
├── adapters/
│   ├── __init__.py
│   ├── retrieval.py         # 检索适配器
│   └── generation.py        # 生成适配器
└── tests/
    └── rate_limit_test.py   # 限流模式验证
```

## 运行方式

### 1. 检索评测

```bash
# 快速模式（mock 嵌入，无需 API Key）
cd backend
python -m tests.benchmark.run_retrieval --datasets crag --mock

# 真实嵌入模式
$env:RAG_REAL_EMBEDDING="1"
python -m tests.benchmark.run_retrieval --datasets crag,liverag --mode bypass

# 全部数据集（抽样 50）
python -m tests.benchmark.run_retrieval --all --sample 50 --output ./benchmark_results
```

### 2. 生成评测

```bash
cd backend
python -m tests.benchmark.run_generation --datasets crag --sample 50
```

需要 DeepSeek API Key。受 chat 限流影响。

### 3. 限流验证

```bash
cd backend

# 生产配置验证
python -m tests.benchmark.tests.rate_limit_test --mode enforce --burst 35

# Bypass 模式验证
python -m tests.benchmark.tests.rate_limit_test --mode bypass --burst 100
```

### 4. 性能压测

```bash
# Locust Benchmark（需后端运行）
locust -f backend/loadtests/locustfile_benchmark.py --host=http://localhost:8000

# 无界面压测
locust -f backend/loadtests/locustfile_benchmark.py --host=http://localhost:8000 --headless -u 5 -r 1 --run-time 5m
```

## 数据集

| 数据集 | 规模 | 下载方式 | 许可 |
|--------|------|----------|------|
| CRAG | 4,409 题 | 自动下载（首次 load 时） | CC BY-NC 4.0 |
| LiveRAG | 895 题 | 手动下载（SIGIR 2025 Challenge） | 比赛许可 |
| RAGEval | 框架 | 手动放置 JSON 文件 | Apache 2.0 |
| RAGBench | 100,000 题 | `datasets` 库自动下载 | 待确认 |
| MIRAGE | 7,560 题 | `datasets` 库自动下载 | NIH |
| EnterpriseRAG-Bench | 500 题 | 手动放置 JSON | 待确认 |

### 首次使用准备

**CRAG** 会自动下载（约 200MB bz2）。
**RAGBench** 和 **MIRAGE** 需安装 `datasets`：

```bash
pip install datasets
python -c "
from datasets import load_dataset
ds = load_dataset('rungalileo/ragbench', split='train')
ds.to_json('backend/data/benchmark/ragbench/ragbench.jsonl')
"
```

## 限流模式

| 模式 | 环境变量 | Chat | Upload | Search |
|------|---------|------|--------|--------|
| bypass | `RAG_RATE_LIMIT_MODE=bypass` | 10,000/h | 10,000/h | 10,000/h |
| enforce | `RAG_RATE_LIMIT_MODE=enforce` | 30/h | 20/h | 60/h |

## 报告输出

评测完成后在 `benchmark_results/` 目录生成：

- `benchmark.json` — 原始数据
- `benchmark.md` — Markdown 摘要
- `benchmark.html` — 可视化仪表盘（Chart.js 雷达图）

## CI

在 GitHub Actions 中手动触发（workflow_dispatch）：
`.github/workflows/benchmark.yml`

每周日凌晨自动运行精选子集。

## 扩展新数据集

1. 在 `loaders/` 下创建 `<名称>.py`
2. 继承 `BenchmarkDataset`，实现 `meta` 和 `load()`
3. 用 `@register("<名称>")` 装饰器注册
4. 在 `loaders/__init__.py` 中导入触发注册

标准实现约 80-120 行。
