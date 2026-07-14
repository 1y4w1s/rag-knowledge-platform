import type { ChatThread } from "@/lib/thread-api";

export type ThreadDayGroup = "today" | "yesterday" | "earlier";

const GROUP_LABELS: Record<ThreadDayGroup, string> = {
  today: "今天",
  yesterday: "昨天",
  earlier: "更早",
};

export function threadSortTimestamp(thread: ChatThread): number {
  const iso = thread.last_message_at ?? thread.updated_at ?? thread.created_at;
  return new Date(iso).getTime();
}

export function threadDayGroup(thread: ChatThread): ThreadDayGroup {
  const iso = thread.last_message_at ?? thread.updated_at ?? thread.created_at;
  const date = new Date(iso);
  const now = new Date();
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const startOfDate = new Date(
    date.getFullYear(),
    date.getMonth(),
    date.getDate(),
  );
  const dayDiff = Math.round(
    (startOfToday.getTime() - startOfDate.getTime()) / 86_400_000,
  );
  if (dayDiff <= 0) return "today";
  if (dayDiff === 1) return "yesterday";
  return "earlier";
}

export function formatThreadListTime(thread: ChatThread): string {
  const iso = thread.last_message_at ?? thread.updated_at ?? thread.created_at;
  const date = new Date(iso);
  const group = threadDayGroup(thread);

  if (group === "today") {
    return date.toLocaleTimeString("zh-CN", {
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    });
  }
  if (group === "yesterday") return "昨天";
  return date.toLocaleDateString("zh-CN", {
    month: "short",
    day: "numeric",
  });
}

export function groupThreadsByDay(
  threads: ChatThread[],
): { group: ThreadDayGroup; label: string; threads: ChatThread[] }[] {
  const sorted = [...threads].sort(
    (left, right) => threadSortTimestamp(right) - threadSortTimestamp(left),
  );

  const buckets: Record<ThreadDayGroup, ChatThread[]> = {
    today: [],
    yesterday: [],
    earlier: [],
  };

  for (const thread of sorted) {
    buckets[threadDayGroup(thread)].push(thread);
  }

  return (["today", "yesterday", "earlier"] as const)
    .filter((group) => buckets[group].length > 0)
    .map((group) => ({
      group,
      label: GROUP_LABELS[group],
      threads: buckets[group],
    }));
}

export function defaultThreadTitle(thread: ChatThread): string {
  const title = thread.title.trim();
  return title || "新对话";
}
