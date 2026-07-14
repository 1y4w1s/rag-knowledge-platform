import type { DocumentStatusCounts } from "@/lib/dashboard-api";

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
  if (n >= 1000) return (n / 1000).toFixed(1) + "k";
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
    docStatus.queued + docStatus.processing + docStatus.completed + docStatus.failed;
  const pending = docStatus.queued + docStatus.processing;

  return (
    <div className="overflow-hidden rounded-[18px] border border-[var(--line2)] bg-[var(--surf)] shadow-[var(--top-hi),var(--card-shadow)] grid grid-cols-[1.7fr_1px_1fr]">
      {/* 左侧：文档流转管道 */}
      <div className="flex flex-col p-5 lg:p-6">
        <div className="mb-4 flex items-center justify-between gap-3">
          <span className="text-[13px] text-[var(--mut)] tracking-wide">文档流转</span>
          <span className="rounded-[6px] border border-[var(--line2)] px-[7px] py-[2px] text-[10px] text-[var(--mut)] tracking-wider">
            实时四态
          </span>
        </div>

        {/* 管道条 */}
        <div className="mb-4 flex h-[46px] overflow-hidden rounded-[10px] text-xs font-semibold text-[#1a1410]">
          {PIPE_STAGES.map(({ key, label, tone }) => {
            const val = docStatus[key];
            const flex = total > 0 ? val : 1;
            return (
              <i
                key={key}
                className="flex items-center justify-center min-w-[60px] transition-[flex] duration-400"
                style={{ flex, background: tone }}
              >
                {label} {val}
              </i>
            );
          })}
        </div>

        {/* 图例 */}
        <div className="mb-4 flex flex-wrap gap-4 text-xs text-[var(--mut)]">
          {PIPE_STAGES.map(({ key, label, tone }) => (
            <span key={key} className="flex items-center gap-1.5">
              <span className="inline-block h-[9px] w-[9px] rounded-[3px]" style={{ background: tone }} />
              {label} {key}
            </span>
          ))}
        </div>

        {/* 底部 mini 指标 */}
        <div className="mt-auto flex gap-6 border-t border-[var(--line2)] pt-4">
          <div>
            <div className={`font-[var(--serif)] text-2xl font-semibold ${healthClass(successRate ?? 0, false)}`}>
              {successRate !== null ? `${successRate}%` : "—"}
            </div>
            <div className="mt-1 text-[11px] text-[var(--mut)]">入库成功率</div>
          </div>
          <div>
            <div className="font-[var(--serif)] text-2xl font-semibold text-[var(--text)]">
              {avgDuration !== null ? `${avgDuration.toFixed(1)}s` : "—"}
            </div>
            <div className="mt-1 text-[11px] text-[var(--mut)]">平均入库耗时</div>
          </div>
          <div>
            <div className="font-[var(--serif)] text-2xl font-semibold text-[var(--text)]">
              {formatChunk(chunkCount)}
            </div>
            <div className="mt-1 text-[11px] text-[var(--mut)]">切片总数</div>
          </div>
        </div>
      </div>

      {/* 分隔线 */}
      <div className="bg-[var(--line2)]" aria-hidden />

      {/* 右侧：存储健康 */}
      <div className="p-5 lg:p-6">
        <div className="mb-4 flex items-center justify-between gap-3">
          <span className="text-[13px] text-[var(--mut)] tracking-wide">存储健康</span>
          <span className="rounded-[6px] border border-[var(--line2)] px-[7px] py-[2px] text-[10px] text-[var(--mut)] tracking-wider">
            Plan-3E
          </span>
        </div>
        <div className="space-y-0">
          {[
            { label: "近 7 日重试", value: retryCount7d, zeroOk: false },
            { label: "清理失败累计", value: cleanFailureCount, zeroOk: true },
            { label: "待处理队列", value: pending, zeroOk: false },
            { label: "最近活跃库", value: recentKbName ?? "—", isText: true },
          ].map(({ label, value, zeroOk, isText }) => (
            <div
              key={label}
              className="flex items-baseline justify-between border-b border-[var(--line2)] py-[11px] text-[13px] last:border-0"
            >
              <span>{label}</span>
              {isText ? (
                <span className="max-w-[120px] truncate text-left">{String(value)}</span>
              ) : (
                <span className={`font-[var(--serif)] text-[19px] font-semibold ${healthClass(value as number, zeroOk ?? false)}`}>
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
