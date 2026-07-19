"""ReportGenerator：评测报告生成器（JSON + Markdown + HTML）。"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from tests.benchmark.schemas import DatasetReport


class ReportGenerator:
    """评测报告生成器。

    输出：
    - report.json      # 原始数据
    - report.md        # Markdown 摘要
    - report.html      # 可视化仪表盘
    """

    def __init__(self, output_dir: str | Path = "benchmark_results") -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._reports: list[DatasetReport] = []

    def add_report(self, report: DatasetReport) -> None:
        self._reports.append(report)

    def add_reports(self, reports: list[DatasetReport]) -> None:
        self._reports.extend(reports)

    @property
    def timestamp(self) -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # —— JSON ——

    def to_json(self, filename: str = "report.json") -> Path:
        """输出原始 JSON 报告。"""
        data = {
            "generated_at": self.timestamp,
            "datasets": [asdict(r) for r in self._reports],
        }
        path = self.output_dir / filename
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str))
        return path

    # —— Markdown ——

    def to_markdown(self, filename: str = "report.md") -> Path:
        """输出 Markdown 摘要报告。"""
        lines = [
            f"# 睿阁 RAG 评测报告",
            f"生成时间: {self.timestamp}",
            "",
            "---",
            "",
        ]

        for r in self._reports:
            lines.extend(self._dataset_md(r))

        path = self.output_dir / filename
        path.write_text("\n".join(lines), encoding="utf-8")
        return path

    @staticmethod
    def _dataset_md(r: DatasetReport) -> list[str]:
        lines = [
            f"## {r.dataset_name}",
            f"- 总查询: {r.total_queries}",
            f"- 跳过: {r.skipped}",
            f"- 延迟: P50={r.p50_latency_ms:.0f}ms / P95={r.p95_latency_ms:.0f}ms / P99={r.p99_latency_ms:.0f}ms",
            f"- 吞吐: {r.throughput_qps:.1f} qps",
            "",
        ]

        if r.retrieval:
            ret = r.retrieval
            lines.extend([
                "### 检索质量",
                f"| 指标 | 得分 |",
                f"|------|------|",
                f"| Hit@1 | {ret.hit_at_1:.1%} |",
                f"| Hit@3 | {ret.hit_at_3:.1%} |",
                f"| Hit@5 | {ret.hit_at_5:.1%} |",
                f"| Precision@K | {ret.precision_at_k:.4f} |",
                f"| Recall@K | {ret.recall_at_k:.4f} |",
                f"| MAP | {ret.map_score:.4f} |",
                f"| MRR | {ret.mean_reciprocal_rank:.4f} |",
                f"| NDCG@k | {ret.mean_ndcg_at_k:.4f} |",
                f"| 拒答正确率 | {ret.correct_rejection_rate:.1%} |",
                "",
            ])
            # domain breakdown
            if r.breakdown_domain:
                lines.append("#### 按 Domain 下钻")
                lines.append("| Domain | 题数 | Hit@3 | MRR | Precision@K |")
                lines.append("|--------|------|-------|-----|------------|")
                for dom, m in sorted(r.breakdown_domain.items()):
                    lines.append(f"| {dom} | {m.total} | {m.hit_at_3:.1%} | {m.mean_reciprocal_rank:.3f} | {m.precision_at_k:.3f} |")
                lines.append("")

        if r.generation:
            gen = r.generation
            lines.extend([
                "### 生成质量",
                f"| 指标 | 得分 |",
                f"|------|------|",
                f"| 正确性 | {gen.correctness:.1%} |",
                f"| 忠实度 | {gen.faithfulness:.1%} |",
                f"| 幻觉率 | {gen.hallucination_rate:.1%} |",
                f"| 引用准确率 | {gen.citation_accuracy:.1%} |",
                f"| 拒答准确率 | {gen.rejection_accuracy:.1%} |",
                "",
            ])

        lines.append("---\n")
        return lines

    # —— HTML ——

    def to_html(self, filename: str = "report.html") -> Path:
        """输出可视化 HTML 仪表盘。"""
        datasets_json = json.dumps(
            [asdict(r) for r in self._reports],
            ensure_ascii=False,
            default=str,
        )

        # 手动替换避免与 JS 模板字面量 ${...} 冲突
        html = HTML_TEMPLATE.replace("__TIMESTAMP__", self.timestamp).replace(
            "__DATASETS_JSON__", datasets_json
        )
        path = self.output_dir / filename
        path.write_text(html, encoding="utf-8")
        return path

    # —— 批量导出 ——

    def export_all(self, prefix: str = "benchmark") -> dict[str, Path]:
        """导出所有格式的报告。返回 {格式: 路径} 字典。"""
        return {
            "json": self.to_json(f"{prefix}.json"),
            "md": self.to_markdown(f"{prefix}.md"),
            "html": self.to_html(f"{prefix}.html"),
        }


# 模块级常量：HTML 模板（使用占位符 __TIMESTAMP__ 和 __DATASETS_JSON__）
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>睿阁 RAG 评测仪表盘</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
<style>
  body { font-family: 'Segoe UI', system-ui, sans-serif; max-width: 1200px; margin: 0 auto; padding: 2rem; background: #f8f5f0; color: #3d3229; }
  h1 { font-family: 'Noto Serif SC', serif; color: #8b6b4a; border-bottom: 2px solid #d4c5b2; padding-bottom: 0.5rem; }
  h2 { color: #6b5340; margin-top: 2rem; }
  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(500px, 1fr)); gap: 1.5rem; }
  .card { background: white; border-radius: 8px; padding: 1.5rem; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }
  .card h3 { margin-top: 0; color: #8b6b4a; }
  table { width: 100%; border-collapse: collapse; }
  th, td { padding: 0.5rem 0.75rem; text-align: left; border-bottom: 1px solid #e8e0d6; }
  th { font-weight: 600; color: #6b5340; }
  .metric-high { color: #2d7d46; font-weight: 600; }
  .metric-mid { color: #b8860b; }
  .metric-low { color: #b22222; }
  .chart-container { width: 100%; max-width: 500px; margin: 0 auto; }
  .footer { margin-top: 2rem; color: #999; font-size: 0.85rem; text-align: center; }
</style>
</head>
<body>
<h1>&#x1F4CA; 睿阁 RAG 评测仪表盘</h1>
<p>生成时间: __TIMESTAMP__</p>

<div id="summary"></div>
<div class="grid" id="dataset-cards"></div>
<div class="footer">
  <p>睿阁 RAG Benchmark · 自动生成</p>
</div>

<script>
const datasets = __DATASETS_JSON__;

// 汇总
const summary = document.getElementById('summary');
let totalQ = datasets.reduce((s, d) => s + d.total_queries, 0);
let avgHit3 = 0;
let countRet = 0;
datasets.forEach(d => { if (d.retrieval) { avgHit3 += d.retrieval.hit_at_3; countRet++; } });
avgHit3 = countRet > 0 ? (avgHit3 / countRet * 100).toFixed(1) : 'N/A';
summary.innerHTML = `
  <div style="display:flex;gap:2rem;flex-wrap:wrap;margin:1rem 0;">
    <div style="background:white;padding:1rem 2rem;border-radius:8px;box-shadow:0 1px 3px rgba(0,0,0,0.08);">
      <div style="font-size:2rem;font-weight:700;color:#8b6b4a;">${totalQ}</div>
      <div style="color:#999;">总查询数</div>
    </div>
    <div style="background:white;padding:1rem 2rem;border-radius:8px;box-shadow:0 1px 3px rgba(0,0,0,0.08);">
      <div style="font-size:2rem;font-weight:700;color:#8b6b4a;">${avgHit3}%</div>
      <div style="color:#999;">平均 Hit@3</div>
    </div>
    <div style="background:white;padding:1rem 2rem;border-radius:8px;box-shadow:0 1px 3px rgba(0,0,0,0.08);">
      <div style="font-size:2rem;font-weight:700;color:#8b6b4a;">${datasets.length}</div>
      <div style="color:#999;">数据集数</div>
    </div>
  </div>
`;

// 每数据集卡片
const container = document.getElementById('dataset-cards');
datasets.forEach((d, idx) => {
  const card = document.createElement('div');
  card.className = 'card';
  let content = '<h3>' + d.dataset_name + '</h3><p>总查询: ' + d.total_queries + ' | 跳过: ' + d.skipped + '</p>';

  if (d.retrieval) {
    const r = d.retrieval;
    function cls(v) { return v > 0.7 ? 'metric-high' : v > 0.4 ? 'metric-mid' : 'metric-low'; }
    content += '<table><tr><th>指标</th><th>得分</th></tr>'
      + '<tr><td>Hit@1</td><td class="' + cls(r.hit_at_1) + '">' + (r.hit_at_1*100).toFixed(1) + '%</td></tr>'
      + '<tr><td>Hit@3</td><td class="' + cls(r.hit_at_3) + '">' + (r.hit_at_3*100).toFixed(1) + '%</td></tr>'
      + '<tr><td>MRR</td><td>' + r.mean_reciprocal_rank.toFixed(4) + '</td></tr>'
      + '<tr><td>延迟 P50</td><td>' + d.p50_latency_ms.toFixed(0) + 'ms</td></tr>'
      + '</table>';
  }

  if (d.generation) {
    const g = d.generation;
    content += '<table><tr><th>指标</th><th>得分</th></tr>'
      + '<tr><td>正确性</td><td>' + (g.correctness*100).toFixed(1) + '%</td></tr>'
      + '<tr><td>引用准确率</td><td>' + (g.citation_accuracy*100).toFixed(1) + '%</td></tr>'
      + '</table>';
  }

  content += '<p>延迟: P50=' + d.p50_latency_ms.toFixed(0) + 'ms / P95=' + d.p95_latency_ms.toFixed(0) + 'ms / P99=' + d.p99_latency_ms.toFixed(0) + 'ms</p>';
  card.innerHTML = content;
  container.appendChild(card);
});

// 雷达图（数据充足时）
const hasRetrieval = datasets.filter(d => d.retrieval).length >= 3;
if (hasRetrieval) {
  const radarDiv = document.createElement('div');
  radarDiv.className = 'card';
  radarDiv.innerHTML = '<h3>检索质量雷达图</h3><div class="chart-container"><canvas id="radarChart"></canvas></div>';
  container.parentNode.insertBefore(radarDiv, container.nextSibling);

  const labels = datasets.filter(d => d.retrieval).map(d => d.dataset_name);
  const hit3Data = datasets.filter(d => d.retrieval).map(d => (d.retrieval.hit_at_3 * 100).toFixed(1));
  const mrrData = datasets.filter(d => d.retrieval).map(d => (d.retrieval.mean_reciprocal_rank * 100).toFixed(1));

  new Chart(document.getElementById('radarChart'), {
    type: 'radar',
    data: {
      labels: labels,
      datasets: [{
        label: 'Hit@3 (%)',
        data: hit3Data,
        borderColor: '#8b6b4a',
        backgroundColor: 'rgba(139,107,74,0.1)',
      }, {
        label: 'MRR (x100)',
        data: mrrData,
        borderColor: '#4a7b8b',
        backgroundColor: 'rgba(74,123,139,0.1)',
      }]
    },
    options: {
      responsive: true,
      scales: { r: { beginAtZero: true, max: 100 } }
    }
  });
}
</script>
</body>
</html>"""
