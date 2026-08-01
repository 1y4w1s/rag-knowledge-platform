#!/usr/bin/env python3
"""msmarco BM25 基线评测 v4（双扫描：第一次统计，第二次同时对43查询打分）。"""
import asyncio, json, logging, os, time, math
from pathlib import Path
from collections import Counter
from statistics import median

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("msmarco_eval_v4")


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


async def main():
    backend_dir = Path(__file__).resolve().parent.parent
    data_dir = backend_dir / "data" / "benchmark" / "beir" / "msmarco"

    corpus_path = data_dir / "corpus.jsonl"
    queries_path = data_dir / "queries.jsonl"
    qrels_path = data_dir / "qrels" / "test.tsv"

    for p in [corpus_path, queries_path, qrels_path]:
        if not p.exists():
            logger.error("缺少文件: %s", p)
            return

    logger.info("加载查询...")
    query_items = load_jsonl(queries_path)
    logger.info("  查询: %d 条", len(query_items))

    logger.info("加载 qrels...")
    qrels = load_qrels(qrels_path)
    logger.info("  qrels: %d 条查询有相关性判定", len(qrels))

    valid_queries = [q for q in query_items if q["_id"] in qrels]
    if not valid_queries:
        logger.error("没有可用查询！")
        return
    logger.info("  有 qrels 的查询: %d", len(valid_queries))

    # 预处理所有查询的 terms
    query_terms_list = [list(set(q["text"].lower().split())) for q in valid_queries]
    query_ids = [q["_id"] for q in valid_queries]
    k1, b = 1.5, 0.75
    top_k = 3

    # ── 第一遍扫描：统计 avgdl 和 term df ──
    logger.info("[Pass 1/2] 统计 avgdl 和 term 文档频次...")
    total_docs = 0
    total_terms = 0
    term_df: Counter = Counter()
    doc_id_list: list[str] = []
    doc_len_map: dict[str, int] = {}

    with open(corpus_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            item = json.loads(line)
            did = item["_id"]
            title = item.get("title", "")
            text = item.get("text", "")
            full_text = f"{title}\n{text}" if title else text
            tokens = full_text.lower().split()
            total_docs += 1
            total_terms += len(tokens)
            doc_id_list.append(did)
            doc_len_map[did] = len(tokens)
            for t in set(tokens):
                term_df[t] += 1

    avgdl = total_terms / total_docs if total_docs else 0.0
    logger.info("  文档数: %d, avgdl: %.1f", total_docs, avgdl)

    # 预计算所有查询的 IDF
    query_idf_list: list[dict[str, float]] = []
    for terms in query_terms_list:
        idf_map = {}
        for term in terms:
            df = term_df.get(term, 0)
            if df > 0:
                idf_map[term] = math.log((total_docs - df + 0.5) / (df + 0.5) + 1.0)
        query_idf_list.append(idf_map)

    # ── 第二遍扫描：同时对全部查询打分 ──
    logger.info("[Pass 2/2] 流式打分（同时处理 %d 个查询）...", len(valid_queries))
    # top_scores[q_idx] = [(score, doc_id), ...] 保留 top_k 个
    top_scores: list[list[tuple[float, str]]] = [[] for _ in range(len(valid_queries))]
    doc_idx = 0

    with open(corpus_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            item = json.loads(line)
            did = item["_id"]
            tokens = (item.get("title", "") + " " + item.get("text", "")).lower().split()
            doc_len = len(tokens)
            if doc_len == 0:
                doc_idx += 1
                continue

            # 计算当前文档的 term frequency
            tf_counter: Counter = Counter(tokens)

            # 对每个查询计算 BM25 score
            for q_idx, idf_map in enumerate(query_idf_list):
                score = 0.0
                for term, idf_val in idf_map.items():
                    tf = tf_counter.get(term, 0)
                    if tf > 0:
                        score += idf_val * (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * doc_len / avgdl))
                if score > 0:
                    ts = top_scores[q_idx]
                    ts.append((score, did))
                    if len(ts) > top_k * 2:
                        ts.sort(key=lambda x: x[0], reverse=True)
                        top_scores[q_idx] = ts[:top_k]

            doc_idx += 1
            if doc_idx % 500000 == 0:
                logger.info("  已处理 %d/%d 文档 (%.0f%%)", doc_idx, total_docs, doc_idx / total_docs * 100)

    # 最终排序每查询的 Top-K
    for q_idx in range(len(valid_queries)):
        top_scores[q_idx].sort(key=lambda x: x[0], reverse=True)
        top_scores[q_idx] = top_scores[q_idx][:top_k]

    # ── 计算指标 ──
    hits_at_1 = 0
    hits_at_3 = 0
    reciprocal_ranks: list[float] = []
    ndcg_scores: list[float] = []
    precision_scores: list[float] = []
    recall_scores: list[float] = []
    map_scores: list[float] = []

    for q_idx, q_item in enumerate(valid_queries):
        qid = q_item["_id"]
        relevant = set(qrels.get(qid, []))
        if not relevant:
            continue
        top_ids = [d for _, d in top_scores[q_idx]]

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
        recall_scores.append(sum(1 for d in top_ids if d in relevant) / len(relevant) if relevant else 0.0)
        map_scores.append(average_precision(top_ids, relevant, top_k))

        if (q_idx + 1) % 10 == 0:
            logger.info("  查询 %d/%d 完成", q_idx + 1, len(valid_queries))

    n = len(valid_queries)
    results = {
        "dataset": "beir/msmarco",
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
            "latency_notes": "批量流式处理，单查询延迟不适用",
        },
    }

    print("\n" + "=" * 60)
    print("BEIR/msmarco — BM25 基线评测结果")
    print("=" * 60)
    print(f"    查询数:          {results['total_queries_with_qrels']}")
    print(f"    语料库:          {results['corpus_size']:,} 文档")
    print(f"    Hit@1:           {results['metrics']['Hit@1']}%")
    print(f"    Hit@3:           {results['metrics']['Hit@3']}%")
    print(f"    MRR:             {results['metrics']['MRR']}")
    print(f"    NDCG@k:          {results['metrics']['NDCG@k']}")
    print(f"    Precision@k:     {results['metrics']['Precision@k']}")
    print(f"    Recall@k:        {results['metrics']['Recall@k']}")
    print(f"    MAP:             {results['metrics']['MAP']}")
    print("=" * 60)

    result_path = backend_dir / "benchmark_results" / "msmarco_bm25_result.json"
    result_path.parent.mkdir(parents=True, exist_ok=True)
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    logger.info("结果已保存到 %s", result_path)


if __name__ == "__main__":
    asyncio.run(main())
