"""M1-B: apply human-reviewed needles for BM miss ∩ MISS_POOL dirty labels.

Does NOT touch services/rag|ingestion. Verifies each needle ∈ source & child.
Rejection cases: clear expect + expect_rejection=true (corpus has no answer).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures"
QA_PATH = FIX / "enterprise_qa.json"

sys.path.insert(0, str(ROOT))
from app.services.ingestion.chunker import structure_chunk  # noqa: E402
from app.services.ingestion.parser import parse_md  # noqa: E402
from app.services.ingestion.types import IngestionConfig  # noqa: E402

# case_id -> (content_contains, optional source_docs override or None)
FIXES: dict[str, tuple[str, list[str] | None]] = {
    "ENT-004": ("支持裸金属、虚拟机及容器混合部署", None),
    "ENT-014": (
        "免费版仅支持1个管理员和2个成员，无单点登录（SSO）功能；"
        "专业版支持5个管理员和50个成员，提供SSO和API密钥管理。"
        "企业版额外支持自定义域名登录和审计日志。",
        ["acme_FAQ合集.md"],
    ),
    "ENT-043": ("minimum 12 characters", None),
    "ENT-062": (
        "| **管理网络** | 1 Gbps 以上，低延迟 (< 2ms) | TCP 6443 (K8s API), 2379-2380 (etcd), 10250 (kubelet) | 节点间通信 |\n"
        "| **数据网络** | 10 Gbps 以上，建议 25 Gbps | TCP 30000-32767 (NodePort), 80/443 (Ingress) | 应用流量 |",
        ["acme_产品规格书.md"],
    ),
    "ENT-064": ("| 生产环境 | 10.20.30.40 | 2222 | 密钥+密码 |", None),
    "ENT-079": ("以下为 AcmeCloud 企业版 v3.2 的 15 项核心功能", None),
    "ENT-099": (
        "| **管理节点 (Master)** | 4 vCPU / 16 GB RAM / 100 GB SSD |",
        None,
    ),
    "ENT-102": (
        "免费版仅支持1个管理员和2个成员，无单点登录（SSO）功能；"
        "专业版支持5个管理员和50个成员，提供SSO和API密钥管理。"
        "企业版额外支持自定义域名登录和审计日志。",
        ["acme_FAQ合集.md"],
    ),
}

# Corpus has no answering span → rejection (same pattern as ENT-100)
REJECTIONS: tuple[str, ...] = ("ENT-008", "ENT-089")


def norm(s: str) -> str:
    return re.sub(r"\s+", "", (s or "").lower()).replace("**", "")


def main() -> None:
    qa = json.loads(QA_PATH.read_text(encoding="utf-8"))
    by = {c["case_id"]: c for c in qa["cases"]}
    docs = {p.name: p.read_text(encoding="utf-8") for p in sorted(FIX.glob("acme_*.md"))}
    cfg = IngestionConfig()
    kids: list[str] = []
    for text in docs.values():
        for d in structure_chunk(parse_md(text), cfg):
            if getattr(d, "chunk_kind", "text") == "parent":
                continue
            c = (d.content or "").strip()
            if c:
                kids.append(c)

    missing = [cid for cid in list(FIXES) + list(REJECTIONS) if cid not in by]
    if missing:
        raise SystemExit(f"missing cases: {missing}")

    bad: list[str] = []
    for cid, (needle, docs_override) in FIXES.items():
        src_names = docs_override or by[cid].get("source_docs") or list(docs.keys())
        src_blob = "\n".join(docs[n] for n in src_names if n in docs)
        in_src = needle in src_blob
        in_child = any(needle in k for k in kids) or any(
            norm(needle) in norm(k) for k in kids
        )
        exact_child = any(needle in k for k in kids)
        if not in_src or not in_child:
            bad.append(
                f"{cid} src={in_src} child={in_child} exact_child={exact_child} "
                f"needle={needle[:80]!r}"
            )
            continue
        case = by[cid]
        expect = dict(case.get("expect") or {})
        expect["content_contains"] = needle
        expect.pop("section_title", None)
        expect.pop("heading_path_contains", None)
        case["expect"] = expect
        case.pop("expect_rejection", None)
        if docs_override is not None:
            case["source_docs"] = docs_override

    for cid in REJECTIONS:
        case = by[cid]
        case["expect"] = {}
        case["expect_rejection"] = True

    if bad:
        print("VERIFY FAIL:")
        print("\n".join(bad))
        raise SystemExit(1)

    QA_PATH.write_text(
        json.dumps(qa, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"updated {QA_PATH} fixes={len(FIXES)} rejections={len(REJECTIONS)}"
    )


if __name__ == "__main__":
    main()
