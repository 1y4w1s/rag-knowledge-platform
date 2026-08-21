"""G1-W2 · Critic rules 误杀率离线汇总（协议 g1_critic_rules_falsekill_v1）。

只读：读轨迹 JSON（answer + chunks）→ 调 rules critic → 打印 / 写出误杀报告。
**绝不**写 DB / golden_qa.json / 改检索或生产开关默认。

评测开 rules 的方式：本脚本直接调 ``critique_answer_rules``（与
``run_critic`` + ``mode=rules`` + 主开关开 等价），**不**改
``settings.rag_critic_enabled`` 默认。若要对齐入口路径，可传
``--via-run-critic``（进程内临时开开关，进程结束即灭）。

用法（在 backend/）::

    python scripts/g1_critic_falsekill_summary.py --samples path/to/trajectories.json
    python scripts/g1_critic_falsekill_summary.py --samples t.json --out report.json
    python scripts/g1_critic_falsekill_summary.py --samples t.json --via-run-critic

轨迹 JSON 最低字段（每条）::

    sample_id · tier(A|B|C) · answer · chunks[] · human_should_pass? · synthetic?
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PROTOCOL = "g1_critic_rules_falsekill_v1"
TIERS = frozenset({"A", "B", "C"})
ON_FAIL_VALUES = frozenset({"fail_closed", "annotate_only"})


@dataclass(frozen=True)
class TrajectorySample:
    sample_id: str
    tier: str
    answer: str
    chunks: list[dict[str, Any]]
    human_should_pass: bool
    synthetic: bool
    query: str = ""


def _require_tier(raw: Any) -> str:
    if not isinstance(raw, str):
        raise ValueError(f"tier must be str; got {raw!r}")
    tier = raw.strip().upper()
    if tier not in TIERS:
        raise ValueError(f"tier must be one of {sorted(TIERS)}; got {raw!r}")
    return tier


def _default_should_pass(tier: str) -> bool:
    # A 正确放行 / C 合法拒答 → 应放行；B 应拦 → 不应放行
    return tier != "B"


def parse_samples(payload: dict[str, Any] | list[Any]) -> tuple[list[TrajectorySample], str]:
    """解析轨迹；返回 (samples, on_fail)。"""
    on_fail = "fail_closed"
    if isinstance(payload, list):
        items = payload
    elif isinstance(payload, dict):
        raw_on_fail = payload.get("on_fail", "fail_closed")
        if not isinstance(raw_on_fail, str) or raw_on_fail not in ON_FAIL_VALUES:
            raise ValueError(
                f"on_fail must be one of {sorted(ON_FAIL_VALUES)}; got {raw_on_fail!r}"
            )
        on_fail = raw_on_fail
        items = payload.get("samples")
        if items is None:
            raise ValueError("trajectory JSON must be a list or object with samples[]")
    else:
        raise ValueError("trajectory JSON must be list or object")

    if not isinstance(items, list) or not items:
        raise ValueError("samples[] must be a non-empty list")

    out: list[TrajectorySample] = []
    for i, raw in enumerate(items):
        if not isinstance(raw, dict):
            raise ValueError(f"samples[{i}] must be object")
        sid = raw.get("sample_id")
        if sid is None or str(sid).strip() == "":
            raise ValueError(f"samples[{i}].sample_id required")
        tier = _require_tier(raw.get("tier"))
        answer = raw.get("answer")
        if not isinstance(answer, str):
            raise ValueError(f"samples[{i}].answer must be str")
        chunks = raw.get("chunks")
        if not isinstance(chunks, list):
            raise ValueError(f"samples[{i}].chunks must be list")
        if "human_should_pass" in raw:
            human_should_pass = bool(raw["human_should_pass"])
        else:
            human_should_pass = _default_should_pass(tier)
        synthetic = bool(raw.get("synthetic", True))
        query = raw.get("query") if isinstance(raw.get("query"), str) else ""
        out.append(
            TrajectorySample(
                sample_id=str(sid),
                tier=tier,
                answer=answer,
                chunks=chunks,
                human_should_pass=human_should_pass,
                synthetic=synthetic,
                query=query,
            )
        )
    return out, on_fail


def chunks_from_dicts(raw_chunks: list[dict[str, Any]]) -> list[Any]:
    """把轨迹里的 chunk dict 转成 RetrievedChunk（缺 UUID 则合成）。"""
    from app.services.rag.types import RetrievedChunk

    out: list[RetrievedChunk] = []
    for i, c in enumerate(raw_chunks):
        if not isinstance(c, dict):
            raise ValueError(f"chunks[{i}] must be object")
        data = dict(c)
        for key in ("kb_id", "chunk_id", "document_id"):
            if key not in data or data[key] in (None, ""):
                data[key] = str(uuid.uuid4())
        if "doc_name" not in data:
            data["doc_name"] = "doc.md"
        if "content" not in data:
            data["content"] = ""
        if "similarity" not in data:
            data["similarity"] = 0.9
        if "page_number" not in data:
            data["page_number"] = 1
        if "section_title" not in data:
            data["section_title"] = None
        if "heading_path" not in data:
            data["heading_path"] = None
        out.append(RetrievedChunk.from_dict(data))
    return out


def critique_sample_rules(sample: TrajectorySample) -> Any:
    """离线 rules 路径（不碰 settings 开关）。"""
    from app.services.rag.critic import critique_answer_rules

    return critique_answer_rules(sample.answer, chunks_from_dicts(sample.chunks))


async def critique_sample_via_run_critic(sample: TrajectorySample) -> Any:
    """对齐公共入口：临时开 rules 后调 run_critic（调用方负责恢复开关）。"""
    from app.services.rag.critic import run_critic

    return await run_critic(
        sample.answer, chunks_from_dicts(sample.chunks), sample.query or "eval"
    )


def _detail_from_result(sample: TrajectorySample, result: Any) -> dict[str, Any]:
    issue = None
    if result.claims:
        failed = next((c for c in result.claims if not c.ok), None)
        if failed is not None:
            issue = failed.issue
    if issue is None and not result.ok:
        issue = result.rationale

    false_kill = (
        sample.tier == "A"
        and sample.human_should_pass
        and result.ok is False
    )
    miss = sample.tier == "B" and result.ok is True
    refusal_ok = sample.tier == "C" and result.ok is True

    return {
        "sample_id": sample.sample_id,
        "tier": sample.tier,
        "critic.ok": result.ok,
        "critic.label": result.label,
        "issue": issue,
        "human_should_pass": sample.human_should_pass,
        "false_kill": false_kill,
        "miss": miss,
        "refusal_ok": refusal_ok,
        "synthetic": sample.synthetic,
    }


def evaluate_samples_rules(samples: list[TrajectorySample]) -> list[dict[str, Any]]:
    """纯函数：rules 离线回放每条轨迹。"""
    return [_detail_from_result(s, critique_sample_rules(s)) for s in samples]


def compute_falsekill_report(
    details: list[dict[str, Any]],
    *,
    on_fail: str = "fail_closed",
    notes: str = "",
) -> dict[str, Any]:
    """给定明细 → §4.4 报告（纯函数 · 零 I/O）。"""
    if not details:
        raise ValueError("details must be non-empty")

    tier_a = [d for d in details if d["tier"] == "A"]
    tier_b = [d for d in details if d["tier"] == "B"]
    tier_c = [d for d in details if d["tier"] == "C"]

    n_a, n_b, n_c = len(tier_a), len(tier_b), len(tier_c)
    false_kills = sum(1 for d in tier_a if d.get("false_kill"))
    catches = sum(1 for d in tier_b if d.get("critic.ok") is False)
    refusal_oks = sum(1 for d in tier_c if d.get("refusal_ok"))
    synth_a = sum(1 for d in tier_a if d.get("synthetic"))

    false_kill_rate = (false_kills / n_a) if n_a else 0.0
    catch_rate = (catches / n_b) if n_b else 0.0
    refusal_ok_rate = (refusal_oks / n_c) if n_c else 0.0
    synthetic_share_a = (synth_a / n_a) if n_a else 0.0

    return {
        "protocol": PROTOCOL,
        "critic_mode": "rules",
        "on_fail": on_fail,
        "n_tier_a": n_a,
        "n_tier_b": n_b,
        "n_tier_c": n_c,
        "false_kill_rate": round(false_kill_rate, 6),
        "catch_rate": round(catch_rate, 6),
        "refusal_ok_rate": round(refusal_ok_rate, 6),
        "synthetic_share_a": round(synthetic_share_a, 6),
        "notes": notes
        or (
            "offline falsekill observation only — not a CI gate; "
            "do not raise rag_critic_enabled production default"
        ),
        "details": details,
    }


def build_report_from_payload(
    payload: dict[str, Any] | list[Any],
    *,
    notes: str = "",
    via_run_critic: bool = False,
) -> dict[str, Any]:
    samples, on_fail = parse_samples(payload)
    if via_run_critic:
        details = _evaluate_via_run_critic(samples)
    else:
        details = evaluate_samples_rules(samples)
    return compute_falsekill_report(details, on_fail=on_fail, notes=notes)


def _evaluate_via_run_critic(samples: list[TrajectorySample]) -> list[dict[str, Any]]:
    """进程内临时开 critic（不改 config 默认值文件）。"""
    from app.core.config import settings

    prev_enabled = settings.rag_critic_enabled
    prev_mode = settings.rag_critic_mode
    try:
        settings.rag_critic_enabled = True
        settings.rag_critic_mode = "rules"

        async def _run() -> list[dict[str, Any]]:
            out: list[dict[str, Any]] = []
            for s in samples:
                result = await critique_sample_via_run_critic(s)
                out.append(_detail_from_result(s, result))
            return out

        return asyncio.run(_run())
    finally:
        settings.rag_critic_enabled = prev_enabled
        settings.rag_critic_mode = prev_mode


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def build_report_from_path(
    samples_path: Path,
    *,
    notes: str = "",
    via_run_critic: bool = False,
) -> dict[str, Any]:
    payload = _load_json(samples_path)
    return build_report_from_payload(
        payload, notes=notes, via_run_critic=via_run_critic
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="G1-W2 offline critic rules falsekill summary (read-only)"
    )
    parser.add_argument(
        "--samples",
        type=Path,
        required=True,
        help="Trajectory JSON (samples[] or bare list)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Write full report JSON (default: print summary to stdout)",
    )
    parser.add_argument("--notes", type=str, default="", help="Optional notes field")
    parser.add_argument(
        "--via-run-critic",
        action="store_true",
        help="Process-local enable rag_critic + call run_critic (restored after)",
    )
    args = parser.parse_args(argv)

    try:
        report = build_report_from_path(
            args.samples,
            notes=args.notes,
            via_run_critic=args.via_run_critic,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    summary = {
        "protocol": report["protocol"],
        "critic_mode": report["critic_mode"],
        "on_fail": report["on_fail"],
        "n_tier_a": report["n_tier_a"],
        "n_tier_b": report["n_tier_b"],
        "n_tier_c": report["n_tier_c"],
        "false_kill_rate": report["false_kill_rate"],
        "catch_rate": report["catch_rate"],
        "refusal_ok_rate": report["refusal_ok_rate"],
        "synthetic_share_a": report["synthetic_share_a"],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"wrote full report → {args.out}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
