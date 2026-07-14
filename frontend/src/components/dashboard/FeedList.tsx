import type { LucideIcon } from "lucide-react";
import {
  MessageSquare,
  Upload,
  PenLine,
  RefreshCw,
  UserPlus,
  Lock,
} from "lucide-react";

const ICON_MAP: Record<string, LucideIcon> = {
  "message-square": MessageSquare,
  upload: Upload,
  "pen-line": PenLine,
  "refresh-cw": RefreshCw,
  "user-plus": UserPlus,
  lock: Lock,
};

export interface FeedItem {
  /** 内置图标名（message-square / upload / ...）或传 icon 组件时忽略 */
  iconName?: string;
  /** 可选：直接传 LucideIcon 组件，优先于 iconName */
  icon?: LucideIcon;
  title: string;
  meta: string;
  time?: string;
}

interface FeedListProps {
  title: string;
  tag?: string;
  items: FeedItem[];
}

export function FeedList({ title, tag, items }: FeedListProps) {
  return (
    <div className="rounded-2xl border border-[var(--line2)] bg-[var(--surf)] p-5 shadow-[var(--top-hi),var(--card-shadow)] transition-colors hover:border-[var(--line)]">
      <div className="mb-4 flex items-center justify-between gap-3">
        <span className="text-[13px] text-[var(--mut)] tracking-wide">{title}</span>
        {tag && (
          <span className="rounded-[6px] border border-[var(--line2)] px-[7px] py-[2px] text-[10px] text-[var(--mut)] tracking-wider">
            {tag}
          </span>
        )}
      </div>

      <div className="flex flex-col gap-0">
        {items.length === 0 && (
          <p className="py-8 text-center text-sm text-[var(--mut)]">暂无记录</p>
        )}
        {items.map(({ icon, iconName, title, meta, time }, i) => {
          const Icon = icon ?? (iconName ? ICON_MAP[iconName] : undefined);
          return (
            <div
              key={i}
              className={`flex gap-3 py-[11px] text-[13px] items-start ${
                i < items.length - 1 ? "border-b border-[var(--line2)]" : ""
              }`}
            >
              {/* 图标 */}
              <span className="flex h-[26px] w-[26px] shrink-0 items-center justify-center rounded-lg bg-[var(--surf2)] text-[var(--mut)]">
                {Icon && <Icon className="h-[15px] w-[15px]" strokeWidth={2} />}
              </span>
              {/* 内容 */}
              <div className="min-w-0 flex-1">
                <div className="text-[var(--text)]">{title}</div>
                <div className="mt-0.5 text-[11px] text-[var(--mut)]">{meta}</div>
              </div>
              {/* 时间 */}
              {time && (
                <span className="shrink-0 pt-0.5 text-[11px] text-[var(--mut)]">{time}</span>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
