import type { FeedItem } from "@/components/dashboard/FeedList";
import type { DashboardActivity, RecentThread, TrendPoint } from "@/lib/dashboard-api";

/** 近 7 日趋势 X 轴标签：首=7天前，末=今天，中间留空。 */
export function formatTrendLabels(trend: TrendPoint[]): string[] {
  const n = trend.length;
  return trend.map((_, i) => (i === 0 ? "7天前" : i === n - 1 ? "今天" : ""));
}

/** 紧凑相对时间：刚刚 / N分钟前 / N小时前 / N天前 / MM-DD。 */
export function formatRelativeTime(iso: string): string {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "";
  const m = Math.floor((Date.now() - then) / 60000);
  if (m < 1) return "刚刚";
  if (m < 60) return `${m}分钟前`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}小时前`;
  const d = Math.floor(h / 24);
  if (d < 7) return `${d}天前`;
  const dt = new Date(iso);
  return `${dt.getMonth() + 1}-${dt.getDate()}`;
}

/** 大数缩写：1234 -> 1.2k。 */
export function formatK(n: number): string {
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`;
  return String(n);
}

/** 最近对话 → FeedItem。 */
export function mapThreadsToFeed(threads: RecentThread[]): FeedItem[] {
  return threads.map((t) => ({
    iconName: "message-square",
    title: t.title.trim() || "未命名对话",
    meta: `${t.citation_count} 条引用`,
    time: formatRelativeTime(t.last_activity_at),
  }));
}

/** 操作动态 → FeedItem（后端 type 直接作图标键）。 */
export function mapActivitiesToFeed(activities: DashboardActivity[]): FeedItem[] {
  return activities.map((a) => ({
    iconName: a.type || "refresh-cw",
    title: a.title,
    meta: a.kb_id ? `kb:${a.kb_id.slice(0, 8)}` : "全局",
    time: formatRelativeTime(a.created_at),
  }));
}
