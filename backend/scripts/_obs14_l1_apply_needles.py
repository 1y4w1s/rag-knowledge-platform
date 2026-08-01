"""Obs-14-L1: apply human-reviewed short needles to enterprise_qa.json.

Does NOT touch services/rag|ingestion. Verifies each needle ∈ source & child.
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

# case_id -> (content_contains, optional source_docs list or None to keep)
# Short needles aligned to true source sentences (manual review 2026-07-23).
FIXES: dict[str, tuple[str, list[str] | None]] = {
    # --- LABEL_ABSENT_SOURCE (contract / FAQ) ---
    "ENT-015": (
        "本合同项下服务的初始期限为 **12** 个月，自 **2024年6月1日** 起至 **2025年5月31日** 止。",
        None,
    ),
    "ENT-016": ("本保密条款的有效期为自本合同生效之日起 **3** 年。", None),
    "ENT-018": (
        "本合同项下服务包的总价为人民币 **¥480,000.00** 元（大写：人民币肆拾捌万元整）。",
        None,
    ),
    "ENT-019": (
        "协商不成的，任何一方均有权将争议提交 **北京仲裁委员会**，按照申请仲裁时该会现行有效的仲裁规则进行仲裁。",
        None,
    ),
    "ENT-020": (
        "服务期限届满前 **60** 日，如双方均未提出书面不续约通知，本合同将自动续约，每次续约期限为 **12** 个月。",
        None,
    ),
    "ENT-021": (
        "每逾期一日，应按逾期未付金额的 **千分之三（0.3%）** 向乙方支付违约金。",
        None,
    ),
    "ENT-022": (
        "乙方技术支持团队对甲方提交的工单或电话请求的响应时间承诺如下：",
        None,
    ),
    "ENT-023": (
        "若乙方提供的服务连续 **2** 个月或累计 **3** 个月未能达到附录A中约定的SLA标准",
        None,
    ),
    "ENT-024": (
        "本合同终止后，乙方应在 **15** 个工作日内向甲方提供完整的数据备份，并协助甲方完成数据迁移。",
        None,
    ),
    "ENT-026": (
        "每逾期一日，应按逾期未付金额的 **千分之三（0.3%）** 向乙方支付违约金。"
        "逾期超过 **30** 日的，乙方有权暂停提供服务，直至甲方付清全部款项及违约金。"
        "逾期超过 **60** 日的",
        None,
    ),
    "ENT-068": ("支持导出为CSV格式，方便财务对账。", None),
    "ENT-075": (
        "登录控制台，进入“计费”→“套餐变更”。升级即时生效，按剩余天数比例补差价",
        None,
    ),
    "ENT-077": (
        "专业版：$29/月（年付$24/月），含100GB存储和1TB月流量。"
        "企业版：$99/月（年付$79/月）",
        None,
    ),
    "ENT-083": (
        "(1) **P1级（紧急故障）**：服务完全不可用或核心功能丧失，对甲方业务造成重大影响。"
        "响应时间：**15** 分钟内。",
        None,
    ),
    "ENT-103": (
        "服务期限届满前 **60** 日，如双方均未提出书面不续约通知，本合同将自动续约，每次续约期限为 **12** 个月。",
        None,
    ),
    # --- LABEL_SEMANTIC_SUSPECT ---
    "ENT-002": (
        "| 项目 | 价格 | 说明 |\n|------|------|------|\n"
        "| **管理节点** | ¥1,200/月/节点 | 最多 3 个管理节点 |",
        None,
    ),
    "ENT-005": (
        "| 项目 | 价格 | 说明 |\n|------|------|------|\n"
        "| **管理节点** | ¥2,000/月/节点 | 最多 7 个管理节点 |",
        None,
    ),
    "ENT-010": (
        "**功能差异**（相比专业版新增）：\n"
        "- 无限制多集群联邦管理\n"
        "- 支持混合云统一纳管（AWS/Azure/阿里云）",
        None,
    ),
    # 年费事实在 FAQ（规格书无年付价）；同步 source_docs
    "ENT-012": (
        "专业版：$29/月（年付$24/月），含100GB存储和1TB月流量。"
        "企业版：$99/月（年付$79/月）",
        ["acme_FAQ合集.md"],
    ),
    "ENT-013": (
        "专业版：$29/月（年付$24/月），含100GB存储和1TB月流量。"
        "企业版：$99/月（年付$79/月）",
        ["acme_FAQ合集.md"],
    ),
    "ENT-034": (
        "| 研发部 | 218 | 44.8% | +18 | AI算法工程师（8人）、后端开发（6人）、嵌入式工程师（4人） |",
        None,
    ),
    "ENT-036": (
        "本季度计划完成 **5个** 关键里程碑，实际完成 **2个**（天枢v2.0、IoT固件3.0）",
        None,
    ),
    "ENT-037": ("本季度总营收达到 **1.87亿元**，同比增长 **18.3%**", None),
    "ENT-039": ("| ARPU（元/月） | 128 | 132 | 115 | -3.0% | +11.3% |", None),
    "ENT-041": ("全职员工每个日历年享有**15个工作日**的带薪年假", None),
    "ENT-042": ("标准工作时间为**上午9:00至下午6:00**，周一至周五", None),
    "ENT-044": ("员工每年享有**10个工作日**的带薪病假", None),
    "ENT-045": ("以下为星辰科技核心部门及团队负责人架构", None),
    "ENT-047": ("**1. 技术研发部**  \n- 部门总监：张伟", None),
    "ENT-049": ("事假须提前2天申请", None),
    "ENT-052": (
        "Do not install unapproved software or applications on company devices",
        None,
    ),
    "ENT-053": ("管理控制台：http://10.10.10.10:8080", None),
    "ENT-055": ("| 日志备份 | 每天 04:00 | 90天 | /backup/logs/ | gzip |", None),
    "ENT-056": ("| 增量备份 | 每天 02:00 | 7天 | /backup/incremental/ | gzip |", None),
    "ENT-059": (
        "| 全量备份 | 每周日 02:00 | 30天 | /backup/full/ | gzip |\n"
        "| 增量备份 | 每天 02:00 | 7天 | /backup/incremental/ | gzip |",
        None,
    ),
    "ENT-080": (
        "免费版仅支持1个管理员和2个成员，无单点登录（SSO）功能；专业版支持5个管理员和50个成员",
        ["acme_FAQ合集.md"],
    ),
    "ENT-081": ("企业版额外支持自定义域名登录和审计日志。", ["acme_FAQ合集.md"]),
    "ENT-085": ("| **销售费用** | 3,120 | 3,050 | 2,680 | +16.4% | +2.3% |", None),
    "ENT-087": (
        "| 自研推理芯片适配计划 | 完成与国产GPU（华为昇腾、寒武纪）的适配 | 40%",
        None,
    ),
    "ENT-105": (
        "| **总运营费用** | **9,000** | **8,520** | **7,570** | **+18.9%** | **+5.6%** |",
        None,
    ),
    "ENT-106": ("| 全量备份 | 每周日 02:00 | 30天 | /backup/full/ | gzip |", None),
}

# Drop extra-field gates that forced EXTRA_FIELD_GATE on otherwise content-only hits
DROP_EXTRA_FIELDS = {"ENT-068"}


def norm(s: str) -> str:
    return re.sub(r"\s+", "", (s or "").lower()).replace("**", "")


def main() -> None:
    qa = json.loads(QA_PATH.read_text(encoding="utf-8"))
    docs = {p.name: p.read_text(encoding="utf-8") for p in sorted(FIX.glob("acme_*.md"))}
    raw = "\n".join(docs.values())
    cfg = IngestionConfig()
    kids: list[str] = []
    for text in docs.values():
        for d in structure_chunk(parse_md(text), cfg):
            if getattr(d, "chunk_kind", "text") == "parent":
                continue
            c = (d.content or "").strip()
            if c:
                kids.append(c)

    by = {c["case_id"]: c for c in qa["cases"]}
    missing = [k for k in FIXES if k not in by]
    if missing:
        raise SystemExit(f"missing cases: {missing}")

    bad: list[str] = []
    for cid, (needle, docs_override) in FIXES.items():
        in_src = needle in raw
        in_child = any(needle in k for k in kids) or any(norm(needle) in norm(k) for k in kids)
        if not in_src or not in_child:
            bad.append(f"{cid} src={in_src} child={in_child} needle={needle[:60]!r}")
            continue
        case = by[cid]
        expect = dict(case.get("expect") or {})
        expect["content_contains"] = needle
        if cid in DROP_EXTRA_FIELDS:
            expect.pop("section_title", None)
            expect.pop("heading_path_contains", None)
        case["expect"] = expect
        if docs_override is not None:
            case["source_docs"] = docs_override

    if bad:
        print("VERIFY FAIL:")
        print("\n".join(bad))
        raise SystemExit(1)

    QA_PATH.write_text(
        json.dumps(qa, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"updated {QA_PATH} cases={len(FIXES)}")


if __name__ == "__main__":
    main()
