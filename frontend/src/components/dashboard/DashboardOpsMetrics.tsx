import { HardDriveDownload, RefreshCw, TrendingUp } from "lucide-react";

import type { OpsMetricsDisplay } from "@/lib/ops-metrics";

interface DashboardOpsMetricsProps {
  metrics: OpsMetricsDisplay;
}

function OpsMetricItem({
  icon: Icon,
  label,
  value,
  unit,
  hint,
}: {
  icon: typeof TrendingUp;
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

/** 运营指标条：入库成功率 · 近 7 日重试 · 磁盘清理失败（OrgScope 聚合） */
export function DashboardOpsMetrics({ metrics }: DashboardOpsMetricsProps) {
  const successRate =
    metrics.ingestionSuccessRate != null
      ? String(metrics.ingestionSuccessRate)
      : "暂无";

  return (
    <section aria-label="运营指标">
      <div className="mb-2.5 flex flex-wrap items-baseline justify-between gap-x-2 gap-y-1">
        <h3 className="section-kicker">运营指标</h3>
        <p className="text-[0.6875rem] text-[#7A6E6A]">
          按当前部门可见资料库聚合
        </p>
      </div>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <OpsMetricItem
          icon={TrendingUp}
          label="入库成功率"
          value={successRate}
          unit={metrics.ingestionSuccessRate != null ? "%" : undefined}
          hint={
            metrics.ingestionSuccessRate != null
              ? "已完成 ÷ 终态文档"
              : "尚无终态文档"
          }
        />
        <OpsMetricItem
          icon={RefreshCw}
          label="近 7 日重试次数"
          value={String(metrics.documentRetryCount7d)}
          hint="失败文档手动重试"
        />
        <OpsMetricItem
          icon={HardDriveDownload}
          label="磁盘清理失败"
          value={String(metrics.storageCleanupFailureCount)}
          hint="删文档时磁盘未清干净"
        />
      </div>
    </section>
  );
}
