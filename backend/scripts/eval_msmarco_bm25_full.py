#!/usr/bin/env python3
"""msmarco BM25 全量评测（倒排索引版）。

与 scripts/eval_msmarco_bm25.py 的指标口径保持一致：
- tokenize: title + text, lower().split()
- BM25 k1=1.5, b=0.75
- idf: log((N - df + 0.5) / (df + 0.5) + 1.0)
- 默认取 Top-3

用法:
  python scripts/eval_msmarco_bm25_full.py --split dev
  python scripts/eval_msmarco_bm25_full.py --split test
"""

import argparse
import json
import logging
import math
import time
from array import array
from heapq import nlargest
from pathlib import Path

try:
    import numpy as np
except ImportError:  # 回退纯 Python 打分（较慢）
    np = None

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("msmarco_eval_full")


def load_jsonl(path: Path) -> list[dict]:
    items: list[dict] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                items.append(json.loads(line))
    return items


def load_qrels(path: Path) -> dict[str, list[str]]:
    qrels: dict[str, list[str]] = {}
    with open(path, "r", encoding="utf-8") as f:
        next(f, None)
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


def ndcg_at_k(ranked: list[str], relevant: set[str], k: int) -> float:
    dcg = 0.0
    for rank in range(min(k, len(ranked))):
        rel = 1.0 if ranked[rank] in relevant else 0.0
        dcg += rel if rank == 0 else rel / (rank + 1)
    idcg = 0.0
    for rank in range(min(k, len(relevant))):
        idcg += 1.0 if rank == 0 else 1.0 / (rank + 1)
    return dcg / idcg if idcg > 0 else 0.0


def average_precision(ranked: list[str], relevant: set[str], k: int) -> float:
    ap = 0.0
    correct = 0
    for rank in range(min(k, len(ranked))):
        if ranked[rank] in relevant:
            correct += 1
            ap += correct / (rank + 1)
    return ap / min(k, len(relevant)) if relevant else 0.0


def score_one_query_python(
    terms: set[str],
    term_df: dict[str, int],
    postings: dict[str, tuple[array, array]],
    doc_len: array,
    total_docs: int,
    avgdl: float,
    k1: float,
    b: float,
    top_k: int,
) -> list[str]:
    idf_map: dict[str, float] = {}
    for t in terms:
        df = term_df.get(t, 0)
        if df > 0:
            idf_map[t] = math.log((total_docs - df + 0.5) / (df + 0.5) + 1.0)
    if not idf_map:
        return []

    score_map: dict[int, float] = {}
    for t, idf_val in idf_map.items():
        doc_ids, tfs = postings[t]
        for i in range(len(doc_ids)):
            did = doc_ids[i]
            tf = tfs[i]
            dl = doc_len[did]
            denom = tf + k1 * (1 - b + b * dl / avgdl)
            score_map[did] = score_map.get(did, 0.0) + idf_val * (tf * (k1 + 1)) / denom
    top_items = nlargest(top_k, score_map.items(), key=lambda kv: kv[1])
    return [str(did) for did, _ in top_items]


def score_one_query_numpy(
    terms: set[str],
    term_df: dict[str, int],
    postings: dict[str, tuple[array, array]],
    doc_len_view: "np.ndarray",
    score_buf: "np.ndarray",
    total_docs: int,
    avgdl: float,
    k1: float,
    b: float,
    top_k: int,
) -> list[str]:
    idf_map: dict[str, float] = {}
    for t in terms:
        df = term_df.get(t, 0)
        if df > 0:
            idf_map[t] = math.log((total_docs - df + 0.5) / (df + 0.5) + 1.0)
    if not idf_map:
        return []

    score_buf.fill(0.0)
    for t, idf_val in idf_map.items():
        doc_ids, tfs = postings[t]
        docs = np.frombuffer(doc_ids, dtype=np.uint32)
        tfs_np = np.frombuffer(tfs, dtype=np.uint16)
        dls = doc_len_view[docs]
        denom = tfs_np + k1 * (1 - b + b * dls / avgdl)
        term_score = idf_val * (tfs_np * (k1 + 1)) / denom
        score_buf += np.bincount(docs, weights=term_score, minlength=total_docs)

    cand = np.flatnonzero(score_buf > 0.0)
    if cand.size == 0:
        return []
    if cand.size <= top_k:
        order = np.argsort(-score_buf[cand])
        top_idx = cand[order]
    else:
        part = np.argpartition(-score_buf[cand], top_k - 1)[:top_k]
        part = part[np.argsort(-score_buf[cand][part])]
        top_idx = cand[part]
    return [str(int(i)) for i in top_idx]


def main() -> None:
    parser = argparse.ArgumentParser(description="msmarco BM25 全量评测（倒排索引版）")
    parser.add_argument("--split", choices=["test", "dev"], default="dev", help="qrels split，默认 dev（6,980 查询）")
    parser.add_argument("--top-k", type=int, default=3, help="Top-K 截断（默认 3）")
    args = parser.parse_args()

    split = args.split
    top_k = args.top_k
    backend_dir = Path(__file__).resolve().parent.parent
    data_dir = backend_dir / "data" / "benchmark" / "beir" / "msmarco"

    corpus_path = data_dir / "corpus.jsonl"
    queries_path = data_dir / "queries.jsonl"
    qrels_path = data_dir / "qrels" / f"{split}.tsv"

    for p in [corpus_path, queries_path, qrels_path]:
        if not p.exists():
            logger.error("缺少文件: %s", p)
            return

    logger.info("加载查询...")
    query_items = load_jsonl(queries_path)
    logger.info("  查询文件: %d 行", len(query_items))

    logger.info("加载 qrels (%s)...", split)
    qrels = load_qrels(qrels_path)
    logger.info("  有相关性判定的查询: %d", len(qrels))

    valid_queries = [q for q in query_items if q["_id"] in qrels]
    if not valid_queries:
        logger.error("没有可用查询")
        return
    logger.info("  匹配 qrels 的查询: %d", len(valid_queries))

    query_terms_list: list[set[str]] = []
    query_terms_set: set[str] = set()
    for q in valid_queries:
        terms = set(q["text"].lower().split())
        query_terms_list.append(terms)
        query_terms_set.update(terms)
    logger.info("  查询词去重后: %d", len(query_terms_set))

    k1, b = 1.5, 0.75
    total_docs = 0
    total_terms = 0
    doc_len = array("I")
    postings: dict[str, tuple[array, array]] = {}
    term_df: dict[str, int] = {}

    logger.info("扫描语料并构建查询词倒排索引...")
    t_scan_start = time.time()
    with open(corpus_path, "r", encoding="utf-8") as f:
        for doc_idx, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            item = json.loads(line)
            did_int = int(item["_id"])
            if did_int != doc_idx:
                raise ValueError(f"corpus _id 不连续: 第 {doc_idx} 行是 {item['_id']}")
            title = item.get("title", "")
            text = item.get("text", "")
            full_text = f"{title}\n{text}" if title else text
            tokens = full_text.lower().split()
            total_docs += 1
            total_terms += len(tokens)
            doc_len.append(len(tokens))

            if tokens:
                hit = set(tokens).intersection(query_terms_set)
                if hit:
                    tf_counter: dict[str, int] = {}
                    for t in tokens:
                        if t in hit:
                            tf_counter[t] = tf_counter.get(t, 0) + 1
                    for t in hit:
                        post = postings.get(t)
                        if post is None:
                            post = (array("I"), array("H"))
                            postings[t] = post
                        post[0].append(doc_idx)
                        post[1].append(tf_counter[t])
                        term_df[t] = term_df.get(t, 0) + 1

            if doc_idx % 1000000 == 0 and doc_idx:
                logger.info("  已处理 %d docs (%.0f%%)", doc_idx, doc_idx / 8841823 * 100)

    avgdl = total_terms / total_docs if total_docs else 0.0
    logger.info(
        "  语料: %d docs, avgdl %.1f, 索引词 %d, 耗时 %.1fs",
        total_docs,
        avgdl,
        len(postings),
        time.time() - t_scan_start,
    )

    logger.info("逐查询打分 (Top-%d)%s...", top_k, "" if np is not None else "，纯 Python 回退")
    doc_len_view = np.frombuffer(doc_len, dtype=np.uint32) if np is not None else None
    score_buf = np.zeros(total_docs, dtype=np.float64) if np is not None else None
    hits_at_1 = 0
    hits_at_3 = 0
    reciprocal_ranks: list[float] = []
    ndcg_scores: list[float] = []
    precision_scores: list[float] = []
    recall_scores: list[float] = []
    map_scores: list[float] = []

    t_score_start = time.time()
    for q_idx, q_item in enumerate(valid_queries):
        qid = q_item["_id"]
        relevant = set(qrels[qid])
        terms = query_terms_list[q_idx]

        if np is not None:
            top_ids = score_one_query_numpy(
                terms,
                term_df,
                postings,
                doc_len_view,
                score_buf,
                total_docs,
                avgdl,
                k1,
                b,
                top_k,
            )
        else:
            top_ids = score_one_query_python(
                terms,
                term_df,
                postings,
                doc_len,
                total_docs,
                avgdl,
                k1,
                b,
                top_k,
            )

        if top_ids and top_ids[0] in relevant:
            hits_at_1 += 1
        if any(did in relevant for did in top_ids):
            hits_at_3 += 1

        for rank, did in enumerate(top_ids, 1):
            if did in relevant:
                reciprocal_ranks.append(1.0 / rank)
                break
        else:
            reciprocal_ranks.append(0.0)

        ndcg_scores.append(ndcg_at_k(top_ids, relevant, top_k))
        precision_scores.append(sum(1 for d in top_ids if d in relevant) / top_k)
        recall_scores.append(sum(1 for d in top_ids if d in relevant) / len(relevant))
        map_scores.append(average_precision(top_ids, relevant, top_k))

        if (q_idx + 1) % 500 == 0:
            logger.info("  查询 %d/%d 完成", q_idx + 1, len(valid_queries))

    n = len(valid_queries)
    results = {
        "dataset": "beir/msmarco",
        "split": split,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "corpus_size": total_docs,
        "total_queries_with_qrels": n,
        "metrics": {
            "Hit@1": round(hits_at_1 / n * 100, 1) if n else 0.0,
            "Hit@3": round(hits_at_3 / n * 100, 1) if n else 0.0,
            "MRR": round(sum(reciprocal_ranks) / n, 3) if n else 0.0,
            "NDCG@k": round(sum(ndcg_scores) / n, 3) if n else 0.0,
            "Precision@k": round(sum(precision_scores) / n, 3) if n else 0.0,
            "Recall@k": round(sum(recall_scores) / n, 3) if n else 0.0,
            "MAP": round(sum(map_scores) / n, 3) if n else 0.0,
            "scoring_seconds": round(time.time() - t_score_start, 1),
        },
    }

    print("\n" + "=" * 60)
    print(f"BEIR/msmarco ({split}) - BM25 全量评测结果")
    print("=" * 60)
    print(f"    查询数:          {results['total_queries_with_qrels']}")
    print(f"    语料库:          {results['corpus_size']:,} docs")
    print(f"    Hit@1:           {results['metrics']['Hit@1']}%")
    print(f"    Hit@3:           {results['metrics']['Hit@3']}%")
    print(f"    MRR:             {results['metrics']['MRR']}")
    print(f"    NDCG@k:          {results['metrics']['NDCG@k']}")
    print(f"    Precision@k:     {results['metrics']['Precision@k']}")
    print(f"    Recall@k:        {results['metrics']['Recall@k']}")
    print(f"    MAP:             {results['metrics']['MAP']}")
    print(f"    打分耗时:        {results['metrics']['scoring_seconds']}s")
    print("=" * 60)

    result_path = backend_dir / "benchmark_results" / f"msmarco_bm25_{split}_result.json"
    result_path.parent.mkdir(parents=True, exist_ok=True)
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    logger.info("结果已保存到 %s", result_path)


if __name__ == "__main__":
    main()
