interface PerfTableProps {
  latency: number | null;
  sampleCount: number;
}

export function PerfTable({ latency, sampleCount }: PerfTableProps) {
  const rows: { label: string; value: string }[] = [
    {
      label: "平均检索延迟",
      value: latency !== null ? `${latency}ms` : "—",
    },
    {
      label: "样本数",
      value: String(sampleCount),
    },
  ];

  return (
    <div className="dash-panel h-full">
      <div className="mb-3 flex items-center justify-between gap-3">
        <span className="text-[13px] text-[var(--mut)]">检索性能</span>
        <span className="text-xs text-muted">近 7 日</span>
      </div>
      <div>
        {rows.map(({ label, value }) => (
          <div
            key={label}
            className="flex items-baseline justify-between border-b border-[var(--line2)] py-[11px] text-[13px] last:border-0"
          >
            <span>{label}</span>
            <span className="font-[var(--serif)] text-[1.1875rem] font-semibold tabular-nums">
              {value}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
