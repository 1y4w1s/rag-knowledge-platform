import { useCallback, useEffect, useState } from "react";
import { AlertBanner } from "@/components/ui/AlertBanner";
import { Button } from "@/components/ui/button";
import {
  type RagasDataset,
  type RagasRunEntry,
  fetchRagasScores,
} from "@/lib/evaluation-api";

type LoadState = "loading" | "error" | "empty" | "ready";

function metricPct(v: number | null | undefined): string {
  if (v == null) return "—";
  return `${(v * 100).toFixed(1)}%`;
}

function metricClass(v: number | null | undefined): string {
  if (v == null) return "text-muted-foreground";
  const threshold = 0.7;
  return v >= threshold
    ? "text-green-600"
    : v >= threshold * 0.8
      ? "text-amber-600"
      : "text-red-600";
}

export function RagasTab() {
  const [state, setState] = useState<LoadState>("loading");
  const [errorMsg, setErrorMsg] = useState("");
  const [datasets, setDatasets] = useState<RagasDataset[]>([]);
  const [selectedDs, setSelectedDs] = useState<string>("");
  const [apiNote, setApiNote] = useState("");

  const load = useCallback(async () => {
    setState("loading");
    setErrorMsg("");
    try {
      const resp = await fetchRagasScores();
      setApiNote(resp.note ?? "");
      if (resp.datasets.length === 0) {
        setState("empty");
        return;
      }
      setDatasets(resp.datasets);
      // 默认选中第一个有 runs 的数据集
      const first = resp.datasets.find((d) => d.runs.length > 0);
      if (first) setSelectedDs(first.name);
      setState("ready");
    } catch (e: any) {
      setErrorMsg(e?.message || "加载 RAGAS 评分失败");
      setState("error");
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  // ── 当前选中的数据集 ──
  const currentDs = datasets.find((d) => d.name === selectedDs);
  const runs = currentDs?.runs ?? [];

  // ── 最近一次运行 ──
  const latest = runs.length > 0 ? runs[0] : null;

  // ── 支持的所有指标 ──
  const hasContext = latest?.context_precision != null || latest?.context_recall != null;
  const metrics: { key: string; label: string }[] = [
    { key: "faithfulness", label: "Faithfulness" },
    { key: "hallucination_rate", label: "Hallucination Rate" },
  ];
  if (hasContext) {
    metrics.push(
      { key: "context_precision", label: "Context Precision" },
      { key: "context_recall", label: "Context Recall" },
    );
  }

  const [selectedMetric, setSelectedMetric] = useState("faithfulness");

  return (
    <section aria-label="RAGAS 评分">
      {/* 数据集选择 */}
      {state === "ready" && datasets.length > 0 && (
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <label className="text-sm text-muted-foreground" htmlFor="ds-select">
              数据集
            </label>
            <select
              id="ds-select"
              className="text-sm border rounded px-2 py-1.5 min-w-[140px]"
              value={selectedDs}
              onChange={(e) => setSelectedDs(e.target.value)}
            >
              {datasets.map((ds) => (
                <option key={ds.name} value={ds.name}>
                  {ds.display_name} ({ds.runs.length} 次)
                </option>
              ))}
            </select>
          </div>
        </div>
      )}

      {/* 加载态 */}
      {state === "loading" && (
        <div className="flex items-center justify-center py-16 text-muted-foreground">
          加载 RAGAS 评分数据...
        </div>
      )}

      {/* 错误态 */}
      {state === "error" && (
        <AlertBanner className="mb-6">
          {errorMsg}
          <Button variant="outline" size="sm" onClick={load}>
            重试
          </Button>
        </AlertBanner>
      )}

      {/* 空态 */}
      {state === "empty" && (
        <div className="flex flex-col items-center gap-2 py-16 text-muted-foreground">
          <p>暂无 RAGAS 评分数据</p>
          <p className="text-sm">
            请先运行 RAGAS 评测：<code className="text-xs">python -m tests.benchmark.run_benchmark --scorer ragas</code>
          </p>
        </div>
      )}

      {/* 就绪态 */}
      {state === "ready" && latest && (
        <>
          {/* ── 提示：Context 指标尚未可用 ── */}
          {apiNote && (
            <div className="mb-6 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
              {apiNote}
            </div>
          )}

          {/* ── 指标卡片 ── */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            {metrics.map((m) => {
              const val = latest[m.key as keyof typeof latest];
              return (
                <div key={m.key} className="bg-white rounded-lg border p-4">
                  <p className="text-xs text-muted-foreground mb-1">{m.label}</p>
                  <p className={`text-2xl font-semibold ${metricClass(val as number | null)}`}>
                    {metricPct(val as number | null)}
                  </p>
                </div>
              );
            })}
            <div className="bg-white rounded-lg border p-4">
              <p className="text-xs text-muted-foreground mb-1">有效 / 总数</p>
              <p className="text-2xl font-semibold tabular-nums">
                {latest.valid}<span className="text-base text-muted-foreground">/{latest.total}</span>
              </p>
            </div>
            <div className="bg-white rounded-lg border p-4">
              <p className="text-xs text-muted-foreground mb-1">跳过</p>
              <p className="text-2xl font-semibold tabular-nums">{latest.skipped}</p>
            </div>
          </div>

          {/* ── 趋势图 ── */}
          <div className="bg-white rounded-lg border p-4 mb-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold text-sm text-foreground">
                {currentDs?.display_name} — 指标趋势
              </h3>
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
            {runs.length > 1 ? (
              <RagasTrendChart
                runs={runs}
                metric={selectedMetric as keyof typeof runs[0]}
              />
            ) : (
              <p className="text-center text-muted-foreground py-8 text-sm">
                至少需要 2 次运行才能显示趋势（当前 {runs.length} 次）
              </p>
            )}
          </div>

          {/* ── Context 指标预览（从 RAGAS 评测结果读取） ── */}
          <div className="bg-white rounded-lg border p-4 mb-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold text-sm text-foreground">
                Context Precision / Recall
              </h3>
              <span className="rounded-[6px] border px-2 py-[3px] text-[11px] text-muted-foreground">
                {hasContext ? "RAGAS × BEIR" : "BEIR 数据集"}
              </span>
            </div>
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-muted-foreground">
                  <th className="text-left py-2">数据集</th>
                  <th className="text-right py-2">Context Precision</th>
                  <th className="text-right py-2">Context Recall</th>
                  <th className="text-right py-2">状态</th>
                </tr>
              </thead>
              <tbody>
                {["nfcorpus", "fiqa", "msmarco"].map((ds) => {
                  const currentName = currentDs?.name ?? "";
                  const isCurrent = currentName.includes(ds);
                  const cp = isCurrent ? latest?.context_precision : null;
                  const cr = isCurrent ? latest?.context_recall : null;
                  return (
                    <tr key={ds} className="border-b last:border-0">
                      <td className="py-2 font-mono text-xs">{ds}</td>
                      <td className={`text-right py-2 ${metricClass(cp)}`}>
                        {metricPct(cp)}
                      </td>
                      <td className={`text-right py-2 ${metricClass(cr)}`}>
                        {metricPct(cr)}
                      </td>
                      <td className="text-right py-2">
                        {isCurrent && cp != null ? (
                          <span className="text-[11px] text-green-600">已评测</span>
                        ) : (
                          <span className="text-[11px] text-muted-foreground">
                            {isCurrent ? "待运行" : "切换数据集查看"}
                          </span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* ── 运行历史 ── */}
          <div className="bg-white rounded-lg border p-4">
            <h3 className="font-semibold text-sm text-foreground mb-3">运行历史</h3>
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-muted-foreground">
                  <th className="text-left py-2">运行 ID</th>
                  <th className="text-left py-2">时间</th>
                  <th className="text-right py-2">Faithfulness</th>
                  <th className="text-right py-2">Hallucination</th>
                  <th className="text-right py-2">有效/总数</th>
                </tr>
              </thead>
              <tbody>
                {runs.map((r) => (
                  <tr key={r.run_id} className="border-b last:border-0">
                    <td className="py-2 font-mono text-xs">{r.run_id}</td>
                    <td className="py-2 text-xs">
                      {new Date(r.timestamp).toLocaleString("zh-CN")}
                    </td>
                    <td className={`text-right py-2 ${metricClass(r.faithfulness)}`}>
                      {metricPct(r.faithfulness)}
                    </td>
                    <td className={`text-right py-2 ${metricClass(r.hallucination_rate != null ? 1 - r.hallucination_rate : null)}`}>
                      {metricPct(r.hallucination_rate)}
                    </td>
                    <td className="text-right py-2 tabular-nums">
                      {r.valid}/{r.total}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </section>
  );
}

// ── 迷你趋势图 ──

function RagasTrendChart({
  runs,
  metric,
}: {
  runs: RagasRunEntry[];
  metric: keyof RagasRunEntry;
}) {
  const values = runs
    .map((r) => ({ ...r, v: r[metric] as number | null }))
    .filter((r) => r.v != null)
    .reverse();

  if (values.length < 2) {
    return (
      <p className="text-center text-muted-foreground py-8 text-sm">
        数据点不足
      </p>
    );
  }

  const maxV = Math.max(...values.map((p) => p.v!), 0.01);
  const minV = Math.min(...values.map((p) => p.v!), 0);
  const range = maxV - minV || 0.01;
  const height = 160;

  const avg = values.reduce((s, p) => s + p.v!, 0) / values.length;

  return (
    <div className="relative">
      <div
        className="flex items-end gap-[2px]"
        style={{ minHeight: `${height}px`, height: `${height}px` }}
      >
        {values.map((p, i) => {
          const h = ((p.v! - minV) / range) * (height - 20) + 4;
          return (
            <div key={i} className="relative group flex-1 min-w-[3px]">
              <div
                className="w-full bg-[var(--action)]/70 hover:bg-[var(--action)] rounded-t transition-colors cursor-pointer"
                style={{ height: `${h}px` }}
                title={`${p.run_id}: ${(p.v! * 100).toFixed(1)}%`}
              />
            </div>
          );
        })}
      </div>
      <p className="text-xs text-muted-foreground mt-1">
        平均: {(avg * 100).toFixed(1)}% &middot; {values.length} 次运行
      </p>
    </div>
  );
}
