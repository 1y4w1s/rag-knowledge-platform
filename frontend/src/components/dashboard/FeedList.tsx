import { Link } from "react-router-dom";
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
  iconName?: string;
  icon?: LucideIcon;
  title: string;
  meta: string;
  time?: string;
  href?: string;
  citeChip?: string;
}

interface FeedListProps {
  title: string;
  items: FeedItem[];
  emptyText?: string;
  emptyIcon?: "message-square" | "refresh-cw";
  variant?: "default" | "soft";
}

export function FeedList({
  title,
  items,
  emptyText,
  emptyIcon = "message-square",
}: FeedListProps) {
  const EmptyIcon = ICON_MAP[emptyIcon] ?? MessageSquare;
  const visible = items.filter((i) => i.title || i.icon || i.iconName);

  return (
    <div className="dash-panel">
      <div className="mb-3 text-[13px] text-[var(--mut)]">{title}</div>
      <div className="flex flex-col gap-1.5">
        {visible.length === 0 ? (
          <div className="flex flex-col items-center gap-2 py-8 text-muted">
            <EmptyIcon className="h-5 w-5 opacity-50" strokeWidth={1.5} />
            <p className="text-sm">{emptyText ?? "暂无记录"}</p>
          </div>
        ) : (
          visible.map((item, i) => {
            const Icon =
              item.icon ?? (item.iconName ? ICON_MAP[item.iconName] : undefined);
            const body = (
              <>
                <span className="dash-feed-ic">
                  {Icon ? (
                    <Icon className="h-[15px] w-[15px]" strokeWidth={2} />
                  ) : null}
                </span>
                <div className="min-w-0 flex-1">
                  <div className="text-[0.875rem] font-semibold text-foreground">
                    {item.title}
                  </div>
                  <div className="mt-0.5 text-xs text-muted">{item.meta}</div>
                  {item.citeChip ? (
                    <span className="dash-cite-chip">{item.citeChip}</span>
                  ) : null}
                </div>
                {item.time ? (
                  <span className="shrink-0 pt-0.5 text-xs text-muted">
                    {item.time}
                  </span>
                ) : null}
              </>
            );

            if (item.href) {
              return (
                <Link
                  key={`${item.title}-${i}`}
                  to={item.href}
                  className="dash-feed-row"
                >
                  {body}
                </Link>
              );
            }

            return (
              <div
                key={`${item.title}-${i}`}
                className="dash-feed-row dash-feed-row-static"
              >
                {body}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
