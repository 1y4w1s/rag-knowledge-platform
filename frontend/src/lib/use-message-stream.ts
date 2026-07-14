import { useCallback, useRef, useState } from "react";
import type { Dispatch, MutableRefObject, SetStateAction } from "react";

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
  createThread as createThreadApi,
  fetchThreadMessages,
  fetchThreads as fetchThreadsApi,
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

export function useMessageStream(
  context: ThreadContext,
  setActiveThreadId: Dispatch<SetStateAction<string | null>>,
  activeThreadIdRef: MutableRefObject<string | null>,
  setMessages: Dispatch<SetStateAction<ChatMessage[]>>,
  messagesRef: MutableRefObject<ChatMessage[]>,
  setThreads: Dispatch<SetStateAction<ChatThread[]>>,
) {
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [streaming, setStreaming] = useState(false);
  const [streamError, setStreamError] = useState<string | null>(null);
  const [toolSteps, setToolSteps] = useState<ToolTimelineStep[]>([]);
  const [agentBudget, setAgentBudget] = useState<AgentBudgetState | null>(null);

  const streamAbortRef = useRef<AbortController | null>(null);
  const streamingRef = useRef(false);
  const inFlightUserMessageRef = useRef<string | null>(null);
  const sendingRef = useRef(false);

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
  }, [messagesRef, setMessages]);

  const abortForModeSwitch = useCallback((): string | null => {
    if (!streamingRef.current) return null;
    return abortStreaming();
  }, [abortStreaming]);

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
    [context, activeThreadIdRef, setMessages],
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
    [setMessages],
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
          const thread = await createThreadApi(context);
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
            onToken: (text: string) => {
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
            },
          },
          signal,
          mode,
        );

        const rows = await fetchThreadsApi(context);
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
    [
      context,
      activeThreadIdRef,
      setActiveThreadId,
      setThreads,
      setMessages,
      messagesRef,
    ],
  );

  return {
    historyLoading,
    historyError,
    streaming,
    streamError,
    toolSteps,
    agentBudget,
    streamAbortRef,
    sendingRef,
    loadMessages,
    sendMessage,
    abortStreaming,
    abortForModeSwitch,
    toggleCitation,
  };
}
