import { useMemo } from "react";
import type { TrendPoint } from "@/lib/dashboard-api";

export interface ActivityChartProps {
  points: TrendPoint[];
  onDayClick?: (date: string) => void;
}

interface DayCell {
  date: string; // YYYY-MM-DD
  count: number;
  dayOfWeek: string;
  shortDate: string;
}

function localISO(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function buildWeekTrend(points: TrendPoint[]): DayCell[] {
  const counts = new Map<string, number>();
  for (const p of points) {
    counts.set(p.date, (counts.get(p.date) ?? 0) + p.count);
  }

  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const week: DayCell[] = [];
  const weekDays = ["日", "一", "二", "三", "四", "五", "六"];

  for (let i = 6; i >= 0; i--) {
    const d = new Date(today);
    d.setDate(today.getDate() - i);
    const iso = localISO(d);
    week.push({
      date: iso,
      count: counts.get(iso) ?? 0,
      dayOfWeek: `周${weekDays[d.getDay()]}`,
      shortDate: `${d.getMonth() + 1}/${d.getDate()}`,
    });
  }
  return week;
}

export function ActivityChart({ points, onDayClick }: ActivityChartProps) {
  const days = useMemo(() => buildWeekTrend(points), [points]);
  const max = useMemo(() => Math.max(1, ...days.map((d) => d.count)), [days]);
  const total = useMemo(() => days.reduce((sum, d) => sum + d.count, 0), [days]);

  return (
    <div className="rounded-2xl border border-[var(--line2)] bg-[var(--surf)] p-5 shadow-[var(--top-hi),var(--card-shadow)] transition-colors hover:border-[var(--line)]">
      <div className="mb-4 flex items-center justify-between gap-3">
        <span className="text-[13px] text-[var(--mut)]">近 7 日提问趋势</span>
        <span className="rounded-[6px] border border-[var(--line2)] px-2 py-[3px] text-xs text-[var(--mut)]">
          按日分桶
        </span>
      </div>

      <div className="grid grid-cols-7 gap-2" aria-label="近 7 日活跃度日历">
        {days.map((day) => {
          const intensity = max > 0 ? day.count / max : 0;
          const fillOpacity = day.count === 0 ? 0 : 0.25 + intensity * 0.75;
          return (
            <button
              key={day.date}
              type="button"
              onClick={() => onDayClick?.(day.date)}
              className="activity-cell relative flex flex-col items-center justify-between gap-1.5 rounded-xl p-1.5 transition-colors hover:bg-[var(--line2)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--action)]"
              aria-label={`${day.date}，${day.count} 次提问`}
            >
              <span className="text-[11px] leading-none text-[var(--mut)]">{day.dayOfWeek}</span>

              <div className="relative w-full aspect-square rounded-[8px] bg-[var(--trend)]">
                <div
                  className="absolute inset-0 rounded-[8px] transition-opacity duration-300"
                  style={{
                    backgroundColor: "var(--trend-peak)",
                    opacity: fillOpacity,
                  }}
                />
              </div>

              <div className="flex flex-col items-center gap-0.5 leading-none">
                <span className="text-[10px] text-[var(--mut)]">{day.shortDate}</span>
                <span className="text-[11px] font-medium text-[var(--text)]">
                  {day.count > 0 ? `${day.count} 次` : "—"}
                </span>
              </div>

              <span className="activity-tooltip pointer-events-none absolute -top-1 left-1/2 z-20 w-max -translate-x-1/2 -translate-y-full rounded-lg border border-[var(--line2)] bg-[var(--surf2)] px-2.5 py-1.5 text-[11px] text-[var(--text)] shadow-md">
                {day.date} · {day.count} 次提问
                {onDayClick && <span className="ml-1 text-[var(--action)]">· 查看</span>}
              </span>
            </button>
          );
        })}
      </div>

      <div className="mt-4 flex items-center gap-3">
        <div className="flex flex-1 items-center gap-2">
          <span className="text-[10px] text-[var(--mut)]">低</span>
          <div className="h-1.5 flex-1 rounded-full bg-gradient-to-r from-[var(--trend)] to-[var(--trend-peak)]" />
          <span className="text-[10px] text-[var(--mut)]">高</span>
        </div>
        <span className="text-[11px] text-[var(--mut)]">7 日合计 {total} 次</span>
      </div>
    </div>
  );
}
