import { useNavigate } from "react-router-dom";

import type { DocumentStatusCounts } from "@/lib/dashboard-api";
import { formatNumberLocale } from "@/lib/dashboard-format";
import { Button } from "@/components/ui/button";

interface IngestionPanelProps {
  docStatus: DocumentStatusCounts;
  successRate: number | null;
  avgDuration: number | null;
  chunkCount: number;
  retryCount7d: number;
  cleanFailureCount: number;
  recentKbName?: string | null;
}

const PIPE_STAGES = [
  { key: "queued" as const, label: "排队", tone: "var(--que)" },
  { key: "processing" as const, label: "处理中", tone: "var(--warn)" },
  { key: "completed" as const, label: "已完成", tone: "var(--ok)" },
  { key: "failed" as const, label: "失败", tone: "var(--bad)" },
];

function healthClass(val: number, zeroIsOk: boolean): string {
  if (zeroIsOk && val === 0) return "text-[var(--ok)]";
  return val > 0 ? "text-[var(--warn)]" : "text-[var(--ok)]";
}

function formatChunk(n: number): string {
  if (n >= 1000) return formatNumberLocale(n);
  return String(n);
}

export function IngestionPanel({
  docStatus,
  successRate,
  avgDuration,
  chunkCount,
  retryCount7d,
  cleanFailureCount,
  recentKbName,
}: IngestionPanelProps) {
  const total =
    docStatus.queued +
    docStatus.processing +
    docStatus.completed +
    docStatus.failed;
  const pending = docStatus.queued + docStatus.processing;
  const isEmpty = total === 0;
  const navigate = useNavigate();
  const activeStages = PIPE_STAGES.filter(({ key }) => docStatus[key] > 0);

  return (
    <div className="dash-panel dash-ingest grid grid-cols-1 gap-0 md:grid-cols-[1.2fr_1px_1fr]">
      <div className="flex flex-col py-1 md:pr-5">
        <div className="mb-3 text-[13px] text-[var(--mut)]">文档流转</div>

        {isEmpty ? (
          <div className="flex flex-1 flex-col justify-center gap-2 py-6">
            <p className="font-[var(--serif)] text-[15px] text-foreground">
              暂无入库活动
            </p>
            <p className="max-w-[280px] text-xs leading-relaxed text-muted">
              上传文档后，此处显示流转与成功率。
            </p>
            <Button
              type="button"
              size="sm"
              variant="outline"
              className="mt-1 w-fit"
              onClick={() => navigate("/knowledge-bases")}
            >
              去上传文档
            </Button>
          </div>
        ) : (
          <>
            <div className="mb-3 flex h-10 overflow-hidden rounded-xl text-xs font-semibold text-white shadow-[inset_0_1px_2px_rgba(0,0,0,0.06)]">
              {activeStages.map(({ key, label, tone }) => (
                <div
                  key={key}
                  className="flex items-center justify-center px-2.5 transition-[flex] duration-300"
                  style={{ flex: docStatus[key], background: tone }}
                >
                  {label} {docStatus[key]}
                </div>
              ))}
            </div>

            <div className="mb-3 flex flex-wrap gap-3 text-xs text-muted">
              {activeStages.map(({ key, label, tone }) => (
                <span key={key} className="flex items-center gap-1.5">
                  <span
                    className="inline-block h-2 w-2 rounded-[3px]"
                    style={{ background: tone }}
                  />
                  {label}
                </span>
              ))}
            </div>

            <div className="mt-auto flex gap-6 border-t border-[var(--line2)] pt-3">
              <div>
                <div
                  className={`font-[var(--serif)] text-2xl font-semibold ${healthClass(successRate ?? 0, false)}`}
                >
                  {successRate !== null ? `${successRate}%` : "—"}
                </div>
                <div className="mt-1 text-xs text-muted">入库成功率</div>
              </div>
              <div>
                <div className="font-[var(--serif)] text-2xl font-semibold text-foreground">
                  {avgDuration !== null ? `${avgDuration.toFixed(1)}s` : "—"}
                </div>
                <div className="mt-1 text-xs text-muted">平均耗时</div>
              </div>
              <div>
                <div className="font-[var(--serif)] text-2xl font-semibold text-foreground">
                  {formatChunk(chunkCount)}
                </div>
                <div className="mt-1 text-xs text-muted">切片数</div>
              </div>
            </div>
          </>
        )}
      </div>

      <div className="hidden bg-[var(--line2)] md:block" aria-hidden />

      <div className="border-t border-[var(--line2)] py-1 pt-4 md:border-0 md:pl-5 md:pt-1">
        <div className="mb-3 text-[13px] text-[var(--mut)]">存储健康</div>
        <div>
          {[
            { label: "近 7 日重试", value: retryCount7d, zeroOk: false },
            { label: "清理失败累计", value: cleanFailureCount, zeroOk: true },
            { label: "待处理队列", value: pending, zeroOk: false },
            {
              label: "最近活跃库",
              value: recentKbName ?? "—",
              isText: true,
            },
          ].map(({ label, value, zeroOk, isText }) => (
            <div
              key={label}
              className="flex items-baseline justify-between border-b border-[var(--line2)] py-3 text-[13px] last:border-0"
            >
              <span>{label}</span>
              {isText ? (
                <span className="max-w-[140px] truncate text-left">
                  {String(value)}
                </span>
              ) : (
                <span
                  className={`font-[var(--serif)] text-[1.1875rem] font-semibold ${healthClass(value as number, zeroOk ?? false)}`}
                >
                  {zeroOk && value === 0 ? `${value} ✓` : value}
                </span>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
