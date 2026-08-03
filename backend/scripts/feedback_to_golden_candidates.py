"""👎 反馈 → golden 候选汇聚（物尽其用 Phase 1a）。

按问句去重计数，只输出 ≥ --min-thumbs-down 条的候选。
**绝不**写入 golden_qa.json（需要人工审题后手动合并）。

用法（容器内）::
    export PYTHONPATH=/app
    python scripts/feedback_to_golden_candidates.py
    python scripts/feedback_to_golden_candidates.py --min-thumbs-down 3 --since 30 --out golden_candidates.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def _parse_since(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        days = int(raw)
        from datetime import timedelta
        return datetime.utcnow() - timedelta(days=days)
    except ValueError:
        pass
    text = raw.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is not None:
        dt = dt.replace(tzinfo=None)
    return dt


async def _run(
    *,
    out: Path | None,
    min_thumbs_down: int,
    since: datetime | None,
    limit: int,
) -> int:
    from app.core.database import SessionLocal
    from app.services.rag.feedback_export import list_thumbs_down_candidates

    async with SessionLocal() as db:
        candidates = await list_thumbs_down_candidates(
            db, since=since, limit=limit,
        )

    # 按 query 聚合（忽略 None query）
    groups: dict[str, dict] = {}
    for c in candidates:
        q = (c.query or "").strip()
        if not q:
            continue
        key = q.lower()
        if key not in groups:
            groups[key] = {
                "query": q,
                "answer": c.answer,
                "kb_name": c.kb_name,
                "count": 0,
                "sample_feedback": [],
            }
        groups[key]["count"] += 1
        if len(groups[key]["sample_feedback"]) < 3:
            groups[key]["sample_feedback"].append(c.feedback_text or "")

    # 筛选超过阈值的
    qualified = [g for g in groups.values() if g["count"] >= min_thumbs_down]
    qualified.sort(key=lambda g: -g["count"])

    # 构造 golden 候选
    golden_candidates = []
    for i, g in enumerate(qualified):
        golden_candidates.append({
            "case_id": f"FB-{(i + 1):04d}",
            "query": g["query"],
            "domain": "feedback",
            "difficulty": 0.5,
            "question_type": "feedback",
            "tags": ["feedback"],
            "source": "md",
            "expect": {
                "content_contains": _extract_needle(g["answer"]),
            },
            "_meta": {
                "thumbs_down_count": g["count"],
                "kb_name": g["kb_name"],
                "sample_feedback": g["sample_feedback"],
            },
        })

    payload = {
        "version": "1.0",
        "kind": "feedback_golden_candidates",
        "description": (
            f"Candidates from {sum(g['count'] for g in groups.values())} thumbs-down "
            f"({len(qualified)} with ≥{min_thumbs_down} votes) — "
            "NOT golden_qa. Fill `expect.content_contains` before merge."
        ),
        "note": "Human must review and fill expect fields before merging into golden_qa.json.",
        "total_feedback": len(candidates),
        "unique_queries": len(groups),
        "qualified_count": len(qualified),
        "min_thumbs_down": min_thumbs_down,
        "candidates": golden_candidates,
    }

    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    # 打印摘要
    print(f"反馈总数: {len(candidates)}")
    print(f"唯一问句: {len(groups)}")
    print(f"合格候选: {len(qualified)} (≥{min_thumbs_down} 个 👎)")
    print(f"输出文件: {out or '(仅打印)'}")
    print()
    for g in qualified[:10]:
        print(f"  [{g['count']}👎] {g['query'][:70]}")
        if g["sample_feedback"][0]:
            print(f"        反馈: {g['sample_feedback'][0][:60]}")
    if len(qualified) > 10:
        print(f"  … +{len(qualified) - 10} more")
    return 0


def _extract_needle(answer: str, max_len: int = 120) -> str:
    """从 assistant 回答中提取一段可作为 content_contains 期望的文本。"""
    # 去掉 citation 标记 [1][2] 和空行
    import re
    cleaned = re.sub(r"\[\d+\]", "", answer)
    cleaned = cleaned.strip()
    # 取前 max_len 字符的完整句子
    if len(cleaned) <= max_len:
        return cleaned
    # 在 max_len 附近找句号
    truncated = cleaned[:max_len]
    last_period = truncated.rfind("。")
    if last_period > max_len // 2:
        return cleaned[: last_period + 1]
    return truncated


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Aggregate thumbs-down feedback into golden candidates"
    )
    parser.add_argument(
        "--out", type=Path, default=None,
        help="Output JSON path",
    )
    parser.add_argument(
        "--min-thumbs-down", type=int, default=3,
        help="Minimum thumbs-down count to qualify (default: 3)",
    )
    parser.add_argument(
        "--since", type=str, default="30",
        help="Lookback: number of days or ISO date (default: 30)",
    )
    parser.add_argument(
        "--limit", type=int, default=2000,
        help="Max feedback rows to scan (default: 2000)",
    )
    args = parser.parse_args()
    raise SystemExit(
        asyncio.run(
            _run(
                out=args.out,
                min_thumbs_down=args.min_thumbs_down,
                since=_parse_since(args.since),
                limit=args.limit,
            )
        )
    )


if __name__ == "__main__":
    main()
