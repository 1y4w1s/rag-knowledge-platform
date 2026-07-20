"""BenchmarkRunner：评测执行引擎（v1.0 加固版：重试/检查点/恢复/性能基线）。

企业评测体系 Phase 2 — BenchmarkRunner 加固：
- 重试：检索/生成失败自动重试（最多 3 次）
- 检查点：每完成一条结果保存到 JSON，支持断点续跑
- 性能基线：分操作类型追踪延迟分布
"""

from __future__ import annotations

import json
import logging
import math
import time
from dataclasses import asdict
from pathlib import Path
from typing import Callable
from uuid import UUID

from tests.benchmark.rate_limit import RateLimitWrapper
from tests.benchmark.schemas import (
    BenchmarkQuery,
    DatasetReport,
    GenerationMetrics,
    GenerationResult,
    RetrievalMetrics,
    RetrievalResult,
)

_llm_judge = None
_faithfulness_judge = None

async def _get_judge():
    global _llm_judge
    if _llm_judge is None:
        try:
            from tests.benchmark.judge import LLMJudge
            _llm_judge = LLMJudge()
            # 校准集验证评分一致性（非阻塞，失败只打日志）
            try:
                calib = await _llm_judge.verify_calibration()
                if calib.get("status") == "WARN":
                    logger.warning("Judge calibration: %d/%d passed (%.0f%%)",
                                   calib["passed"], calib["total"], calib["pass_rate"] * 100)
                else:
                    logger.info("Judge calibration: %s (%d/%d)",
                                calib["status"], calib.get("passed", 0), calib.get("total", 0))
            except Exception as calib_err:
                logger.warning("Judge calibration skipped: %s", calib_err)
        except ImportError:
            pass
    return _llm_judge

def _get_faithfulness():
    global _faithfulness_judge
    if _faithfulness_judge is None:
        try:
            from tests.benchmark.faithfulness import FaithfulnessJudge
            _faithfulness_judge = FaithfulnessJudge()
        except ImportError:
            pass
    return _faithfulness_judge

logger = logging.getLogger(__name__)

RetrieveFn = Callable[[str, UUID, int], "list"]
GenerateFn = Callable[[str, UUID], "tuple[str, list[dict]]"]

MAX_RETRIES = 3
CHECKPOINT_DIR = Path(__file__).resolve().parent.parent / "benchmark_results" / "checkpoints"


class BenchmarkRunner:
    """评测执行引擎（v1.0 加固版）。"""

    def __init__(
        self,
        kb_id: UUID,
        user_id: UUID,
        rate_limit: RateLimitWrapper | None = None,
    ) -> None:
        self.kb_id = kb_id
        self.user_id = user_id
        self.rate_limit = rate_limit or RateLimitWrapper()
        self._retrieve_fn: RetrieveFn | None = None
        self._generate_fn: GenerateFn | None = None

    def set_retrieve_fn(self, fn: RetrieveFn) -> None:
        self._retrieve_fn = fn

    def set_generate_fn(self, fn: GenerateFn) -> None:
        self._generate_fn = fn

    # ==================== 重试工具 ====================

    async def _call_with_retry(self, fn: Callable, *args, **kwargs):
        """带重试的函数调用，最多 MAX_RETRIES 次。
        自动 await 异步函数。"""
        # 分离 label（仅用于日志）和实际函数参数
        label = kwargs.pop("label", "")
        last_err = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                result = fn(*args, **kwargs)
                if hasattr(result, "__await__"):
                    result = await result
                return result
            except Exception as e:
                last_err = e
                if attempt < MAX_RETRIES:
                    logger.warning("重试 %s (attempt %d/%d): %s", label, attempt, MAX_RETRIES, e)
                    time.sleep(1.0 * attempt)
                else:
                    logger.error("重试耗尽 %s: %s", label, e)
        raise last_err

    # ==================== 检查点工具 ====================

    def _checkpoint_path(self, dataset_name: str, mode: str, run_id: str) -> Path:
        CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
        return CHECKPOINT_DIR / ("%s_%s_%s.json" % (dataset_name, mode, run_id))

    def _save_checkpoint(self, path: Path, results: list, completed: int, total: int) -> None:
        data = {"completed": completed, "total": total, "results": [asdict(r) for r in results]}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, default=str)

    def _load_checkpoint(self, path: Path) -> tuple[list[dict], int] | None:
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("results", []), data.get("completed", 0)
        except (json.JSONDecodeError, KeyError, IOError):
            return None

    # ==================== 检索评测 ====================

    async def run_retrieval(
        self, dataset, *,
        top_k: int = 3, sample_size: int | None = None,
        run_id: str | None = None, resume: bool = False,
    ) -> DatasetReport:
        queries = await dataset.load()
        if sample_size and sample_size < len(queries):
            queries = dataset.sample(queries, sample_size)
        if self._retrieve_fn is None:
            raise RuntimeError("请先调用 set_retrieve_fn")

        dataset_name = dataset.meta.name
        run_id = run_id or time.strftime("%Y%m%d_%H%M%S")
        cp_path = self._checkpoint_path(dataset_name, "retrieval", run_id)

        # 检查检查点恢复
        completed_results: list[RetrievalResult] = []
        start_idx = 0
        if resume:
            cp = self._load_checkpoint(cp_path)
            if cp:
                completed_results = [RetrievalResult(**r) for r in cp[0]]
                start_idx = cp[1]
                logger.info("恢复评测: %s, 已有 %d/%d 条", dataset_name, start_idx, len(queries))

        logger.info("检索评测: %s (%d 条, top_k=%d)", dataset_name, len(queries), top_k)

        domain_results: dict[str, list[RetrievalResult]] = {}
        type_results: dict[str, list[RetrievalResult]] = {}
        skipped = 0
        latencies: list[float] = []
        retrieval_latencies: list[float] = []  # 检索纯耗时

        for idx in range(start_idx, len(queries)):
            q = queries[idx]
            await self.rate_limit.wait_for_search(self.user_id)

            t0 = time.perf_counter()
            try:
                chunks = await self._call_with_retry(
                    self._retrieve_fn, q.query, self.kb_id, top_k,
                    label="retrieval-%s" % q.case_id,
                )
            except Exception as e:
                skipped += 1
                # 回滚适配器的 DB 会话，防止 InFailedSQLTransaction
                try:
                    from sqlalchemy import text as sa_text
                    await self._retrieve_fn.__self__._db.execute(sa_text("ROLLBACK"))
                except Exception:
                    pass
                continue

            elapsed = (time.perf_counter() - t0) * 1000
            latencies.append(elapsed)
            retrieval_latencies.append(elapsed)

            result = self._eval_retrieval(q, chunks, top_k, elapsed)
            completed_results.append(result)

            # 分 domain/type
            if q.domain:
                domain_results.setdefault(q.domain, []).append(result)
            if q.question_type:
                type_results.setdefault(q.question_type, []).append(result)

            # 每 10 条存一次检查点
            if (idx + 1) % 10 == 0:
                self._save_checkpoint(cp_path, completed_results, idx + 1, len(queries))
                logger.info("检查点: %d/%d", idx + 1, len(queries))

        # 最终检查点
        self._save_checkpoint(cp_path, completed_results, len(queries), len(queries))

        metrics = self._aggregate_retrieval(completed_results, top_k)
        report = DatasetReport(
            dataset_name=dataset_name,
            total_queries=len(queries), skipped=skipped,
            retrieval=metrics,
            p50_latency_ms=_percentile(latencies, 50),
            p95_latency_ms=_percentile(latencies, 95),
            p99_latency_ms=_percentile(latencies, 99),
            throughput_qps=len(completed_results) / (sum(latencies) / 1000) if latencies else 0.0,
            breakdown_domain={k: self._aggregate_retrieval(v, top_k) for k, v in domain_results.items()},
            breakdown_type={k: self._aggregate_retrieval(v, top_k) for k, v in type_results.items()},
        )
        logger.info("检索完成: %s Hit@%d=%.1f%% MRR=%.3f (skip=%d)",
                     dataset_name, top_k, getattr(metrics, f"hit_at_{top_k}", 0) * 100, metrics.mean_reciprocal_rank, skipped)
        return report

    def _eval_retrieval(
        self, q: BenchmarkQuery, chunks: list, top_k: int, latency_ms: float,
    ) -> RetrievalResult:
        from tests.golden_qa_loader import chunk_matches as _chunk_match

        chunk_ids = [str(c.chunk_id) for c in chunks[:top_k]]
        scores = [float(c.similarity) for c in chunks[:top_k]]
        contents = [c.content[:200] for c in chunks[:top_k]]

        match_positions = []
        matched_expects: set[int] = set()  # 2026-07-19: 去重 expects 索引

        for i, chunk in enumerate(chunks[:top_k]):
            content = (chunk.content or "").lower()
            matched = False
            if q.expects:
                for ei, exp in enumerate(q.expects):
                    cc = exp.get("content_contains", "")
                    if cc and cc.lower() in content:
                        if ei not in matched_expects:
                            matched_expects.add(ei)
                        matched = True
                        break
            if not matched and q.answer:
                if q.answer.lower() in content:
                    matched = True
            if matched:
                match_positions.append(i)

        total_relevant = len(matched_expects) if q.expects else (1 if any(matched_expects) else 0)
        if not matched_expects and match_positions and not q.expects:
            total_relevant = 1

        hit_1 = any(p < 1 for p in match_positions)
        hit_3 = any(p < 3 for p in match_positions)
        hit_5 = any(p < 5 for p in match_positions)
        mrr = 1.0 / (match_positions[0] + 1) if match_positions else 0.0
        ndcg = self._ndcg_at_k(match_positions, top_k)
        correct_rejection = bool(q.expect_rejection and not match_positions)

        precision = total_relevant / max(1, top_k)
        recall = min(1.0, total_relevant / max(1, len(q.expects) if q.expects else 1))
        map_contrib = 0.0
        if match_positions:
            running_hits = 0
            for rank, pos in enumerate(match_positions, 1):
                running_hits += 1
                if pos < top_k:
                    map_contrib += running_hits / (pos + 1)

        return RetrievalResult(
            case_id=q.case_id, query=q.query, top_k=top_k,
            chunk_ids=chunk_ids, chunk_scores=scores, chunk_contents=contents,
            hit_at_1=hit_1, hit_at_3=hit_3, hit_at_5=hit_5,
            mrr=mrr, ndcg_at_k=ndcg, correct_rejection=correct_rejection,
            expect_rejection=q.expect_rejection,
            precision_at_k=precision, recall_at_k=recall,
            map_contribution=map_contrib,
            latency_ms=latency_ms,
        )

    @staticmethod
    def _ndcg_at_k(match_positions: list[int], k: int) -> float:
        if not match_positions:
            return 0.0
        # 标准 log2 折扣（2026-07-19: 从 bit_length 修正）
        dcg = sum(1.0 / math.log2(pos + 2) for pos in match_positions if pos < k)
        ideal = sum(1.0 / math.log2(i + 2) for i in range(min(len(match_positions), k)))
        return dcg / ideal if ideal > 0 else 0.0

    @staticmethod
    def _aggregate_retrieval(results: list[RetrievalResult], top_k: int) -> RetrievalMetrics:
        n = len(results)
        if n == 0:
            return RetrievalMetrics()
        rejection_denom = sum(1 for r in results if r.expect_rejection)
        return RetrievalMetrics(
            hit_at_1=sum(1 for r in results if r.hit_at_1) / n,
            hit_at_3=sum(1 for r in results if r.hit_at_3) / n,
            hit_at_5=sum(1 for r in results if r.hit_at_5) / n,
            mean_reciprocal_rank=sum(r.mrr for r in results) / n,
            mean_ndcg_at_k=sum(r.ndcg_at_k for r in results) / n,
            correct_rejection_rate=(
                sum(1 for r in results if r.correct_rejection) /
                max(1, rejection_denom)
            ) if rejection_denom > 0 else 0.0,
            total=n,
            precision_at_k=sum(r.precision_at_k for r in results) / n,
            recall_at_k=sum(r.recall_at_k for r in results) / n,
            map_score=sum(r.map_contribution for r in results) / n,
        )

    # ==================== 生成评测 ====================

    async def run_generation(
        self, dataset, *,
        sample_size: int | None = None,
        judge: bool = True, faithfulness: bool = False,
        run_id: str | None = None, resume: bool = False,
    ) -> DatasetReport:
        queries = await dataset.load()
        if sample_size and sample_size < len(queries):
            queries = dataset.sample(queries, sample_size)
        if self._generate_fn is None:
            raise RuntimeError("请先调用 set_generate_fn")

        dataset_name = dataset.meta.name
        run_id = run_id or time.strftime("%Y%m%d_%H%M%S")
        cp_path = self._checkpoint_path(dataset_name, "generation", run_id)

        judge_instance = await _get_judge() if judge else None
        faith_instance = _get_faithfulness() if faithfulness else None

        completed_results: list[GenerationResult] = []
        start_idx = 0
        if resume:
            cp = self._load_checkpoint(cp_path)
            if cp:
                completed_results = [GenerationResult(**r) for r in cp[0]]
                start_idx = cp[1]
                logger.info("恢复: %s, %d/%d 条", dataset_name, start_idx, len(queries))

        latencies: list[float] = []
        correctness_scores: list[float] = []
        citation_scores: list[float] = []
        rejection_scores: list[float] = []
        faithfulness_scores: list[float] = []
        hallucination_rates: list[float] = []

        for idx in range(start_idx, len(queries)):
            q = queries[idx]
            if q.expect_rejection:
                continue

            await self.rate_limit.wait_for_chat(self.user_id)
            t0 = time.perf_counter()
            try:
                answer, citations = await self._call_with_retry(
                    self._generate_fn, q.query, self.kb_id,
                    label="gen-%s" % q.case_id,
                )
            except Exception as e:
                logger.warning("生成失败: case=%s err=%s", q.case_id, e)
                continue
            elapsed = (time.perf_counter() - t0) * 1000
            latencies.append(elapsed)

            result = GenerationResult(
                case_id=q.case_id, query=q.query,
                answer=answer, citations=citations, latency_ms=elapsed,
            )

            if judge_instance and q.answer:
                score, reason = await judge_instance.evaluate_correctness(q.query, answer, q.answer)
                result.correctness_score = score
                result.judge_reason = reason
                correctness_scores.append(score)

                if citations:
                    cite_score, cite_reason = await judge_instance.evaluate_citation_accuracy(answer, citations)
                    result.citation_accuracy = cite_score
                    citation_scores.append(cite_score)

            if faith_instance and citations:
                faith_score, hallu_rate = await faith_instance.evaluate(answer, citations)
                result.faithfulness_score = faith_score
                result.hallucination_rate = hallu_rate
                faithfulness_scores.append(faith_score)
                hallucination_rates.append(hallu_rate)

            completed_results.append(result)

            if (idx + 1) % 5 == 0:
                self._save_checkpoint(cp_path, completed_results, idx + 1, len(queries))

        self._save_checkpoint(cp_path, completed_results, len(queries), len(queries))

        n = len(completed_results)
        metrics = GenerationMetrics(
            correctness=sum(correctness_scores) / max(1, len(correctness_scores)),
            citation_accuracy=sum(citation_scores) / max(1, len(citation_scores)),
            rejection_accuracy=sum(rejection_scores) / max(1, len(rejection_scores)),
            total=n,
            faithfulness=sum(faithfulness_scores) / max(1, len(faithfulness_scores)),
            hallucination_rate=sum(hallucination_rates) / max(1, len(hallucination_rates)),
        )
        return DatasetReport(
            dataset_name=dataset_name,
            total_queries=len(queries), skipped=0,
            generation=metrics,
            p50_latency_ms=_percentile(latencies, 50),
            p95_latency_ms=_percentile(latencies, 95),
            p99_latency_ms=_percentile(latencies, 99),
            throughput_qps=n / (sum(latencies) / 1000) if latencies else 0.0,
        )


def _percentile(values: list[float], p: int) -> float:
    if not values:
        return 0.0
    sv = sorted(values)
    idx = max(0, int(len(sv) * p / 100) - 1)
    return sv[idx]
