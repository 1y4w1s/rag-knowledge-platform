import { useId, type ReactNode } from "react";

import { cn } from "@/lib/utils";

interface ChatEmptyPanelProps {
  title: string;
  description: string;
  action?: ReactNode;
  /** 侧栏 thread 列表等窄区域 */
  compact?: boolean;
  className?: string;
  testId?: string;
}

/** G2-3.3 · 消息区 / 侧栏空态共用虚线卡片壳 — 对齐 kb-result-empty */
export function ChatEmptyPanel({
  title,
  description,
  action,
  compact = false,
  className,
  testId,
}: ChatEmptyPanelProps) {
  const titleId = useId();
  const descId = useId();

  return (
    <div
      className={cn(
        "chat-state-empty",
        compact ? "chat-state-empty-compact" : "chat-state-empty-default",
        className,
      )}
      role="region"
      aria-labelledby={titleId}
      aria-describedby={descId}
      data-testid={testId}
    >
      <p
        id={titleId}
        className="chat-state-empty-title"
      >
        {title}
      </p>
      <p id={descId} className="chat-state-empty-desc">
        {description}
      </p>
      {action ? <div className="chat-state-empty-action">{action}</div> : null}
    </div>
  );
}
