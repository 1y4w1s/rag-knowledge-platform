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
  /** 是否为最新项（显示左侧品牌色高亮条） */
  recent?: boolean;
}

interface FeedListProps {
  title: string;
  tag?: string;
  items: FeedItem[];
  /** 空态自定义文案 */
  emptyText?: string;
  /** 空态自定义图标名 */
  emptyIcon?: "message-square" | "refresh-cw";
}

export function FeedList({ title, tag, items, emptyText, emptyIcon = "message-square" }: FeedListProps) {
  const EmptyIcon = ICON_MAP[emptyIcon] ?? MessageSquare;

  return (
    <div className="rounded-2xl border border-[var(--line2)] bg-[var(--surf)] p-5 shadow-[var(--top-hi),var(--card-shadow)] transition-colors hover:border-[var(--line)]">
      <div className="mb-4 flex items-center justify-between gap-3">
        <span className="text-[13px] text-[var(--mut)]">{title}</span>
        {tag && (
          <span className="rounded-[6px] border border-[var(--line2)] px-2 py-[3px] text-xs text-[var(--mut)]">
            {tag}
          </span>
        )}
      </div>

      <div className="flex flex-col gap-[2px]">
        {items.length === 0 || (items.length === 1 && !items[0].title && !items[0].iconName) ? (
          /* 增强空态：图标 + 虚线风格 */
          <div className="flex flex-col items-center justify-center py-8 px-4 text-[var(--mut)]">
            <div className="mb-3 flex h-[40px] w-[40px] items-center justify-center rounded-lg border border-dashed border-[var(--line)] text-[var(--mut)]">
              <EmptyIcon className="h-[20px] w-[20px]" strokeWidth={1.5} />
            </div>
            <p className="text-[13px]">{emptyText ?? (tag === "audit" ? "暂无操作动态" : "暂无对话记录")}</p>
          </div>
        ) : (
          items.map(({ icon, iconName, title, meta, time, recent }, i) => {
            const Icon = icon ?? (iconName ? ICON_MAP[iconName] : undefined);
            /* 跳过纯占位空项 */
            if (!title && !icon && !iconName) return null;
            return (
              <div
                key={i}
                className={`group relative flex gap-3 py-[11px] text-[13px] items-start transition-colors rounded-lg -mx-2 px-2 ${
                  i < items.length - 1 ? "border-b border-[var(--line2)]" : ""
                } hover:bg-[var(--surf2)]`}
              >
                {/* 最近项左侧品牌色高亮条 */}
                {recent && (
                  <span
                    className="absolute left-0 top-2 bottom-2 w-[3px] rounded-r-[3px] bg-[var(--brand)]"
                    aria-hidden
                  />
                )}
                {/* 图标 */}
                <span className="flex h-[26px] w-[26px] shrink-0 items-center justify-center rounded-lg bg-[var(--surf2)] text-[var(--mut)] transition-colors group-hover:bg-[var(--bg)] group-hover:text-[var(--brand)]">
                  {Icon && <Icon className="h-[15px] w-[15px]" strokeWidth={2} />}
                </span>
                {/* 内容 */}
                <div className="min-w-0 flex-1">
                  <div className="text-[var(--text)]">{title}</div>
                  <div className="mt-0.5 text-xs text-[var(--mut)]">{meta}</div>
                </div>
                {/* 时间 */}
                {time && (
                  <span className="shrink-0 pt-[3px] text-xs text-[var(--mut)]">{time}</span>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
