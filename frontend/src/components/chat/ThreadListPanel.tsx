import { Loader2, Trash2 } from "lucide-react";

import { ChatEmptyPanel } from "@/components/chat/ChatEmptyPanel";
import { ChatLoadingPanel } from "@/components/chat/ChatLoadingPanel";
import { AlertBanner } from "@/components/ui/AlertBanner";
import { Button } from "@/components/ui/button";
import type { ChatThread } from "@/lib/thread-api";
import {
  defaultThreadTitle,
  formatThreadListTime,
  groupThreadsByDay,
} from "@/lib/thread-list-utils";
import { cn } from "@/lib/utils";

export interface ThreadListPanelProps {
  threads: ChatThread[];
  activeThreadId: string | null;
  loading?: boolean;
  error?: string | null;
  creating?: boolean;
  archivingThreadId?: string | null;
  onSelectThread: (threadId: string) => void;
  onCreateThread: () => void | Promise<void>;
  onArchiveThread?: (threadId: string) => void | Promise<void>;
  onRetry?: () => void;
  subtitle?: string;
  className?: string;
}

export function ThreadListPanel({
  threads,
  activeThreadId,
  loading = false,
  error = null,
  creating = false,
  archivingThreadId = null,
  onSelectThread,
  onCreateThread,
  onArchiveThread,
  onRetry,
  subtitle = "当前空间 · 仅自己可见",
  className,
}: ThreadListPanelProps) {
  const grouped = groupThreadsByDay(threads);
  const showEmpty = !loading && !error && threads.length === 0;

  return (
    <aside
      className={cn("thread-list-panel", className)}
      aria-label="历史会话列表"
      data-testid="thread-list-panel"
    >
      <div className="thread-list-head">
        <h3 className="thread-list-title">历史会话</h3>
        {subtitle ? (
          <p className="thread-list-subtitle">{subtitle}</p>
        ) : null}
        <button
          type="button"
          className="thread-list-new-btn"
          onClick={() => void onCreateThread()}
          disabled={creating || loading}
          data-testid="thread-new-btn"
        >
          {creating ? (
            <>
              <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden />
              创建中…
            </>
          ) : (
            "+ 新建对话"
          )}
        </button>
      </div>

      <div className="thread-list-scroll">
        {error ? (
          <AlertBanner
            className="mx-2 mt-2"
            action={
              onRetry ? (
                <Button type="button" variant="outline" size="sm" onClick={onRetry}>
                  重试
                </Button>
              ) : undefined
            }
          >
            {error}
          </AlertBanner>
        ) : null}

        {loading ? (
          <ChatLoadingPanel
            label="加载会话列表…"
            compact
            testId="thread-list-loading"
          />
        ) : null}

        {showEmpty ? (
          <ChatEmptyPanel
            title="暂无会话"
            description="点上方「新建对话」开始第一次问答"
            compact
            testId="thread-list-empty"
          />
        ) : null}

        {!loading && !error
          ? grouped.map(({ group, label, threads: groupThreads }) => (
              <section key={group} aria-label={label}>
                <h4 className="thread-list-group">{label}</h4>
                <ul className="thread-list-items">
                  {groupThreads.map((thread) => {
                    const active = thread.id === activeThreadId;
                    const archiving = archivingThreadId === thread.id;

                    return (
                      <li key={thread.id} className="thread-list-row">
                        <button
                          type="button"
                          className={cn(
                            "thread-list-item",
                            active && "thread-list-item-active",
                          )}
                          onClick={() => onSelectThread(thread.id)}
                          aria-current={active ? "true" : undefined}
                          data-testid={`thread-item-${thread.id}`}
                        >
                          <span className="thread-list-item-title">
                            {defaultThreadTitle(thread)}
                          </span>
                          <span className="thread-list-item-time">
                            {formatThreadListTime(thread)}
                          </span>
                        </button>
                        {onArchiveThread ? (
                          <button
                            type="button"
                            className="thread-list-delete-btn"
                            onClick={() => void onArchiveThread(thread.id)}
                            disabled={archiving}
                            aria-label={`删除会话 ${defaultThreadTitle(thread)}`}
                            data-testid={`thread-delete-${thread.id}`}
                          >
                            {archiving ? (
                              <Loader2
                                className="h-3.5 w-3.5 animate-spin"
                                aria-hidden
                              />
                            ) : (
                              <Trash2 className="h-3.5 w-3.5" aria-hidden />
                            )}
                          </button>
                        ) : null}
                      </li>
                    );
                  })}
                </ul>
              </section>
            ))
          : null}
      </div>
    </aside>
  );
}
