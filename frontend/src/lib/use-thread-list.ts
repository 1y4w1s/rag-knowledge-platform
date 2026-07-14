import { useCallback, useState } from "react";
import type { Dispatch, SetStateAction } from "react";

import type { ChatMessage } from "@/components/chat/ChatMessageList";

import {
  createThread as createThreadApi,
  deleteThread as deleteThreadApi,
  fetchThreads as fetchThreadsApi,
  patchThread,
  type ChatThread,
  type ThreadContext,
} from "@/lib/thread-api";

export function useThreadList(
  context: ThreadContext,
  setActiveThreadId: Dispatch<SetStateAction<string | null>>,
  setThreads: Dispatch<SetStateAction<ChatThread[]>>,
  setMessages: Dispatch<SetStateAction<ChatMessage[]>>,
  abortStreaming: () => string | null,
) {
  const [threadsLoading, setThreadsLoading] = useState(false);
  const [threadsError, setThreadsError] = useState<string | null>(null);

  const loadThreads = useCallback(async () => {
    if (context.kind === "knowledge_base" && !context.kbId) {
      setThreads([]);
      setActiveThreadId(null);
      return;
    }

    setThreadsLoading(true);
    setThreadsError(null);
    try {
      const rows = await fetchThreadsApi(context);
      if (rows === null) return;

      setThreads(rows);
      setActiveThreadId((current) => {
        if (current && rows.some((thread) => thread.id === current)) {
          return current;
        }
        return rows[0]?.id ?? null;
      });
    } catch (err) {
      setThreadsError(
        err instanceof Error ? err.message : "加载会话列表失败，请稍后重试",
      );
      setThreads([]);
      setActiveThreadId(null);
    } finally {
      setThreadsLoading(false);
    }
  }, [context, setActiveThreadId, setThreads]);

  const selectThread = useCallback(
    (threadId: string) => {
      abortStreaming();
      setActiveThreadId(threadId);
    },
    [abortStreaming, setActiveThreadId],
  );

  /** Clears the active thread message area without creating a server thread. */
  const resetActiveChat = useCallback(() => {
    abortStreaming();
    setMessages([]);
  }, [abortStreaming, setMessages]);

  const createNewThread = useCallback(
    async (title = "") => {
      abortStreaming();

      const thread = await createThreadApi(context, title);
      setThreads((prev) => [thread, ...prev]);
      setActiveThreadId(thread.id);
      setMessages([]);
      return thread;
    },
    [context, abortStreaming, setThreads, setActiveThreadId, setMessages],
  );

  const renameThreadFn = useCallback(
    async (threadId: string, title: string) => {
      const updated = await patchThread(context, threadId, { title });
      setThreads((prev) =>
        prev.map((thread) => (thread.id === threadId ? updated : thread)),
      );
      return updated;
    },
    [context, setThreads],
  );

  const archiveThread = useCallback(
    async (threadId: string) => {
      await deleteThreadApi(context, threadId);
      setThreads((prev) => {
        const next = prev.filter((t) => t.id !== threadId);
        setActiveThreadId((current) => {
          if (current !== threadId) return current;
          return next[0]?.id ?? null;
        });
        return next;
      });
    },
    [context, setThreads, setActiveThreadId],
  );

  return {
    threadsLoading,
    threadsError,
    loadThreads,
    selectThread,
    resetActiveChat,
    createNewThread,
    renameThread: renameThreadFn,
    archiveThread,
  };
}
