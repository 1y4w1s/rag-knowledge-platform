import { Loader2 } from "lucide-react";

import { cn } from "@/lib/utils";

interface ChatLoadingPanelProps {
  label: string;
  compact?: boolean;
  className?: string;
  testId?: string;
}

/** G2-3.3 · 对话加载态 — spinner + 文案，Ask/Chat/ThreadList 共用 */
export function ChatLoadingPanel({
  label,
  compact = false,
  className,
  testId,
}: ChatLoadingPanelProps) {
  return (
    <div
      className={cn(
        "chat-state-loading",
        compact ? "chat-state-loading-compact" : "chat-state-loading-default",
        className,
      )}
      role="status"
      aria-live="polite"
      aria-busy="true"
      data-testid={testId}
    >
      <Loader2
        className={cn(
          "animate-spin text-muted",
          compact ? "h-4 w-4" : "h-5 w-5",
        )}
        aria-hidden
      />
      <p className="chat-state-loading-label">{label}</p>
    </div>
  );
}
