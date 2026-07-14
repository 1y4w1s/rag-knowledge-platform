import { Layers, Quote, Timer } from "lucide-react";



import type { RagMetricsDisplay } from "@/lib/rag-metrics";



interface DashboardRagMetricsProps {

  metrics: RagMetricsDisplay;

}



function formatBaselineDate(iso: string | null): string | null {

  if (!iso) return null;

  const d = new Date(iso);

  if (Number.isNaN(d.getTime())) return null;

  return d.toLocaleDateString("zh-CN", {

    year: "numeric",

    month: "short",

    day: "numeric",

  });

}



function RagMetricItem({

  icon: Icon,

  label,

  value,

  unit,

  hint,

}: {

  icon: typeof Layers;

  label: string;

  value: string;

  unit?: string;

  hint?: string | null;

}) {

  return (

    <div className="flex flex-1 items-center gap-3 rounded-lg border border-border bg-white/[0.72] px-4 py-3.5">

      <Icon className="h-[18px] w-[18px] shrink-0 text-[#52525B]" strokeWidth={1.5} />

      <div className="min-w-0">

        <p className="font-mono text-base font-semibold tabular-nums tracking-[0.05em] text-foreground">

          {value}

          {unit && (

            <span className="ml-0.5 text-sm font-normal text-muted">{unit}</span>

          )}

        </p>

        <p className="mt-1.5 text-[0.72rem] text-muted">

          {label}

          {hint && (

            <span className="mt-0.5 block text-[0.6875rem] text-[#7A6E6A]">{hint}</span>

          )}

        </p>

      </div>

    </div>

  );

}



/** RAG 能力指标条：切片规模 · golden Hit@3 · 近 7 日平均检索延迟 */

export function DashboardRagMetrics({ metrics }: DashboardRagMetricsProps) {

  const baselineDate = formatBaselineDate(metrics.goldenBaselineEvaluatedAt);

  const hitRate =

    metrics.goldenHitRatePercent != null

      ? String(metrics.goldenHitRatePercent)

      : "暂无";

  const latency =

    metrics.avgRetrievalLatencyMs != null

      ? String(Math.round(metrics.avgRetrievalLatencyMs))

      : "暂无";

  const latencyHint =

    metrics.retrievalLatencySampleCount > 0

      ? `近 7 日 ${metrics.retrievalLatencySampleCount} 次对话`

      : "近 7 日暂无对话样本";



  return (

    <section aria-label="RAG 指标">

      <div className="mb-2.5 flex flex-wrap items-baseline justify-between gap-x-2 gap-y-1">

        <h3 className="section-kicker">RAG 概览</h3>

        <p className="text-[0.6875rem] text-[#7A6E6A]">

          指标来自 API · 基线见 RAG_PRODUCTION_BASELINE.md

        </p>

      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">

        <RagMetricItem

          icon={Layers}

          label="向量切片总数"

          value={metrics.totalChunks.toLocaleString("zh-CN")}

        />

        <RagMetricItem

          icon={Quote}

          label="引用命中率（golden_qa · 生产嵌入）"

          value={hitRate}

          unit={metrics.goldenHitRatePercent != null ? "%" : undefined}

          hint={

            baselineDate ? `基线评估 ${baselineDate}` : undefined

          }

        />

        <RagMetricItem

          icon={Timer}

          label="平均检索延迟"

          value={latency}

          unit={metrics.avgRetrievalLatencyMs != null ? "ms" : undefined}

          hint={latencyHint}

        />

      </div>

    </section>

  );

}


