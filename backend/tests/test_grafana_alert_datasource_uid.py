"""T6-DC-9 告警 datasourceUid 接线测试（masterplan 主题 E · T6 审计 DC-9）。

背景：alert-rules.yml 曾硬编码 ``datasourceUid: P1``，而 datasource.yml 未声明
显式 uid（Grafana 自动生成随机 UID）→ 告警查询找不到数据源，规则静默失效。
修复：datasource.yml 显式声明 uid（loki / tempo），告警规则与内部交叉引用
（``tracesToLogs.datasourceUid``）统一引用显式 UID。

本测试为纯静态行级解析（不 import yaml——CI 依赖集无 PyYAML，遵守不新引依赖），
对 provisioning 文件做结构断言：
1. 每个数据源必须声明非空 uid，且符合 Grafana UID 格式（字母/数字/连字符）；
2. 每条告警规则的 datasourceUid 必须解析到已声明的 uid，且指向 Loki（LogQL 查询）；
3. datasource.yml 内部 jsonData 的 datasourceUid 交叉引用同样可解析。

测试失败 = 告警静默失效（CI 红）。
"""

from __future__ import annotations

import pathlib
import re


BACKEND_ROOT = pathlib.Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
DATASOURCES_YML = REPO_ROOT / "docker" / "grafana" / "datasources" / "datasource.yml"
ALERT_RULES_YML = REPO_ROOT / "docker" / "grafana" / "alerting" / "alert-rules.yml"

# Grafana 数据源 UID 允许字符（官方 strict UID 格式，v12 起默认强制）。
_UID_RE = re.compile(r"^[A-Za-z0-9-]+$")


def _read(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def _parse_datasources(text: str) -> list[dict[str, str]]:
    """解析 datasource.yml 顶层 datasources 序列，仅抽取 name/type/uid。"""
    sources: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for raw in text.splitlines():
        if raw.startswith("  - name:"):
            current = {
                "name": raw.split(":", 1)[1].strip().strip("\"'"),
                "uid": "",
            }
            sources.append(current)
        elif current is not None and raw.startswith("    "):
            m = re.match(r"^    (type|uid):\s*(.+?)\s*$", raw)
            if m:
                current[m.group(1)] = m.group(2).strip().strip("\"'")
    return sources


def _parse_alert_rule_uids(text: str) -> list[tuple[str, str]]:
    """解析 alert-rules.yml 每条规则的 (rule_uid, datasourceUid)。"""
    rules: list[tuple[str, str]] = []
    current_rule: str | None = None
    for raw in text.splitlines():
        if raw.startswith("      - uid:"):
            current_rule = raw.split(":", 1)[1].strip().strip("\"'")
        elif current_rule is not None and raw.startswith("            datasourceUid:"):
            ds_uid = raw.split(":", 1)[1].strip().strip("\"'")
            rules.append((current_rule, ds_uid))
    return rules


def test_datasources_declare_explicit_valid_uids() -> None:
    sources = _parse_datasources(_read(DATASOURCES_YML))
    assert len(sources) >= 2, "应至少声明 Loki 与 Tempo 两个数据源"
    declared = [s["uid"] for s in sources]
    assert all(declared), (
        "每个数据源必须显式声明 uid（否则 Grafana 自动生成，告警引用静默失效）"
    )
    assert len(set(declared)) == len(declared), "数据源 uid 必须唯一"
    assert all(_UID_RE.fullmatch(uid) for uid in declared), (
        "uid 必须符合 Grafana 格式（仅字母/数字/连字符）"
    )


def test_alert_rules_datasource_uid_resolves_to_loki() -> None:
    sources = _parse_datasources(_read(DATASOURCES_YML))
    type_by_uid = {s["uid"]: s["type"] for s in sources}
    loki_uid = next(s["uid"] for s in sources if s["name"] == "Loki")
    rules = _parse_alert_rule_uids(_read(ALERT_RULES_YML))
    assert len(rules) == 3, "睿阁应有 3 条告警规则（5xx / P95 延迟 / ingestion）"
    for rule_uid, ds_uid in rules:
        assert rule_uid, "每条规则必须声明 uid"
        assert ds_uid in type_by_uid, (
            f"规则 {rule_uid} 的 datasourceUid={ds_uid!r} "
            "未解析到 datasource.yml 声明的 uid"
        )
        assert type_by_uid[ds_uid] == "loki", (
            f"规则 {rule_uid} 的 LogQL 查询应指向 Loki 数据源"
            f"（实际 type={type_by_uid[ds_uid]}）"
        )
        assert ds_uid == loki_uid, (
            f"规则 {rule_uid} 的 datasourceUid 应等于 Loki 的显式 uid {loki_uid!r}"
        )


def test_traces_to_logs_cross_reference_resolves() -> None:
    """Tempo jsonData.tracesToLogs.datasourceUid 必须指向已声明 uid（非数据源名）。"""
    text = _read(DATASOURCES_YML)
    declared = {s["uid"] for s in _parse_datasources(text)}
    m = re.search(r"tracesToLogs:\s*\n\s+datasourceUid:\s*([^\s]+)", text)
    assert m, "Tempo 应配置 tracesToLogs 日志关联"
    value = m.group(1).strip().strip("\"'")
    assert value in declared, (
        f"tracesToLogs.datasourceUid={value!r} 未解析到已声明 uid"
    )
