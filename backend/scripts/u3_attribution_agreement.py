"""U3-W1 · 归因机器标签 ↔ 人工桶一致率离线统计（协议 u3_attribution_agreement_v1）。

只读：读导出 JSON（可选）+ 人工明细 → 打印 / 写出 agreement 报告。
**绝不**写 DB / golden_qa.json / 改检索或生产开关。

用法（在 backend/）::

    python scripts/u3_attribution_agreement.py --human path/to/human.json
    python scripts/u3_attribution_agreement.py --export td.json --human human.json --out report.json

人工明细最低字段（每条）::

    feedback_id? · machine_label? · human_label · source(p1|p2|p3) · synthetic?

有 --export 时可省略 machine_label（按 feedback_id 从 attribution.label 回填）。
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Label enum SSOT — 与 feedback_attribution 对齐（复制常量，不 import 业务链路）。
LABELS: frozenset[str] = frozenset(
    {
        "retrieval_miss",
        "generation_bad",
        "refusal_wrong",
        "product_or_acl",
        "doc_gap",
        "unknown",
    }
)
SOURCES: frozenset[str] = frozenset({"p1", "p2", "p3"})
PROTOCOL = "u3_attribution_agreement_v1"


@dataclass(frozen=True)
class AgreementRow:
    feedback_id: str | None
    machine_label: str
    human_label: str
    source: str
    synthetic: bool
    override: bool

    @property
    def agree(self) -> bool:
        return self.machine_label == self.human_label


def _require_label(raw: Any, *, field: str) -> str:
    if not isinstance(raw, str) or raw not in LABELS:
        raise ValueError(f"{field} must be one of {sorted(LABELS)}; got {raw!r}")
    return raw


def _require_source(raw: Any) -> str:
    if not isinstance(raw, str) or raw not in SOURCES:
        raise ValueError(f"source must be one of {sorted(SOURCES)}; got {raw!r}")
    return raw


def load_machine_labels_from_export(payload: dict[str, Any]) -> dict[str, str]:
    """从 thumbs_down 导出 JSON 建 feedback_id → attribution.label 映射。"""
    candidates = payload.get("candidates")
    if not isinstance(candidates, list):
        raise ValueError("export JSON missing candidates[]")
    out: dict[str, str] = {}
    for i, c in enumerate(candidates):
        if not isinstance(c, dict):
            raise ValueError(f"candidates[{i}] must be object")
        fid = c.get("feedback_id")
        attr = c.get("attribution") or {}
        if not isinstance(attr, dict):
            raise ValueError(f"candidates[{i}].attribution must be object")
        label = attr.get("label")
        if fid is None or label is None:
            continue
        out[str(fid)] = _require_label(label, field=f"candidates[{i}].attribution.label")
    return out


def parse_human_items(
    payload: dict[str, Any] | list[Any],
    *,
    machine_by_id: dict[str, str] | None = None,
) -> list[AgreementRow]:
    """解析人工明细；可与导出 machine 标签合并。"""
    if isinstance(payload, list):
        items = payload
    elif isinstance(payload, dict):
        items = payload.get("items")
        if items is None:
            raise ValueError("human JSON must be a list or object with items[]")
    else:
        raise ValueError("human JSON must be list or object")

    if not isinstance(items, list) or not items:
        raise ValueError("human items[] must be a non-empty list")

    machine_by_id = machine_by_id or {}
    rows: list[AgreementRow] = []
    for i, raw in enumerate(items):
        if not isinstance(raw, dict):
            raise ValueError(f"items[{i}] must be object")
        fid_raw = raw.get("feedback_id")
        feedback_id = str(fid_raw) if fid_raw not in (None, "") else None

        machine = raw.get("machine_label")
        if machine is None and feedback_id is not None:
            machine = machine_by_id.get(feedback_id)
        if machine is None:
            raise ValueError(
                f"items[{i}]: machine_label required "
                "(or provide --export joinable by feedback_id)"
            )
        machine_label = _require_label(machine, field=f"items[{i}].machine_label")
        human_label = _require_label(raw.get("human_label"), field=f"items[{i}].human_label")
        source = _require_source(raw.get("source", "p3"))
        synthetic = bool(raw.get("synthetic", source == "p3"))

        if "override" in raw:
            override = bool(raw["override"])
        else:
            override = machine_label != human_label

        rows.append(
            AgreementRow(
                feedback_id=feedback_id,
                machine_label=machine_label,
                human_label=human_label,
                source=source,
                synthetic=synthetic,
                override=override,
            )
        )
    return rows


def _per_label_stats(rows: list[AgreementRow]) -> dict[str, dict[str, float | int]]:
    """per_label: precision / recall / support（support = 人工金标条数）。"""
    human_counts: Counter[str] = Counter(r.human_label for r in rows)
    machine_counts: Counter[str] = Counter(r.machine_label for r in rows)
    tp: Counter[str] = Counter(
        r.human_label for r in rows if r.machine_label == r.human_label
    )
    out: dict[str, dict[str, float | int]] = {}
    for label in sorted(LABELS):
        h = human_counts.get(label, 0)
        m = machine_counts.get(label, 0)
        hit = tp.get(label, 0)
        recall = (hit / h) if h else 0.0
        precision = (hit / m) if m else 0.0
        out[label] = {
            "precision": round(precision, 6),
            "recall": round(recall, 6),
            "support": h,
        }
    return out


def n_tier(n: int, *, p1: int, p2: int) -> str:
    """§4.5 分档解读（非硬门禁）。"""
    if n < 5:
        return "below_protocol_smoke"
    real_share = (p1 + p2) / n if n else 0.0
    if n >= 20 and real_share >= 0.70:
        return "claimable_calibration"
    if n >= 10:
        return "observation_baseline"
    return "protocol_smoke"


def compute_agreement_report(
    rows: list[AgreementRow],
    *,
    notes: str = "",
) -> dict[str, Any]:
    """给定明细行 → §4.4 报告（纯函数 · 零 I/O）。"""
    if not rows:
        raise ValueError("rows must be non-empty")

    n = len(rows)
    agree_n = sum(1 for r in rows if r.agree)
    override_n = sum(1 for r in rows if r.override)
    unknown_n = sum(1 for r in rows if r.machine_label == "unknown")
    sources = Counter(r.source for r in rows)
    p1, p2, p3 = sources.get("p1", 0), sources.get("p2", 0), sources.get("p3", 0)

    details = [
        {
            "feedback_id": r.feedback_id,
            "machine_label": r.machine_label,
            "human_label": r.human_label,
            "source": r.source,
            "agree": r.agree,
            "synthetic": r.synthetic,
            "override": r.override,
        }
        for r in rows
    ]

    return {
        "protocol": PROTOCOL,
        "n": n,
        "sources": {"p1": p1, "p2": p2, "p3": p3},
        "agreement_rate": round(agree_n / n, 6),
        "per_label": _per_label_stats(rows),
        "unknown_rate": round(unknown_n / n, 6),
        "override_rate": round(override_n / n, 6),
        "n_tier": n_tier(n, p1=p1, p2=p2),
        "notes": notes
        or (
            "offline agreement only — not a G1 gate; "
            "do not auto-ingest; synthetic rows marked in details"
        ),
        "details": details,
    }


def _load_json(path: Path) -> Any:
    # utf-8-sig tolerates PowerShell Set-Content BOM
    return json.loads(path.read_text(encoding="utf-8-sig"))


def build_report_from_paths(
    *,
    human_path: Path,
    export_path: Path | None = None,
    notes: str = "",
) -> dict[str, Any]:
    human_payload = _load_json(human_path)
    machine_by_id: dict[str, str] = {}
    if export_path is not None:
        export_payload = _load_json(export_path)
        if not isinstance(export_payload, dict):
            raise ValueError("export JSON must be an object")
        machine_by_id = load_machine_labels_from_export(export_payload)
    rows = parse_human_items(human_payload, machine_by_id=machine_by_id)
    return compute_agreement_report(rows, notes=notes)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="U3-W1 offline attribution↔human agreement (read-only)"
    )
    parser.add_argument(
        "--human",
        type=Path,
        required=True,
        help="Human annotation JSON (items[] or bare list)",
    )
    parser.add_argument(
        "--export",
        type=Path,
        default=None,
        help="Optional thumbs_down export JSON (join machine labels by feedback_id)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Write full report JSON (default: print summary to stdout)",
    )
    parser.add_argument("--notes", type=str, default="", help="Optional notes field")
    args = parser.parse_args(argv)

    try:
        report = build_report_from_paths(
            human_path=args.human,
            export_path=args.export,
            notes=args.notes,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    summary = {
        "protocol": report["protocol"],
        "n": report["n"],
        "sources": report["sources"],
        "agreement_rate": report["agreement_rate"],
        "unknown_rate": report["unknown_rate"],
        "override_rate": report["override_rate"],
        "n_tier": report["n_tier"],
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
