"""BEIR 公开数据集加载器（msmarco / nfcorpus / fiqa）。

数据来源：https://huggingface.co/BeIR
许可：多种（cc-by-sa-4.0, mit 等，每个子集不同）
格式：HuggingFace datasets → 转为 BenchmarkQuery

本地缓存：backend/data/benchmark/beir/<subset>/
  corpus.jsonl    — 检索语料库
  queries.jsonl   — 查询
  qrels/test.tsv  — 相关性判定

每个 BEIR 子集单独注册，命名约定：beir/<subset>。

⚠️ 仅支持 retrieval 模式（不支持 generation），因为 BEIR 是检索评测基准。
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from tests.benchmark.base import BenchmarkDataset
from tests.benchmark.loaders import register
from tests.benchmark.schemas import BenchmarkQuery, DatasetMeta

logger = logging.getLogger(__name__)


# ── BEIR 本地文件格式常量 ──

CORPUS_FILE = "corpus.jsonl"
QUERIES_FILE = "queries.jsonl"
QRELS_FILE = Path("qrels") / "test.tsv"

_REQUIRED_FILES = (CORPUS_FILE, QUERIES_FILE, str(QRELS_FILE))


# ═══════════════════════════════════════════════════════════════
# 抽象基类
# ═══════════════════════════════════════════════════════════════


class BEIRDatasetBase(BenchmarkDataset):
    """BEIR 数据集基类。

    子类只需定义 _SUBSET_NAME 等类常量。
    """

    # —— 子类必须覆盖 ——
    _SUBSET_NAME: str = ""
    _DISPLAY_NAME: str = ""
    _DESCRIPTION: str = ""
    _HOMEPAGE: str = ""
    _LICENSE: str = ""
    _TOTAL_QUESTIONS: int = 0
    _HF_PATH: str = "BeIR"

    def __init__(self) -> None:
        super().__init__()
        self._bm25_cache: tuple[Any, list[str], dict[str, Any]] | None = None

    @property
    def meta(self) -> DatasetMeta:
        return DatasetMeta(
            name=f"beir/{self._SUBSET_NAME}",
            display_name=self._DISPLAY_NAME,
            description=self._DESCRIPTION,
            homepage=self._HOMEPAGE,
            license=self._LICENSE,
            total_questions=self._TOTAL_QUESTIONS,
            supported_modes=("retrieval",),
            domains=(),
        )

    @property
    def _local_dir(self) -> Path:
        return self.DATA_DIR / "beir" / self._SUBSET_NAME

    # ── 数据下载 ──

    async def download_if_needed(self) -> Path:
        """从 HuggingFace Hub 下载数据集到本地缓存。"""
        local_dir = self._local_dir
        local_dir.mkdir(parents=True, exist_ok=True)

        # 检查所有必需文件是否都存在
        all_exist = all((local_dir / f).exists() for f in _REQUIRED_FILES)
        if all_exist:
            logger.info("BEIR/%s 本地已缓存: %s", self._SUBSET_NAME, local_dir)
            return local_dir

        logger.info("正在从 HuggingFace Hub 下载 BEIR/%s ...", self._SUBSET_NAME)
        self._download_from_hf(local_dir)
        logger.info("BEIR/%s 下载完成", self._SUBSET_NAME)
        return local_dir

    def _download_from_hf(self, local_dir: Path) -> None:
        """使用 datasets 库下载并缓存为 JSONL。

        datasets >=4.x 不再支持 trust_remote_code，需要按 config 分别加载。
        """
        from datasets import load_dataset

        hf_path = f"{self._HF_PATH}/{self._SUBSET_NAME}"

        # corpus: 配置名 'corpus'
        try:
            ds_corpus = load_dataset(hf_path, "corpus", split="corpus")
            corpus_path = local_dir / CORPUS_FILE
            with open(corpus_path, "w", encoding="utf-8") as f:
                for item in ds_corpus:
                    f.write(
                        json.dumps(
                            {
                                "_id": item["_id"],
                                "title": item.get("title", ""),
                                "text": item.get("text", ""),
                            },
                            ensure_ascii=False,
                        )
                        + "\n"
                    )
            logger.info("  corpus: %d 条 → %s", len(ds_corpus), corpus_path)
        except Exception as e:
            logger.warning("  corpus 加载失败: %s", e)

        # queries: 配置名 'queries'
        try:
            ds_queries = load_dataset(hf_path, "queries", split="queries")
            queries_path = local_dir / QUERIES_FILE
            with open(queries_path, "w", encoding="utf-8") as f:
                for item in ds_queries:
                    f.write(
                        json.dumps(
                            {"_id": item["_id"], "text": item.get("text", "")},
                            ensure_ascii=False,
                        )
                        + "\n"
                    )
            logger.info("  queries: %d 条 → %s", len(ds_queries), queries_path)
        except Exception as e:
            logger.warning("  queries 加载失败: %s", e)

        # qrels: 来自独立的 {dataset}-qrels HF repo（新版 datasets 已无 qrels split）
        try:
            from huggingface_hub import hf_hub_download
            import shutil

            qrels_dir = local_dir / "qrels"
            qrels_dir.mkdir(parents=True, exist_ok=True)

            # 下载到 HF 缓存，然后复制到本地
            cached = hf_hub_download(
                f"BeIR/{self._SUBSET_NAME}-qrels",
                "test.tsv",
                repo_type="dataset",
            )
            dest = qrels_dir / "test.tsv"
            shutil.copy2(cached, dest)
            with open(dest) as f:
                qrel_count = len(f.readlines())
            logger.info("  qrels: %d 条 test 查询 → %s", qrel_count, dest)
        except Exception as e:
            logger.warning("  qrels 下载失败: %s", e)

    # ── 本地文件加载 ──

    def _load_corpus(self) -> dict[str, dict[str, str]]:
        """加载本地 corpus.jsonl，返回 {doc_id: {text, title}}。"""
        corpus_path = self._local_dir / CORPUS_FILE
        if not corpus_path.exists():
            raise FileNotFoundError(
                f"BEIR/{self._SUBSET_NAME} 未下载。"
                f"请运行: python -c \"from tests.benchmark.loaders import get_loader; "
                f"import asyncio; asyncio.run(get_loader('beir/{self._SUBSET_NAME}').download_if_needed())\""
            )

        corpus: dict[str, dict[str, str]] = {}
        with open(corpus_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                item = json.loads(line)
                doc_id = item["_id"]
                text = item.get("text", "")
                title = item.get("title", "")
                full_text = f"{title}\n{text}" if title else text
                corpus[doc_id] = {"text": full_text, "title": title}
        return corpus

    def _load_queries(self) -> dict[str, str]:
        """加载本地 queries.jsonl，返回 {query_id: query_text}。"""
        queries_path = self._local_dir / QUERIES_FILE
        if not queries_path.exists():
            raise FileNotFoundError(
                f"BEIR/{self._SUBSET_NAME} 的 queries 文件未找到: {queries_path}"
            )

        queries: dict[str, str] = {}
        with open(queries_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                item = json.loads(line)
                queries[item["_id"]] = item.get("text", "")
        return queries

    def _load_qrels(self) -> dict[str, list[str]]:
        """加载 qrels/test.tsv，返回 {query_id: [relevant_doc_ids]}。

        只返回 score > 0 的相关判定。
        """
        qrels_path = self._local_dir / QRELS_FILE
        if not qrels_path.exists():
            logger.warning("qrels 文件未找到: %s，所有文档视为不相关", qrels_path)
            return {}

        qrels: dict[str, list[str]] = {}
        with open(qrels_path, "r", encoding="utf-8") as f:
            next(f, None)  # 跳过表头
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = line.split("\t")
                if len(parts) < 3:
                    continue
                qid, doc_id, score = parts[0], parts[1], int(parts[2])
                if score > 0:
                    qrels.setdefault(qid, []).append(doc_id)
        return qrels

    async def load(self) -> list[BenchmarkQuery]:
        """加载数据集并返回统一 BenchmarkQuery 列表。

        每个 BenchmarkQuery 包含：
        - query: 问题文本
        - answer: 拼接的相关段落文本（RAGAS 评分用）
        - expects: 相关段落 content_contains
        - metadata: BEIR 元信息（qrel_doc_ids, corpus_size 等）
        """
        if self._queries is not None:
            return self._queries

        await self.download_if_needed()

        corpus = self._load_corpus()
        raw_queries = self._load_queries()
        qrels = self._load_qrels()

        queries_list: list[BenchmarkQuery] = []
        for qid, query_text in raw_queries.items():
            relevant_ids = qrels.get(qid, [])
            relevant_texts = [
                corpus[did]["text"]
                for did in relevant_ids
                if did in corpus
            ]

            expects = tuple(
                {"content_contains": rt[:300]}
                for rt in relevant_texts
            )

            queries_list.append(
                BenchmarkQuery(
                    case_id=qid,
                    query=query_text,
                    answer="\n---\n".join(relevant_texts[:5])
                    if relevant_texts
                    else None,
                    expects=expects,
                    metadata={
                        "dataset": f"beir/{self._SUBSET_NAME}",
                        "qrel_doc_ids": relevant_ids,
                        "corpus_size": len(corpus),
                        "total_queries": len(raw_queries),
                    },
                )
            )

        logger.info(
            "BEIR/%s 加载完成: %d queries, %d corpus docs, %d qrels",
            self._SUBSET_NAME,
            len(queries_list),
            len(corpus),
            sum(len(v) for v in qrels.values()),
        )
        # 过滤：只保留有 qrels 的查询（无 qrels 无法评估）。
        # 仅当 qrels 非空时才过滤——qrels 文件缺失/为空时保留全部查询
        # （answer=None 表示无相关文档），避免数据集被静默清空（N13 回归）。
        if qrels:
            queries_list = [q for q in queries_list if len(q.expects) > 0]
            logger.info(
                "BEIR/%s 过滤后: %d queries（移除了 %d 条无 qrels 的查询）",
                self._SUBSET_NAME,
                len(queries_list),
                len(raw_queries) - len(queries_list),
            )
        else:
            logger.warning(
                "BEIR/%s qrels 为空/缺失，保留全部 %d 条查询（answer=None，无法评估相关性）",
                self._SUBSET_NAME,
                len(queries_list),
            )
        self._queries = queries_list
        return queries_list

    # ── BM25 检索（缓存索引）──

    def _build_bm25_index(self) -> tuple[Any, list[str], dict[str, Any]]:
        """构建 BM25 索引（缓存，仅首次构建）。"""
        if self._bm25_cache is not None:
            return self._bm25_cache

        from rank_bm25 import BM25Okapi

        corpus = self._load_corpus()
        doc_ids = list(corpus.keys())
        tokenized_corpus = [
            corpus[did]["text"].lower().split()
            for did in doc_ids
        ]

        bm25 = BM25Okapi(tokenized_corpus)
        self._bm25_cache = (bm25, doc_ids, corpus)
        logger.info(
            "BEIR/%s BM25 索引构建完成: %d 文档",
            self._SUBSET_NAME,
            len(doc_ids),
        )
        return self._bm25_cache

    def search(
        self,
        query: str,
        top_k: int = 10,
    ) -> list[dict[str, Any]]:
        """对 BEIR 语料库执行 BM25 检索（索引缓存）。

        返回: [{doc_id, content, score, title}, ...]
        """
        bm25, doc_ids, corpus = self._build_bm25_index()
        tokenized_query = query.lower().split()
        scores = bm25.get_scores(tokenized_query)

        scored = sorted(
            ((i, scores[i]) for i in range(len(scores))),
            key=lambda x: x[1],
            reverse=True,
        )

        results = []
        for i, score in scored[:top_k]:
            did = doc_ids[i]
            results.append({
                "doc_id": did,
                "content": corpus[did]["text"],
                "title": corpus[did]["title"],
                "score": float(score),
            })
        return results


# ═══════════════════════════════════════════════════════════════
# BEIR 子数据集
# ═══════════════════════════════════════════════════════════════


@register("beir/nfcorpus")
class BEIRNFCorpus(BEIRDatasetBase):
    """BEIR/nfcorpus: 金融文档检索基准（小数据集，适合快速验证）。"""

    _SUBSET_NAME = "nfcorpus"
    _DISPLAY_NAME = "BEIR/nfcorpus (Financial Document Retrieval)"
    _DESCRIPTION = (
        "Financial domain retrieval benchmark, 3,633 docs, 323 queries. "
        "Source: NCBI (National Center for Biotechnology Information)."
    )
    _HOMEPAGE = "https://huggingface.co/datasets/BeIR/nfcorpus"
    _LICENSE = "MIT"
    _TOTAL_QUESTIONS = 323


@register("beir/fiqa")
class BEIRFiQA(BEIRDatasetBase):
    """BEIR/fiqa: 金融问答检索基准。"""

    _SUBSET_NAME = "fiqa"
    _DISPLAY_NAME = "BEIR/fiqa (Financial QA Retrieval)"
    _DESCRIPTION = (
        "Financial domain QA retrieval benchmark, 57K docs. "
        "Source: FiQA 2018 challenge."
    )
    _HOMEPAGE = "https://huggingface.co/datasets/BeIR/fiqa"
    _LICENSE = "MIT"
    _TOTAL_QUESTIONS = 648


@register("beir/msmarco")
class BEIRMSMARCO(BEIRDatasetBase):
    """BEIR/msmarco: MS MARCO 段落检索基准（大规模）。"""

    _SUBSET_NAME = "msmarco"
    _DISPLAY_NAME = "BEIR/msmarco (MS MARCO Passage Retrieval)"
    _DESCRIPTION = (
        "MS MARCO passage retrieval benchmark, 8.8M docs, 6.9K dev queries. "
        "From real Bing search logs. Industry-standard retrieval benchmark."
    )
    _HOMEPAGE = "https://huggingface.co/datasets/BeIR/msmarco"
    _LICENSE = "CC-BY-SA-4.0"
    _TOTAL_QUESTIONS = 6900
