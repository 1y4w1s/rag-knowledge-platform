import { useCallback, useEffect, useState } from "react";

import {
  fetchChatMessages,
  isCitationExpandBlocked,
  streamChat,
  type Citation,
  type HistoryMessage,
} from "@/lib/chat-api";
import type { ScopeFetchOptions } from "@/lib/scope-fetch";
import type {
  AssistantChatMessage,
  ChatMessage,
} from "@/components/chat/ChatMessageList";

function mapHistoryMessage(message: HistoryMessage): ChatMessage {
  if (message.role === "user") {
    return {
      role: "user",
      content: message.content,
      createdAt: message.created_at,
    };
  }
  return {
    role: "assistant",
    content: message.content,
    citations: message.citations ?? [],
    expandedIndex: null,
    createdAt: message.created_at,
  };
}

export function useChatSession(
  kbId: string | undefined,
  scope?: Pick<ScopeFetchOptions, "workspace" | "departmentId">,
) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [streaming, setStreaming] = useState(false);
  const [streamError, setStreamError] = useState<string | null>(null);

  const loadHistory = useCallback(async () => {
    if (!kbId) {
      setMessages([]);
      return;
    }
    setHistoryLoading(true);
    setHistoryError(null);
    try {
      const rows = await fetchChatMessages(kbId, 50, scope);
      setMessages(rows.map(mapHistoryMessage));
    } catch (err) {
      setHistoryError(
        err instanceof Error ? err.message : "加载对话历史失败，请稍后重试",
      );
      setMessages([]);
    } finally {
      setHistoryLoading(false);
    }
  }, [kbId, scope]);

  useEffect(() => {
    void loadHistory();
  }, [loadHistory]);

  const resetChat = useCallback(() => {
    setMessages([]);
    setStreaming(false);
    setStreamError(null);
  }, []);

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

  const sendMessage = useCallback(
    async (message: string, signal: AbortSignal) => {
      if (!kbId || streaming) return;

      setStreamError(null);
      setStreaming(true);

      const now = new Date().toISOString();
      const assistantMessage: AssistantChatMessage = {
        role: "assistant",
        content: "",
        citations: [],
        streaming: true,
        expandedIndex: null,
        createdAt: now,
      };

      setMessages((prev) => [
        ...prev,
        { role: "user", content: message, createdAt: now },
        assistantMessage,
      ]);

      try {
        await streamChat(
          kbId,
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
          },
          signal,
          scope,
        );
      } catch (err) {
        if (signal.aborted) return;
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
        setStreaming(false);
      }
    },
    [kbId, scope, streaming],
  );

  return {
    messages,
    historyLoading,
    historyError,
    streaming,
    streamError,
    resetChat,
    toggleCitation,
    sendMessage,
    loadHistory,
  };
}
