"""Offline classify enterprise observed vs diagnose gap (no retrieval).

Produces gap buckets for docs/tasks memo. Eval-side only.

S0 (2026-07-23): cohit uses jieba + stopwords (not greedy CJK runs).
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import jieba

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures"
DIAG = ROOT.parent / "docs" / "tasks" / "enterprise_a2_rerank_off.json"
OUT = ROOT.parent / "docs" / "tasks" / "_obs14_gap_out.txt"
SEM_SAMPLE = ROOT.parent / "docs" / "tasks" / "_obs14_semantic_sample.txt"

sys.path.insert(0, str(ROOT))

from app.services.ingestion.chunker import structure_chunk  # noqa: E402
from app.services.ingestion.parser import parse_md  # noqa: E402
from app.services.ingestion.types import IngestionConfig  # noqa: E402

# ASCII / number tokens (kept; CJK goes through jieba)
_ASCII = re.compile(r"[A-Za-z][A-Za-z0-9_\-]{1,}|\d+(?:\.\d+)?")
_CJK_CHAR = re.compile(r"[\u4e00-\u9fff]")

# Question / function words that inflate SEMANTIC false positives when
# co-occurrence is required (aligned with route_extract._STOP + particles).
_STOP = frozenset(
    {
        "什么",
        "多少",
        "怎么",
        "如何",
        "是否",
        "哪些",
        "有没有",
        "请问",
        "帮忙",
        "一下",
        "那个",
        "这个",
        "一个",
        "可以",
        "需要",
        "应该",
        "如果",
        "还是",
        "或者",
        "以及",
        "同时",
        "因为",
        "所以",
        "为什么",
        "怎样",
        "哪里",
        "谁的",
        "多少钱",
        "几天",
        "多久",
        "哪些人",
        "哪种",
        "哪类",
        "吗",
        "呢",
        "啊",
        "吧",
        "的",
        "了",
        "着",
        "过",
        "是",
        "在",
        "有",
        "和",
        "与",
        "及",
        "等",
        "就",
        "都",
        "也",
        "很",
        "更",
        "最",
        "请",
        "告诉",
        "说明",
        "介绍",
        "关于",
        "针对",
        "对于",
        "根据",
        "按照",
        "the",
        "and",
        "for",
        "with",
        "what",
        "how",
        "are",
        "is",
        "a",
        "an",
        "of",
        "to",
        "in",
        "on",
    }
)


def norm(s: str) -> str:
    return re.sub(r"\s+", "", (s or "").lower()).replace("**", "")


def tokens(s: str) -> set[str]:
    """Contentful tokens for query↔child co-occurrence (S0).

    - jieba word cut for CJK (len≥2 after stop filter)
    - ASCII/digits via regex
    - drops question/function stopwords
    """
    text = s or ""
    out: set[str] = set()
    for m in _ASCII.findall(text):
        t = m.lower()
        if t not in _STOP and len(t) >= 1:
            out.add(t)
    for w in jieba.lcut(text):
        w = w.strip().lower()
        if not w or w in _STOP:
            continue
        if _ASCII.fullmatch(w):
            continue
        if _CJK_CHAR.search(w):
            if len(w) < 2:
                continue
            out.add(w)
    return out


def needle_in_source(cc: str, raw_l: str, blob: str) -> str:
    if not cc:
        return "EMPTY"
    if cc.lower() in raw_l:
        return "EXACT"
    if norm(cc) in blob:
        return "WS_NORM"
    return "ABSENT_SOURCE"


def main() -> None:
    qa = json.loads((FIX / "enterprise_qa.json").read_text(encoding="utf-8"))
    diag = json.loads(DIAG.read_text(encoding="utf-8"))
    diag_by = {r["case_id"]: r for r in diag["rows"]}

    docs = {p.name: p.read_text(encoding="utf-8") for p in sorted(FIX.glob("acme_*.md"))}
    raw_l = "\n".join(docs.values()).lower()
    blob = norm("\n".join(docs.values()))

    cfg = IngestionConfig()
    child_blobs: list[str] = []
    for text in docs.values():
        drafts = structure_chunk(parse_md(text), cfg)
        for d in drafts:
            if getattr(d, "chunk_kind", "text") == "parent":
                continue
            content = (d.content or "").strip()
            if content:
                child_blobs.append(content)

    child_l = [c.lower() for c in child_blobs]
    child_n = [norm(c) for c in child_blobs]

    non = [c for c in qa["cases"] if not c.get("expect_rejection")]
    counts: Counter[str] = Counter()
    by_bucket: dict[str, list[str]] = defaultdict(list)
    cross: Counter[tuple[str, str]] = Counter()
    semantic_rows: list[dict[str, str]] = []
    len200 = 0
    preview_drift = 0

    for c in non:
        cid = c["case_id"]
        expect = c.get("expect") or {}
        cc = expect.get("content_contains") or ""
        st = expect.get("section_title") or ""
        hp = expect.get("heading_path_contains") or ""
        q = c.get("query") or ""

        if len(cc) == 200:
            len200 += 1

        src = needle_in_source(cc, raw_l, blob)
        in_child = bool(cc) and any(cc.lower() in b for b in child_l)
        in_child_ws = bool(cc) and any(norm(cc) in b for b in child_n)

        qtok = tokens(q)
        cohit = False
        cohit_toks: set[str] = set()
        if cc and qtok:
            cc_l = cc.lower()
            for raw_child in child_blobs:
                cl = raw_child.lower()
                if cc_l in cl or norm(cc) in norm(raw_child):
                    inter = qtok & tokens(raw_child)
                    if inter:
                        cohit = True
                        cohit_toks = inter
                        break

        diag_row = diag_by.get(cid) or {}
        diag_b = diag_row.get("bucket", "?")
        prev = (diag_row.get("needle_preview") or "").strip()
        rebuilt = cc[:80].replace("\n", " ")
        drifted = bool(prev) and prev != rebuilt and not rebuilt.startswith(prev[: min(12, len(prev))])
        if drifted:
            preview_drift += 1

        if not cc:
            label = "LABEL_EMPTY"
        elif src == "ABSENT_SOURCE":
            label = "LABEL_ABSENT_SOURCE"
        elif not in_child and in_child_ws:
            label = "NEEDLE_WS_MISMATCH"
        elif not in_child and not in_child_ws:
            label = "CHUNK_CONTENT_MISS"
        elif st or hp:
            label = "EXTRA_FIELD_GATE"
        elif not cohit:
            label = "LABEL_SEMANTIC_SUSPECT"
        else:
            label = "CONTENT_MATCHABLE"

        flavor = "len200" if len(cc) == 200 else ("lt200" if len(cc) < 200 else "gt200")
        drift_tag = "drift" if drifted else "ok"
        qtok_s = ",".join(sorted(qtok)[:12])
        co_s = ",".join(sorted(cohit_toks)[:8])
        counts[label] += 1
        by_bucket[label].append(
            f"{cid}|{diag_b}|{flavor}|src={src}|{drift_tag}|cohit={int(cohit)}"
            f"|qtok=[{qtok_s}]|co=[{co_s}]"
        )
        cross[(diag_b, label)] += 1
        if label == "LABEL_SEMANTIC_SUSPECT":
            semantic_rows.append(
                {
                    "case_id": cid,
                    "diag": diag_b,
                    "query": q.replace("\n", " ").strip(),
                    "needle": cc.replace("\n", " ").strip()[:160],
                    "qtok": qtok_s,
                }
            )

    n = len(non)
    lines: list[str] = []
    lines.append(f"non_rejection={n}")
    lines.append(f"child_chunks={len(child_blobs)}")
    lines.append(f"len_eq_200={len200} ({len200/n:.1%})")
    lines.append(f"diagnose_preview_vs_fixture_drift≈{preview_drift}")
    lines.append("--- gap buckets (run_benchmark content-only lens; S0 jieba cohit) ---")
    for k, v in counts.most_common():
        lines.append(f"{k}\t{v}\t{v/n:.1%}")

    ub = (
        counts["CONTENT_MATCHABLE"]
        + counts["LABEL_SEMANTIC_SUSPECT"]
        + counts["EXTRA_FIELD_GATE"]
    )
    lines.append(f"\ncorpus_content_eligible≈{ub}/{n}={ub/n:.1%} (needle in ≥1 child; may still miss Top-3)")
    lines.append(
        f"strict_matchable_with_query_cohit={counts['CONTENT_MATCHABLE']}/{n}"
        f"={counts['CONTENT_MATCHABLE']/n:.1%}"
    )
    lines.append(
        "observed_run_benchmark_hit_at_k=53/90=58.9% (M1-B ObsRefresh; not re-run this window)"
    )

    lines.append("\n--- cross: diagnose_bucket × gap_label ---")
    for (db, lab), v in sorted(cross.items(), key=lambda x: (-x[1], x[0])):
        lines.append(f"{db}\t{lab}\t{v}")

    lines.append("\n--- samples per gap label (up to 10) ---")
    for lab, items in by_bucket.items():
        lines.append(f"[{lab}] n={len(items)}")
        for s in items[:10]:
            lines.append(f"  {s}")

    text = "\n".join(lines) + "\n"
    OUT.write_text(text, encoding="utf-8")
    print(text)

    # Full SEMANTIC dump for S0 human sample (≥10)
    sem_lines = [
        f"LABEL_SEMANTIC_SUSPECT n={len(semantic_rows)} "
        f"(after S0 jieba+stop cohit)",
        "",
    ]
    for i, row in enumerate(semantic_rows, 1):
        sem_lines.append(f"--- {i}. {row['case_id']} diag={row['diag']} ---")
        sem_lines.append(f"Q: {row['query']}")
        sem_lines.append(f"needle: {row['needle']}")
        sem_lines.append(f"qtok: [{row['qtok']}]")
        sem_lines.append("")
    SEM_SAMPLE.write_text("\n".join(sem_lines), encoding="utf-8")
    print(f"wrote semantic sample → {SEM_SAMPLE} ({len(semantic_rows)} rows)")


if __name__ == "__main__":
    main()
