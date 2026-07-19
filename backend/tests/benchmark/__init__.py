"""睿阁 RAG 评测基准（Benchmark）框架。

本模块独立于现有 pytest 测试，提供统一的评测框架：
- BenchmarkDataset 基类 + 6 个数据集加载器
- SearchEvaluator / GenerationEvaluator
- RateLimitWrapper（bypass / enforce 双模式）
- BenchmarkRunner + ReportGenerator

结构：
  benchmark/
    __init__.py      # 包初始化
    base.py          # BenchmarkDataset 基类，统一数据模型
    schemas.py       # BenchmarkQuery / BenchmarkResult 数据模型
    rate_limit.py    # RateLimitWrapper（bypass/enforce）
    loaders/
      __init__.py    # 加载器注册表
      crag.py        # CRAG 数据集加载器
      liverag.py     # LiveRAG 数据集加载器
      rageval.py     # RAGEval 数据集加载器
      ragbench.py    # RAGBench 数据集加载器
      mirage.py      # MIRAGE 数据集加载器
      enterprise.py  # EnterpriseRAG-Bench 数据集加载器
    runner.py        # BenchmarkRunner
    report.py        # ReportGenerator

使用方式（Phase 2 后）：
  python -m tests.benchmark.runner --datasets crag,liverag --mode bypass
"""
