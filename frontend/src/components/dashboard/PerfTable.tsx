interface PerfTableProps {
  latency: number | null;
  sampleCount: number;
  citRate?: number | null;
  p95?: number | null;
}

const ROWS = [
  { key: "latency" as const, label: "平均检索延迟", unit: "ms" },
  { key: "sample" as const, label: "样本数", unit: "" },
  { key: "cit" as const, label: "引用覆盖率", unit: "" },
  { key: "p95" as const, label: "P95 延迟", unit: "" },
];

function val(row: PerfTableProps, key: string): number | string | null {
  switch (key) {
    case "latency":
      return row.latency !== null ? `${row.latency}ms` : null;
    case "sample":
      return row.sampleCount;
    case "cit":
      return row.citRate ?? null;
    case "p95":
      return row.p95 ?? null;
    default:
      return null;
  }
}

export function PerfTable(props: PerfTableProps) {
  return (
    <div className="h-full rounded-2xl border border-[var(--line2)] bg-[var(--surf)] p-5 shadow-[var(--top-hi),var(--card-shadow)] transition-colors hover:border-[var(--line)]">
      <div className="mb-4 flex items-center justify-between gap-3">
        <span className="text-[13px] text-[var(--mut)]">检索性能</span>
        <span className="rounded-[6px] border border-[var(--line2)] px-2 py-[3px] text-xs text-[var(--mut)]">
          近 7 日
        </span>
      </div>
      <div>
        {ROWS.map(({ key, label }) => {
          const v = val(props, key);
          return (
            <div
              key={key}
              className="flex items-baseline justify-between border-b border-[var(--line2)] py-[11px] text-[13px] last:border-0"
            >
              <span>{label}</span>
              <span className="font-[var(--serif)] text-[19px] font-semibold tabular-nums">
                {v ?? "—"}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
