import { ChatLoadingPanel } from "@/components/chat/ChatLoadingPanel";
import { cn } from "@/lib/utils";

interface ChatPageShellSkeletonProps {
  label?: string;
  className?: string;
}

/** G2-3.3 · AskPage / ChatPage 首屏加载共用壳 */
export function ChatPageShellSkeleton({
  label = "加载对话页…",
  className,
}: ChatPageShellSkeletonProps) {
  return (
    <div
      className={cn(
        "full-bleed h-auto overflow-visible",
        className,
      )}
    >
      <div className="h-12 animate-pulse border-b border-[var(--line2)] bg-[var(--surf-shell)]" />
      <div className="flex flex-1 items-center justify-center px-6">
        <ChatLoadingPanel label={label} />
      </div>
    </div>
  );
}
