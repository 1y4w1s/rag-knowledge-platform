import { useMemo } from "react";
import type { TrendPoint } from "@/lib/dashboard-api";

export interface ActivityChartProps {
  points: TrendPoint[];
}

interface DayCell {
  date: string;
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

export function ActivityChart({ points }: ActivityChartProps) {
  const days = useMemo(() => buildWeekTrend(points), [points]);
  const max = useMemo(() => Math.max(1, ...days.map((d) => d.count)), [days]);
  const total = useMemo(
    () => days.reduce((sum, d) => sum + d.count, 0),
    [days],
  );

  return (
    <div className="dash-panel">
      <div className="mb-3 text-[13px] text-[var(--mut)]">近 7 日提问</div>

      <div className="grid grid-cols-7 gap-2" aria-label="近 7 日提问趋势">
        {days.map((day) => {
          const intensity = max > 0 ? day.count / max : 0;
          const fillOpacity =
            day.count === 0 ? 0.12 : 0.28 + intensity * 0.72;
          return (
            <div
              key={day.date}
              className="dash-trend-day flex flex-col items-center justify-between gap-1.5"
              title={`${day.date} · ${day.count} 次提问`}
            >
              <span className="text-[11px] leading-none text-muted">
                {day.dayOfWeek.replace("周", "")}
              </span>
              <div
                className="relative w-full aspect-square rounded-[10px]"
                style={{
                  backgroundColor: `color-mix(in srgb, var(--action) ${Math.round(fillOpacity * 100)}%, #f3efe9)`,
                }}
              />
              <div className="flex flex-col items-center gap-0.5 leading-none">
                <span className="text-[10px] text-muted">{day.shortDate}</span>
                <span className="text-[11px] font-medium text-foreground">
                  {day.count > 0 ? `${day.count}` : "—"}
                </span>
              </div>
            </div>
          );
        })}
      </div>

      <div className="mt-3 text-right text-[11px] text-muted">
        7 日合计 {total} 次
      </div>
    </div>
  );
}
