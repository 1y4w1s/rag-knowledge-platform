import { useCallback, useEffect, useState } from "react";
import { AlertBanner } from "@/components/ui/AlertBanner";
import { Button } from "@/components/ui/button";
import { SectionTitle } from "@/components/common/SectionTitle";
import {
  type EvaluationRun,
  type EvaluationTrend,
  fetchLatestEvaluation,
  fetchEvaluationTrends,
  fetchEvaluationRuns,
} from "@/lib/evaluation-api";

type LoadState = "loading" | "error" | "empty" | "ready";

function metricPct(v: number | null | undefined): string {
  if (v == null) return "-";
  return `${(v * 100).toFixed(1)}%`;
}

function metricMs(v: number | null | undefined): string {
  if (v == null) return "-";
  return `${v.toFixed(0)} ms`;
}

function metricVal(v: number | null | undefined, decimals = 4): string {
  if (v == null) return "-";
  return v.toFixed(decimals);
}

function metricClass(v: number | null | undefined, threshold = 0.7): string {
  if (v == null) return "text-muted-foreground";
  return v >= threshold ? "text-green-600" : v >= threshold * 0.8 ? "text-amber-600" : "text-red-600";
}

export function EvaluationsPage() {
  const [state, setState] = useState<LoadState>("loading");
  const [errorMsg, setErrorMsg] = useState("");
  const [latest, setLatest] = useState<EvaluationRun | null>(null);
  const [trends, setTrends] = useState<EvaluationTrend | null>(null);
  const [recentRuns, setRecentRuns] = useState<EvaluationRun[]>([]);
  const [selectedMetric, setSelectedMetric] = useState("hit_at_3");

  const load = useCallback(async () => {
    setState("loading");
    setErrorMsg("");
    try {
      const [l, t, r] = await Promise.all([
        fetchLatestEvaluation(),
        fetchEvaluationTrends("golden_qa", selectedMetric, 30),
        fetchEvaluationRuns("golden_qa", undefined, 10),
      ]);
      setLatest(l);
      setTrends(t);
      setRecentRuns(r);
      setState(l || r.length > 0 ? "ready" : "empty");
    } catch (e: any) {
      setErrorMsg(e?.message || "加载评测数据失败");
      setState("error");
    }
  }, [selectedMetric]);

  useEffect(() => { load(); }, [load]);

  // ── Metric selector ──
  const metrics = [
    { key: "hit_at_3", label: "Hit@3" },
    { key: "hit_at_1", label: "Hit@1" },
    { key: "mrr", label: "MRR" },
    { key: "precision_at_k", label: "Precision@K" },
    { key: "recall_at_k", label: "Recall@K" },
    { key: "correct_rejection_rate", label: "拒答准确率" },
  ];

  return (
    <div className="mx-auto max-w-[1180px] px-7 pb-16 pt-7">
      <SectionTitle
        title="RAG 评测"
        description="Golden QA 检索/生成质量评测与趋势追踪"
      />

      {state === "loading" && (
        <div className="flex items-center justify-center py-16 text-muted-foreground">
          加载评测数据...
        </div>
      )}

      {state === "error" && (
        <AlertBanner variant="error" message={errorMsg} className="mb-6">
          <Button variant="outline" size="sm" onClick={load}>重试</Button>
        </AlertBanner>
      )}

      {state === "empty" && (
        <div className="flex flex-col items-center gap-2 py-16 text-muted-foreground">
          <p>暂无评测数据</p>
          <p className="text-sm">请先运行评测流水线：<code className="text-xs">python -m tests.run_golden_baseline --save</code></p>
        </div>
      )}

      {state === "ready" && (
        <>
          {/* ── Summary cards ── */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
            <SummaryCard label="Hit@3" value={metricPct(latest?.hit_at_3)} cls={metricClass(latest?.hit_at_3)} />
            <SummaryCard label="MRR" value={metricVal(latest?.mrr)} cls={metricClass(latest?.mrr)} />
            <SummaryCard label="P50 延迟" value={metricMs(latest?.p50_latency_ms)} cls="" />
            <SummaryCard label="拒答准确率" value={metricPct(latest?.correct_rejection_rate)} cls={metricClass(latest?.correct_rejection_rate)} />
          </div>

          {/* ── Trend chart ── */}
          <div className="bg-white rounded-lg border p-4 mb-8">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold text-sm text-foreground">指标趋势</h3>
              <select
                className="text-sm border rounded px-2 py-1"
                value={selectedMetric}
                onChange={(e) => setSelectedMetric(e.target.value)}
              >
                {metrics.map((m) => (
                  <option key={m.key} value={m.key}>{m.label}</option>
                ))}
              </select>
            </div>
            {trends && trends.points.length > 0 ? (
              <SimpleTrendChart points={trends.points} average={trends.average} metric={selectedMetric} />
            ) : (
              <p className="text-center text-muted-foreground py-8 text-sm">暂无趋势数据</p>
            )}
          </div>

          {/* ── Domain breakdown ── */}
          {latest?.breakdown_domain && (
            <div className="bg-white rounded-lg border p-4 mb-8">
              <h3 className="font-semibold text-sm text-foreground mb-3">Domain 下钻</h3>
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-muted-foreground">
                    <th className="text-left py-2">Domain</th>
                    <th className="text-right py-2">题数</th>
                    <th className="text-right py-2">Hit@3</th>
                    <th className="text-right py-2">MRR</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(latest.breakdown_domain).map(([dom, vals]: [string, any]) => (
                    <tr key={dom} className="border-b last:border-0">
                      <td className="py-2">{dom}</td>
                      <td className="text-right py-2">{vals.total}</td>
                      <td className={`text-right py-2 ${metricClass(vals.hit_rate)}`}>{metricPct(vals.hit_rate)}</td>
                      <td className="text-right py-2">{vals.avg_latency_ms ? `${vals.avg_latency_ms.toFixed(0)}ms` : "-"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* ── Recent runs ── */}
          <div className="bg-white rounded-lg border p-4">
            <h3 className="font-semibold text-sm text-foreground mb-3">最近评测记录</h3>
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-muted-foreground">
                  <th className="text-left py-2">运行 ID</th>
                  <th className="text-left py-2">时间</th>
                  <th className="text-right py-2">Hit@3</th>
                  <th className="text-right py-2">MRR</th>
                  <th className="text-right py-2">题数</th>
                  <th className="text-left py-2">触发</th>
                </tr>
              </thead>
              <tbody>
                {recentRuns.map((r) => (
                  <tr key={r.run_id} className="border-b last:border-0">
                    <td className="py-2 font-mono text-xs">{r.run_id}</td>
                    <td className="py-2 text-xs">{new Date(r.created_at).toLocaleString("zh-CN")}</td>
                    <td className={`text-right py-2 ${metricClass(r.hit_at_3)}`}>{metricPct(r.hit_at_3)}</td>
                    <td className="text-right py-2">{metricVal(r.mrr)}</td>
                    <td className="text-right py-2">{r.total_queries}</td>
                    <td className="py-2 text-xs">{r.triggered_by || "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}

// ── Sub-components ──

function SummaryCard({ label, value, cls }: { label: string; value: string; cls: string }) {
  return (
    <div className="bg-white rounded-lg border p-4">
      <p className="text-xs text-muted-foreground mb-1">{label}</p>
      <p className={`text-2xl font-semibold ${cls}`}>{value}</p>
    </div>
  );
}

function SimpleTrendChart({ points, average, metric }: { points: { run_id: string; value: number; created_at: string }[]; average: number; metric: string }) {
  const maxV = Math.max(...points.map(p => p.value), 0.01);
  const minV = Math.min(...points.map(p => p.value), 0);
  const range = maxV - minV || 0.01;
  const height = 160;
  const barW = Math.max(4, Math.min(20, (600 - 40) / points.length));

  return (
    <div className="relative">
      <div className="flex items-end gap-[2px] h-[160px]" style={{ minHeight: `${height}px` }}>
        {points.map((p, i) => {
          const h = ((p.value - minV) / range) * (height - 20) + 4;
          return (
            <div key={i} className="relative group flex-1 min-w-[3px]">
              <div
                className="w-full bg-amber-600/70 hover:bg-amber-600 rounded-t transition-colors cursor-pointer"
                style={{ height: `${h}px` }}
                title={`${p.run_id}: ${(p.value * 100).toFixed(1)}%`}
              />
            </div>
          );
        })}
      </div>
      <p className="text-xs text-muted-foreground mt-1">
        平均: {(average * 100).toFixed(1)}% &middot; {points.length} 次运行
      </p>
    </div>
  );
}
