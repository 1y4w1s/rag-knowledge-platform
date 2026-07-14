import { useCallback, useEffect, useRef, useState } from "react";

import {
  applyAgentBudget,
  applyToolResult,
  applyToolStart,
  type AgentBudgetState,
  type ToolTimelineStep,
} from "@/lib/agent-stream";
import type { AgentMode } from "@/lib/agent-mode";
import {
  isCitationExpandBlocked,
  type ApprovalState,
  type Citation,
  type HistoryMessage,
} from "@/lib/chat-api";
import type {
  AssistantChatMessage,
  ChatMessage,
} from "@/components/chat/ChatMessageList";
import { rollbackInFlightMessages } from "@/lib/thread-stream-abort";
import {
  createThread,
  deleteThread as deleteThreadApi,
  fetchThreadMessages,
  fetchThreads,
  patchThread,
  resolveApproval as resolveApprovalApi,
  streamThreadChat,
  type ChatThread,
  type ThreadContext,
} from "@/lib/thread-api";

function mapHistoryMessage(message: HistoryMessage): ChatMessage {
  if (message.role === "user") {
    return {
      role: "user",
      content: message.content,
      createdAt: message.created_at,
    };
  }
  const approval: ApprovalState | undefined =
    message.approval_id && message.approval_status
      ? {
          approval_id: message.approval_id,
          filename: "",
          kb_name: "",
          draft_preview: "",
          citations: [],
          can_adopt: false,
          status:
            (message.approval_status as Record<string, unknown>)
              .status === "adopted"
              ? "adopted"
              : "cancelled",
        }
      : undefined;

  return {
    role: "assistant",
    content: message.content,
    citations: message.citations ?? [],
    expandedIndex: null,
    createdAt: message.created_at,
    approval,
  };
}

export function useThreadSession(context: ThreadContext) {
  const [threads, setThreads] = useState<ChatThread[]>([]);
  const [threadsLoading, setThreadsLoading] = useState(false);
  const [threadsError, setThreadsError] = useState<string | null>(null);
  const [activeThreadId, setActiveThreadId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [streaming, setStreaming] = useState(false);
  const [streamError, setStreamError] = useState<string | null>(null);
  const [toolSteps, setToolSteps] = useState<ToolTimelineStep[]>([]);
  const [agentBudget, setAgentBudget] = useState<AgentBudgetState | null>(
    null,
  );
  const [resolvingApprovalId, setResolvingApprovalId] = useState<
    string | null
  >(null);
  const [approvalError, setApprovalError] = useState<string | null>(null);
  const streamAbortRef = useRef<AbortController | null>(null);
  const streamingRef = useRef(false);
  const messagesRef = useRef<ChatMessage[]>([]);
  const inFlightUserMessageRef = useRef<string | null>(null);
  const activeThreadIdRef = useRef<string | null>(null);
  const sendingRef = useRef(false);

  useEffect(() => {
    messagesRef.current = messages;
  }, [messages]);

  const abortStreaming = useCallback((): string | null => {
    const wasStreaming = streamingRef.current;
    const pendingDraft = inFlightUserMessageRef.current;

    streamAbortRef.current?.abort();
    streamAbortRef.current = null;
    streamingRef.current = false;
    setStreaming(false);
    setStreamError(null);
    setToolSteps([]);
    setAgentBudget(null);

    const result = rollbackInFlightMessages(messagesRef.current);
    messagesRef.current = result.messages;
    setMessages(result.messages);
    inFlightUserMessageRef.current = null;

    return result.restoredDraft ?? (wasStreaming ? pendingDraft : null);
  }, []);

  const abortForModeSwitch = useCallback((): string | null => {
    if (!streamingRef.current) return null;
    return abortStreaming();
  }, [abortStreaming]);

  useEffect(() => {
    activeThreadIdRef.current = activeThreadId;
  }, [activeThreadId]);

  const loadThreads = useCallback(async () => {
    if (context.kind === "knowledge_base" && !context.kbId) {
      setThreads([]);
      setActiveThreadId(null);
      return;
    }

    setThreadsLoading(true);
    setThreadsError(null);
    try {
      const rows = await fetchThreads(context);
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
  }, [context]);

  const loadMessages = useCallback(
    async (threadId: string | null) => {
      if (!threadId) {
        setMessages([]);
        setHistoryError(null);
        setHistoryLoading(false);
        return;
      }

      setHistoryLoading(true);
      setHistoryError(null);
      try {
        const rows = await fetchThreadMessages(context, threadId);
        if (rows === null) return;
        if (activeThreadIdRef.current !== threadId) return;
        setMessages(rows.map(mapHistoryMessage));
        setToolSteps([]);
        setAgentBudget(null);
      } catch (err) {
        if (activeThreadIdRef.current !== threadId) return;
        setHistoryError(
          err instanceof Error ? err.message : "加载对话历史失败，请稍后重试",
        );
        setMessages([]);
      } finally {
        if (activeThreadIdRef.current === threadId) {
          setHistoryLoading(false);
        }
      }
    },
    [context],
  );

  useEffect(() => {
    abortStreaming();
    void loadThreads();
  }, [abortStreaming, loadThreads]);

  useEffect(() => {
    if (sendingRef.current) {
      // sendMessage 自行管理消息和流状态，避免此 hook 干扰（如 abort 刚启动的 stream）
      void loadMessages(activeThreadId);
      return;
    }
    abortStreaming();
    void loadMessages(activeThreadId);
  }, [activeThreadId, abortStreaming, loadMessages]);

  useEffect(() => {
    return () => {
      streamAbortRef.current?.abort();
      streamAbortRef.current = null;
    };
  }, []);

  const selectThread = useCallback(
    (threadId: string) => {
      abortStreaming();
      setActiveThreadId(threadId);
    },
    [abortStreaming],
  );

  /** Clears the active thread message area without creating a server thread. */
  const resetActiveChat = useCallback(() => {
    abortStreaming();
    setMessages([]);
  }, [abortStreaming]);

  const createNewThread = useCallback(
    async (title = "") => {
      abortStreaming();

      const thread = await createThread(context, title);
      setThreads((prev) => [thread, ...prev]);
      setActiveThreadId(thread.id);
      setMessages([]);
      setHistoryError(null);
      return thread;
    },
    [context, abortStreaming],
  );

  const renameThread = useCallback(
    async (threadId: string, title: string) => {
      const updated = await patchThread(context, threadId, { title });
      setThreads((prev) =>
        prev.map((thread) => (thread.id === threadId ? updated : thread)),
      );
      return updated;
    },
    [context],
  );

  const archiveThread = useCallback(
    async (threadId: string) => {
      await deleteThreadApi(context, threadId);
      setThreads((prev) => {
        const next = prev.filter((thread) => thread.id !== threadId);
        setActiveThreadId((current) => {
          if (current !== threadId) return current;
          return next[0]?.id ?? null;
        });
        return next;
      });
    },
    [context],
  );

  const toggleCitation = useCallback(
    (messageIndex: number, citationIndex: number) => {
      setMessages((prev) =>
        prev.map((message, index) => {
          if (index !== messageIndex || message.role !== "assistant") {
            return message;
          }
          const citation = message.citations[citationIndex];
          if (citation && isCitationExpandBlocked(citation)) {
            return message;
          }
          const nextExpanded =
            message.expandedIndex === citationIndex ? null : citationIndex;
          return { ...message, expandedIndex: nextExpanded };
        }),
      );
    },
    [],
  );

  const resolveApproval = useCallback(
    async (approvalId: string, action: "adopt" | "cancel") => {
      setResolvingApprovalId(approvalId);
      setApprovalError(null);

      try {
        const result = await resolveApprovalApi(approvalId, action);

        setMessages((prev) =>
          prev.map((msg) => {
            if (msg.role !== "assistant" || !msg.approval) return msg;
            if (msg.approval.approval_id !== approvalId) return msg;
            const updated: ApprovalState =
              action === "adopt"
                ? {
                    ...msg.approval,
                    status: "adopted",
                    filename:
                      (result.filename as string) ?? msg.approval.filename,
                  }
                : { ...msg.approval, status: "cancelled" };
            return { ...msg, approval: updated };
          }),
        );
      } catch (err) {
        const message =
          err instanceof Error ? err.message : "操作失败，请稍后重试";
        setApprovalError(message);
      } finally {
        setResolvingApprovalId(null);
      }
    },
    [],
  );

  const sendMessage = useCallback(
    async (message: string, mode: AgentMode = "fast") => {
      if (context.kind === "knowledge_base" && !context.kbId) return;
      if (streamingRef.current) return;

      streamAbortRef.current?.abort();
      const controller = new AbortController();
      streamAbortRef.current = controller;
      const signal = controller.signal;

      setStreamError(null);
      streamingRef.current = true;
      setStreaming(true);
      setToolSteps([]);
      setAgentBudget(null);

      let threadId = activeThreadIdRef.current;
      sendingRef.current = true;
      try {
        if (!threadId) {
          const thread = await createThread(context);
          threadId = thread.id;
          setThreads((prev) => [thread, ...prev]);
          setActiveThreadId(thread.id);
        }

        const now = new Date().toISOString();
        const assistantMessage: AssistantChatMessage = {
          role: "assistant",
          content: "",
          citations: [],
          streaming: true,
          expandedIndex: null,
          createdAt: now,
        };

        inFlightUserMessageRef.current = message;
        setMessages((prev) => {
          const next: ChatMessage[] = [
            ...prev,
            { role: "user", content: message, createdAt: now },
            assistantMessage,
          ];
          messagesRef.current = next;
          return next;
        });

        await streamThreadChat(
          context,
          threadId,
          message,
          {
            onCitation: (citation: Citation) => {
              setMessages((prev) => {
                const next = [...prev];
                const last = next[next.length - 1];
                if (last?.role !== "assistant") return prev;
                next[next.length - 1] = {
                  ...last,
                  citations: [...last.citations, citation],
                };
                return next;
              });
            },
            onToken: (text) => {
              setMessages((prev) => {
                const next = [...prev];
                const last = next[next.length - 1];
                if (last?.role !== "assistant") return prev;
                next[next.length - 1] = {
                  ...last,
                  content: last.content + text,
                };
                return next;
              });
            },
            onDone: (payload) => {
              setMessages((prev) => {
                const next = [...prev];
                const last = next[next.length - 1];
                if (last?.role !== "assistant") return prev;
                const citations = payload.citations;
                next[next.length - 1] = {
                  ...last,
                  citations,
                  streaming: false,
                  expandedIndex: citations.length > 0 ? 0 : null,
                };
                return next;
              });
            },
            onToolStart: (payload) => {
              setToolSteps((prev) => applyToolStart(prev, payload));
            },
            onToolResult: (payload) => {
              setToolSteps((prev) => applyToolResult(prev, payload));
            },
            onAgentBudget: (payload) => {
              setAgentBudget(applyAgentBudget(payload));
            },
            onApprovalRequired: (payload) => {
              const approval: ApprovalState = {
                approval_id: payload.approval_id,
                filename: payload.filename,
                kb_name: payload.kb_name,
                draft_preview: payload.draft_preview,
                citations: payload.citations,
                can_adopt: payload.can_adopt,
                status: "pending",
              };
              setMessages((prev) => {
                const next = [...prev];
                const last = next[next.length - 1];
                if (last?.role !== "assistant") return prev;
                next[next.length - 1] = {
                  ...last,
                  approval,
                };
                return next;
              });
              setApprovalError(null);
            },
          },
          signal,
          mode,
        );

        const rows = await fetchThreads(context);
        if (rows !== null) {
          setThreads(rows);
        }
        inFlightUserMessageRef.current = null;
      } catch (err) {
        if (signal.aborted) {
          const result = rollbackInFlightMessages(messagesRef.current);
          messagesRef.current = result.messages;
          setMessages(result.messages);
          inFlightUserMessageRef.current = null;
          return;
        }
        inFlightUserMessageRef.current = null;
        const messageText =
          err instanceof Error ? err.message : "对话请求失败，请稍后重试";
        setStreamError(messageText);
        setMessages((prev) => {
          const next = [...prev];
          const last = next[next.length - 1];
          if (last?.role === "assistant") {
            next[next.length - 1] = {
              ...last,
              content: last.content || messageText,
              streaming: false,
            };
          }
          return next;
        });
      } finally {
        sendingRef.current = false;
        if (streamAbortRef.current === controller) {
          streamAbortRef.current = null;
        }
        streamingRef.current = false;
        setStreaming(false);
      }
    },
    [context],
  );

  return {
    threads,
    threadsLoading,
    threadsError,
    activeThreadId,
    messages,
    historyLoading,
    historyError,
    streaming,
    streamError,
    toolSteps,
    agentBudget,
    resolvingApprovalId,
    approvalError,
    loadThreads,
    loadMessages,
    selectThread,
    resetActiveChat,
    createNewThread,
    renameThread,
    archiveThread,
    toggleCitation,
    resolveApproval,
    sendMessage,
    abortStreaming,
    abortForModeSwitch,
  };
}
