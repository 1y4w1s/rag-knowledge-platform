interface TrendChartProps {
  data: number[];
  labels?: string[];
}

export function TrendChart({ data, labels }: TrendChartProps) {
  const max = Math.max(...data, 1);

  return (
    <div className="rounded-2xl border border-[var(--line2)] bg-[var(--surf)] p-5 shadow-[var(--top-hi),var(--card-shadow)] transition-colors hover:border-[var(--line)]">
      <div className="mb-4 flex items-center justify-between gap-3">
        <span className="text-[13px] text-[var(--mut)] tracking-wide">近 7 日提问趋势</span>
        <span className="rounded-[6px] border border-[var(--line2)] px-[7px] py-[2px] text-[10px] text-[var(--mut)] tracking-wider">
          按日分桶 · 待聚合
        </span>
      </div>

      {/* 柱状图 */}
      <div className="flex items-end gap-1.5 h-[90px] mt-2">
        {data.map((v, i) => {
          const pct = Math.round((v / max) * 100);
          const isPeak = v === max;
          return (
            <b
              key={i}
              title={`${v} 次`}
              className={`flex-1 rounded-[4px_4px_2px_2px] opacity-[0.92] transition-all duration-400 hover:opacity-100 ${
                isPeak ? "bg-[var(--trend-peak)]" : "bg-[var(--trend)]"
              }`}
              style={{ height: `${pct}%` }}
            />
          );
        })}
      </div>

      {/* X 轴标签 */}
      <div className="mt-2 flex justify-between text-[10px] text-[var(--mut)]">
        {(labels ?? ["7天前", "", "4天前", "", "今天"]).map((l, i) => (
          <span key={i}>{l}</span>
        ))}
      </div>
    </div>
  );
}
