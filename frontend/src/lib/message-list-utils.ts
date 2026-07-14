import type { ChatMessage } from "@/components/chat/ChatMessageList";

export type MessageDayGroup = "today" | "yesterday" | "earlier";

export interface IndexedChatMessage {
  message: ChatMessage;
  index: number;
}

export interface MessageDayGroupBlock {
  dayKey: string;
  pillLabel: string;
  items: IndexedChatMessage[];
}

function localDayKey(iso: string): string {
  const date = new Date(iso);
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function dayDiffFromToday(iso: string): number {
  const date = new Date(iso);
  const now = new Date();
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const startOfDate = new Date(
    date.getFullYear(),
    date.getMonth(),
    date.getDate(),
  );
  return Math.round(
    (startOfToday.getTime() - startOfDate.getTime()) / 86_400_000,
  );
}

export function messageDayGroup(iso: string): MessageDayGroup {
  const dayDiff = dayDiffFromToday(iso);
  if (dayDiff <= 0) return "today";
  if (dayDiff === 1) return "yesterday";
  return "earlier";
}

export function formatMessageDayPill(iso: string): string {
  const group = messageDayGroup(iso);
  if (group === "today") return "今天";
  if (group === "yesterday") return "昨天";
  return new Date(iso).toLocaleDateString("zh-CN", {
    month: "long",
    day: "numeric",
  });
}

export function formatMessageTime(iso: string): string {
  const date = new Date(iso);
  const group = messageDayGroup(iso);
  const time = date.toLocaleTimeString("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });

  if (group === "today") return `今天 ${time}`;
  if (group === "yesterday") return `昨天 ${time}`;

  const dayDiff = dayDiffFromToday(iso);
  if (dayDiff <= 7) return `${dayDiff} 天前`;

  return `${date.toLocaleDateString("zh-CN", {
    month: "long",
    day: "numeric",
  })} ${time}`;
}

export function groupMessagesByDay(
  messages: ChatMessage[],
): MessageDayGroupBlock[] {
  const groups: MessageDayGroupBlock[] = [];

  messages.forEach((message, index) => {
    const dayKey = localDayKey(message.createdAt);
    const last = groups[groups.length - 1];
    if (last?.dayKey === dayKey) {
      last.items.push({ message, index });
      return;
    }
    groups.push({
      dayKey,
      pillLabel: formatMessageDayPill(message.createdAt),
      items: [{ message, index }],
    });
  });

  return groups;
}
