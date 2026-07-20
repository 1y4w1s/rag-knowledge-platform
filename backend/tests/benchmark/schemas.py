"""基准评测统一数据模型（与 retrieve_chunks / GoldenQACase 对齐）。

v1.0 企业评测体系 Phase 2 扩展：
- RetrievalMetrics: 新增 precision_at_k / recall_at_k / map
- GenerationMetrics: 新增 faithfulness / hallucination_rate
- DatasetReport: 新增 breakdown (domain/tag 下钻)
- RetrievalResult: 新增 precision / recall / map_contribution
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Literal


# —— 输入模型 ——

SourceKind = Literal["md", "pdf", "docx", "txt", "html", "json"]


@dataclass(frozen=True)
class BenchmarkQuery:
    """一条评测查询，统一表示各数据集的 QA 条目。"""

    case_id: str
    query: str
    answer: str | None = None
    alt_answers: tuple[str, ...] = ()
    source: SourceKind = "txt"
    domain: str | None = None
    difficulty: float | None = None
    question_type: str | None = None
    expect_rejection: bool = False
    expects: tuple[dict[str, Any], ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


# —— 输出模型 ——


@dataclass
class RetrievalResult:
    """一条查询的检索结果（v1.0 新增 precision/recall/map_contribution）。"""

    case_id: str
    query: str
    top_k: int
    chunk_ids: list[str] = field(default_factory=list)
    chunk_scores: list[float] = field(default_factory=list)
    chunk_contents: list[str] = field(default_factory=list)
    # 指标
    hit_at_1: bool = False
    hit_at_3: bool = False
    hit_at_5: bool = False
    mrr: float = 0.0
    ndcg_at_k: float = 0.0
    correct_rejection: bool = False
    expect_rejection: bool = False  # 2026-07-19: 修正 rejection_rate 分母
    # v1.0 扩展
    precision_at_k: float = 0.0  # 相关 chunks / top_k
    recall_at_k: float = 0.0     # 检索到的相关 chunks / 全部相关 chunks
    map_contribution: float = 0.0  # 单条贡献给 MAP
    # 耗时
    latency_ms: float = 0.0


@dataclass
class GenerationResult:
    """一条查询的生成结果（v1.0 新增 faithfulness/hallucination）。"""

    case_id: str
    query: str
    answer: str
    citations: list[dict[str, Any]] = field(default_factory=list)
    # 正确性
    correctness_score: float = 0.0
    citation_accuracy: float = 0.0
    rejection_correct: bool = False
    judge_reason: str = ""
    # v1.0 扩展
    faithfulness_score: float = 0.0  # 答案忠实度（decompose-and-verify）
    hallucination_rate: float = 0.0  # 幻觉率（无 chunk 支撑的 claims / 总 claims）
    # 耗时
    latency_ms: float = 0.0


@dataclass
class DatasetReport:
    """单个数据集的评测报告（v1.0 新增 breakdown）。"""

    dataset_name: str
    total_queries: int
    skipped: int
    # 检索
    retrieval: RetrievalMetrics | None = None
    # 生成
    generation: GenerationMetrics | None = None
    # 性能
    p50_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0
    throughput_qps: float = 0.0
    # v1.0 扩展：分 domain / type 下钻
    breakdown_domain: dict[str, RetrievalMetrics] = field(default_factory=dict)
    breakdown_type: dict[str, RetrievalMetrics] = field(default_factory=dict)


@dataclass
class RetrievalMetrics:
    """检索质量汇总（v1.0 新增 precision/recall/map）。"""

    hit_at_1: float = 0.0
    hit_at_3: float = 0.0
    hit_at_5: float = 0.0
    mean_reciprocal_rank: float = 0.0
    mean_ndcg_at_k: float = 0.0
    correct_rejection_rate: float = 0.0
    total: int = 0
    # v1.0 扩展
    precision_at_k: float = 0.0   # 全量平均 Precision@K
    recall_at_k: float = 0.0      # 全量平均 Recall@K
    map_score: float = 0.0        # Mean Average Precision


@dataclass
class GenerationMetrics:
    """生成质量汇总（v1.0 新增 faithfulness/hallucination）。"""

    correctness: float = 0.0
    citation_accuracy: float = 0.0
    rejection_accuracy: float = 0.0
    total: int = 0
    # v1.0 扩展
    faithfulness: float = 0.0       # 平均忠实度
    hallucination_rate: float = 0.0  # 平均幻觉率


# —— 数据集元信息 ——


@dataclass(frozen=True)
class DatasetMeta:
    """数据集的元描述。"""

    name: str
    display_name: str
    description: str
    homepage: str
    license: str
    total_questions: int
    supported_modes: tuple[str, ...] = ("retrieval",)
    domains: tuple[str, ...] = ()
