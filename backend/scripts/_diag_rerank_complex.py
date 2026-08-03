# -*- coding: utf-8 -*-
"""实验 N 诊断扩展：conditional 全局开启的 A/B 量化（实验 O）。

三模式对比（对同一题跑多次生产 retrieve_chunks，top-20 池定位 rank）：
  - off        : RERANK_POLICY=off（生产现状，bge 完全不跑）
  - conditional: RERANK_POLICY=conditional（should_run_rerank 门闩：
                 RRF 过平 rel_gap<0.08 或 两路 Top-3 Jaccard<0.34 才跑 bge）
  - always     : RERANK_POLICY=always（bge 全跑，实验 N 已实锤负排序，作对照）

scope：
  - complex（默认）: 19 题 complex 且非 composite，三路全跑
  - all            : 全量 Enterprise QA 108 题，off vs conditional 两路
                    （--all-modes 时三路：off/conditional/always）

模型：默认 settings.rerank_model（BAAI/bge-reranker-base）；--model 覆盖
      （如 jinaai/jina-reranker-v2-base-multilingual），--cache-dir 复用本地缓存。
输出 JSON 到 --out（默认 /tmp/diag_rerank_conditional.json）+ 控制台汇总。
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

os.environ["RAG_RATE_LIMIT_MODE"] = "bypass"

KB_ID = UUID("3e6d6ba6-d4c1-433c-b544-a583d4fec78f")
HIT_K = 3
POOL_K = 20

_FIXTURES_CANDIDATES = [
    Path("/app/tests/fixtures"),
    Path(__file__).resolve().parent.parent / "tests" / "fixtures",
]
FIXTURES = next((p for p in _FIXTURES_CANDIDATES if p.exists()), _FIXTURES_CANDIDATES[0])


def _norm(s: str) -> str:
    if not s:
        return ""
    return re.sub(r"[\s，。、；：？！—\-–—()（）【】\[\]\"\'“”‘’·|]+", "", s or "").lower()


def _needle_in(needle: str, text: str) -> bool:
    if not needle:
        return False
    return needle in (text or "")


def _case_ok(ck, cc: str, sp: str, hp: str) -> bool:
    body = _norm(ck.parent_content or ck.content or "")
    content = _norm(ck.content or "")
    st = _norm(ck.heading_path or ck.section_title or "")
    if cc and not (_needle_in(cc, body) or _needle_in(cc, content)):
        return False
    if sp and sp not in st:
        return False
    if hp and hp not in st:
        return False
    return True


async def _run_retrieve(db, query: str, top_k: int, mode: str):
    """生产 retrieve_chunks；mode ∈ off | conditional | always。

    off 模式必须同时 settings.rerank_enabled=False：否则 effective_rerank_policy()
    会把 off 桥接成 always（planner.py 桥接逻辑），composite 题 strategy=None
    走 effective_rerank_policy() 而非 effective_rerank_for_strategy，主路径会
    真跑 bge——污染 off 基线（曾观察到 45 次 off rerank）。
    """
    from app.core.config import settings

    orig_policy = settings.rerank_policy
    orig_enabled = settings.rerank_enabled
    orig_model = settings.rerank_model
    orig_cache = settings.bge_rerank_cache_dir
    settings.rerank_policy = mode
    settings.rerank_enabled = mode != "off"  # off 关闭桥接，全路径短路
    if _ARGS.model:
        settings.rerank_model = _ARGS.model
    if _ARGS.cache_dir:
        settings.bge_rerank_cache_dir = _ARGS.cache_dir
    try:
        from app.services.rag.retrieval import retrieve_chunks

        return await retrieve_chunks(db, kb_id=KB_ID, query=query, top_k=top_k)
    finally:
        settings.rerank_policy = orig_policy
        settings.rerank_enabled = orig_enabled
        settings.rerank_model = orig_model
        settings.bge_rerank_cache_dir = orig_cache


# 全局参数（_run_retrieve 内读取；模块级在 argparse 后填充）
_ARGS: argparse.Namespace | None = None


def _set_args(ns: argparse.Namespace) -> None:
    global _ARGS
    _ARGS = ns


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scope", choices=["complex", "all"], default="complex")
    parser.add_argument("--all-modes", action="store_true", help="scope=all 时三路 off/conditional/always")
    parser.add_argument("--model", default="", help="覆盖 settings.rerank_model（如 jinaai/jina-reranker-v2-base-multilingual）")
    parser.add_argument("--cache-dir", default="", help="覆盖 settings.bge_rerank_cache_dir（复用已下载模型）")
    parser.add_argument("--out", default="/tmp/diag_rerank_conditional.json", help="输出 JSON 路径")
    args = parser.parse_args()
    _set_args(args)

    from app.core.config import settings
    from app.services.rag.cache import set_query_cache_enabled

    set_query_cache_enabled(False)

    # ① 变体生成改确定性 mock（隔离 LLM：变量只留 rerank）
    import app.services.rag.generation as generation_mod
    from app.services.rag.multi_query import mock_expand_queries

    async def _mock_expand_async(query, *_a, **_k):
        return mock_expand_queries(query)

    _orig_expand = generation_mod.expand_queries
    generation_mod.expand_queries = _mock_expand_async

    # ② adaptive_top_k 截断会破坏 top_k=20 池的 rank 定位，诊断时改为不截断
    import app.services.rag.retrieval as retrieval_mod

    _orig_adaptive = retrieval_mod._adaptive_top_k
    retrieval_mod._adaptive_top_k = lambda candidates, query: len(candidates)

    # ③ 记录 did_rerank（bge 真跑次数）：按 mode 分桶
    _rerank_calls: list[tuple[str, str]] = []
    _orig_rerank = retrieval_mod.rerank_chunks

    async def _counted_rerank(query, chunks, *, top_k):
        _rerank_calls.append((settings.rerank_policy, query[:60]))
        return await _orig_rerank(query, chunks, top_k=top_k)

    retrieval_mod.rerank_chunks = _counted_rerank

    # ③b 注入限线程的 encoder：onnxruntime 默认用满全部核，推理峰值内存
    #    在宿主内存紧张时触发 OOM（Killed）。threads=4 压低峰值，仅诊断用。
    import app.services.rag.rerank as rerank_mod

    _encoder_holder: dict[tuple[str, str], Any] = {}

    def _threaded_encoder() -> Any:
        key = (settings.rerank_model, settings.bge_rerank_cache_dir)
        if key not in _encoder_holder:
            from fastembed.rerank.cross_encoder import TextCrossEncoder

            kwargs: dict[str, Any] = {
                "model_name": settings.rerank_model,
                "providers": ["CPUExecutionProvider"],
                "lazy_load": True,
                "threads": 4,
            }
            if settings.bge_rerank_cache_dir:
                kwargs["cache_dir"] = settings.bge_rerank_cache_dir
            _encoder_holder[key] = TextCrossEncoder(**kwargs)
        return _encoder_holder[key]

    _orig_get_encoder = rerank_mod._get_bge_encoder
    rerank_mod._get_bge_encoder = _threaded_encoder

    # ④ 确保 bge 可用
    _orig_enabled = settings.rerank_enabled
    settings.rerank_enabled = True
    try:
        await _main_impl(args.scope)
    finally:
        generation_mod.expand_queries = _orig_expand
        retrieval_mod._adaptive_top_k = _orig_adaptive
        retrieval_mod.rerank_chunks = _orig_rerank
        rerank_mod._get_bge_encoder = _orig_get_encoder
        settings.rerank_enabled = _orig_enabled
        by_mode = Counter(m for m, _ in _rerank_calls)
        print(f"\n[diag] 实际调用 rerank_chunks 次数: {len(_rerank_calls)}（bge 真跑）")
        for m in ("off", "conditional", "always"):
            print(f"  {m}: {by_mode.get(m, 0)} 次")
        for m, q in _rerank_calls:
            print(f"  [{m}] rerank: {q}")


async def _main_impl(scope: str) -> None:
    from app.core.database import SessionLocal

    data = json.loads((FIXTURES / "enterprise_qa.json").read_text(encoding="utf-8"))
    cases = data["cases"]

    # 筛 complex 且非 composite（scope=complex），或全量（scope=all）
    if scope == "complex":
        from app.services.rag.planner import is_composite_query, select_strategy

        sel = [
            c
            for c in cases
            if select_strategy(c["query"]).value == "complex" and not is_composite_query(c["query"])
        ]
        modes = ["off", "conditional", "always"]
        print(f"complex 且非 composite: {len(sel)} 题，三路对比: {modes}")
    else:
        sel = cases
        modes = ["off", "conditional", "always"] if _ARGS and _ARGS.all_modes else ["off", "conditional"]
        print(f"全量 Enterprise QA: {len(sel)} 题，对比: {modes}")

    rows = []
    async with SessionLocal() as db:
        for i, case in enumerate(sel, start=1):
            q = case["query"]
            exp = case.get("expect", {})
            cc, sp, hp = _norm(exp.get("content_contains")), _norm(exp.get("section_title")), _norm(exp.get("heading_path_contains"))

            per_mode: dict[str, dict] = {}
            for mode in modes:
                pool = await _run_retrieve(db, q, top_k=POOL_K, mode=mode)
                rank = next(
                    (idx for idx, ck in enumerate(pool, start=1) if _case_ok(ck, cc, sp, hp)),
                    None,
                )
                per_mode[mode] = {"rank": rank, "hit": rank is not None and rank <= HIT_K}

            parts = []
            for m in modes:
                parts.append("%s=%s" % (m, "hit" if per_mode[m]["hit"] else "miss"))
            tag = "  ranks: " + ", ".join(
                "%s=%s" % (m, per_mode[m]["rank"]) for m in modes
            )
            print(
                f"  [{i}/{len(sel)}] {case['case_id']} {case.get('difficulty')} "
                + " ".join(parts) + tag,
                flush=True,
            )

            row = {
                "case_id": case["case_id"],
                "difficulty": case.get("difficulty"),
                "query": q,
                "level": case.get("difficulty"),
                "ranks": {m: per_mode[m]["rank"] for m in modes},
                "hits": {m: per_mode[m]["hit"] for m in modes},
            }
            rows.append(row)

    # ── 汇总：off vs conditional（核心）＋ off vs always（对照）──
    n = len(rows)
    print("\n" + "=" * 70)
    print(f"实验 O 诊断（{scope}）：{n} 题（KB {KB_ID}）")

    def _summarize(mode: str) -> None:
        hits = sum(1 for r in rows if r["hits"].get(mode))
        print(f"  Hit@3 {mode:<12}: {hits}/{n} = {hits/n:.0%}")

    for m in modes:
        _summarize(m)

    if "off" in modes and "conditional" in modes:
        lift = [r for r in rows if not r["hits"]["off"] and r["hits"]["conditional"]]
        hurt = [r for r in rows if r["hits"]["off"] and not r["hits"]["conditional"]]
        both = [r for r in rows if r["hits"]["off"] and r["hits"]["conditional"]]
        print("\n  conditional vs off:")
        print(f"    conditional 救回（off miss & cond hit）: {len(lift)} 题")
        for r in lift:
            print(f"      {r['case_id']} {r['difficulty']} rank_off={r['ranks']['off']} rank_cond={r['ranks']['conditional']} q={r['query'][:50]}")
        print(f"    conditional 负排序（off hit & cond miss）: {len(hurt)} 题")
        for r in hurt:
            print(f"      {r['case_id']} {r['difficulty']} rank_off={r['ranks']['off']} rank_cond={r['ranks']['conditional']} q={r['query'][:50]}")
        print(f"    两边都命中: {len(both)} 题")
        print(f"    净变化: {len(lift) - len(hurt)} 题")

    if "off" in modes and "always" in modes:
        hurt_always = [r for r in rows if r["hits"]["off"] and not r["hits"]["always"]]
        lift_always = [r for r in rows if not r["hits"]["off"] and r["hits"]["always"]]
        print("\n  always vs off（对照，实验 N 已实锤负排序）:")
        print(f"    always 负排序: {len(hurt_always)} 题；救回: {len(lift_always)} 题；净变化: {len(lift_always) - len(hurt_always)} 题")

    if scope == "all":
        # 按难度分层（对齐全量 Enterprise QA 评测口径）
        by_level = {}
        for r in rows:
            lv = r["level"]
            s = by_level.setdefault(lv, {"total": 0})
            s["total"] += 1
            for m in modes:
                s[m] = s.get(m, 0) + (1 if r["hits"].get(m) else 0)
        print("\n  按难度分层（Hit@3 " + " / ".join(modes) + "）:")
        for lv in ["L1", "L2", "L3", "L4"]:
            s = by_level.get(lv, {"total": 0})
            parts = "  |  ".join(
                "{} {}/{} = {:.0%}".format(m, s.get(m, 0), s["total"], s.get(m, 0) / max(1, s["total"]))
                for m in modes
            )
            print(f"    {lv}: {parts}")

    out = {
        "experiment": "O-conditional-vs-off",
        "scope": scope,
        "model": (_ARGS.model if _ARGS and _ARGS.model else "default(bge-reranker-base)"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "kb_id": str(KB_ID),
        "n": n,
        "modes": modes,
        "hits": {m: sum(1 for r in rows if r["hits"].get(m)) for m in modes},
        "lift": [r["case_id"] for r in rows if "off" in modes and "conditional" in modes and not r["hits"]["off"] and r["hits"]["conditional"]],
        "hurt": [r["case_id"] for r in rows if "off" in modes and "conditional" in modes and r["hits"]["off"] and not r["hits"]["conditional"]],
        "rows": rows,
    }
    out_path = Path(_ARGS.out if _ARGS else "/tmp/diag_rerank_conditional.json")
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nwrote: {out_path}")


if __name__ == "__main__":
    asyncio.run(main())
