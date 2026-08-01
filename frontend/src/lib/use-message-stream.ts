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
  clarifyDocumentWrite,
  isCitationExpandBlocked,
  submitDocumentWrite,
  type ApprovalState,
  type Citation,
  type ClarifyPayload,
  type HistoryMessage,
  type ProposalState,
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
  deleteThreadMessage,
  type ChatThread,
  type ThreadContext,
} from "@/lib/thread-api";

function mapHistoryMessage(message: HistoryMessage): ChatMessage {
  if (message.role === "user") {
    return {
      role: "user",
      content: message.content,
      createdAt: message.created_at,
      id: message.id,
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
    id: message.id,
    approval,
    /** 038 · 传递中断状态 */
    status: message.status === "interrupted" ? "interrupted" : undefined,
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
  const [submittingProposal, setSubmittingProposal] = useState(false);
  const [proposalError, setProposalError] = useState<string | null>(null);
  const [clarifying, setClarifying] = useState(false);
  const [clarifyError, setClarifyError] = useState<string | null>(null);

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

  // SSE 自动重连配置
  const MAX_RETRIES = 3;
  const RETRY_DELAY_MS = [1000, 2000, 4000];

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
      let retryCount = 0;

      const doSend = async (): Promise<void> => {
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
                  id: payload.message_id,
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
            onProposalPreview: (payload) => {
              const proposal: ProposalState = {
                operation: payload.operation,
                document_id: payload.document_id,
                kb_id: payload.kb_id,
                filename: payload.filename,
                kb_name: payload.kb_name,
                impact: payload.impact,
                conflict: payload.conflict,
                run_id: payload.run_id,
                can_adopt: payload.can_adopt,
                double_confirm: payload.double_confirm,
              };
              setMessages((prev) => {
                const next = [...prev];
                const last = next[next.length - 1];
                if (last?.role !== "assistant") return prev;
                next[next.length - 1] = {
                  ...last,
                  proposal,
                  clarify: undefined,
                };
                return next;
              });
            },
            onClarify: (payload: ClarifyPayload) => {
              setMessages((prev) => {
                const next = [...prev];
                const last = next[next.length - 1];
                if (last?.role !== "assistant") return prev;
                next[next.length - 1] = {
                  ...last,
                  clarify: payload,
                };
                return next;
              });
            },
          },
          signal,
          mode,
        );

        inFlightUserMessageRef.current = null;
      };
      // doSend 结束

      try {
        await doSend();

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

        // SSE 自动重连：空流（未收到任何 token）时指数退避 + 回滚重试
        const lastMsg = messagesRef.current?.[messagesRef.current.length - 1];
        const isEmpty =
          lastMsg?.role === "assistant" &&
          !lastMsg.content &&
          !lastMsg.citations?.length;
        if (isEmpty && retryCount < MAX_RETRIES) {
          retryCount++;
          const rollback = rollbackInFlightMessages(messagesRef.current);
          messagesRef.current = rollback.messages;
          setMessages(rollback.messages);
          const delay =
            RETRY_DELAY_MS[Math.min(retryCount - 1, RETRY_DELAY_MS.length - 1)];
          await new Promise((r) => setTimeout(r, delay));
          try {
            await doSend();
            inFlightUserMessageRef.current = null;
            return; // 重试成功
          } catch (retryErr) {
            if (signal.aborted) {
              const r2 = rollbackInFlightMessages(messagesRef.current);
              messagesRef.current = r2.messages;
              setMessages(r2.messages);
              inFlightUserMessageRef.current = null;
              return;
            }
          }
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

  const regenerate = useCallback(
    async (messageIndex: number) => {
      const messages = messagesRef.current;
      const assistantMsg = messages[messageIndex];
      if (!assistantMsg || assistantMsg.role !== "assistant") return;
      const userMsg = messages[messageIndex - 1];
      if (!userMsg || userMsg.role !== "user") return;
      const threadId = activeThreadIdRef.current;
      if (!threadId) return;
      if (streamingRef.current) return;

      // Delete the assistant message on the server
      const assistantId = assistantMsg.id;
      if (assistantId) {
        try {
          await deleteThreadMessage(context, threadId, assistantId);
        } catch {
          // Non-critical: proceed even if delete fails
        }
      }

      // Truncate local state: remove assistant message, keep preceding user message
      messagesRef.current = messages.slice(0, messageIndex);
      setMessages(messages.slice(0, messageIndex));

      // Re-send the preceding user message
      await sendMessage(userMsg.content);
    },
    [context, activeThreadIdRef, messagesRef, sendMessage, setMessages],
  );

  const submitProposal = useCallback(
    async (messageIndex: number) => {
      const msg = messagesRef.current[messageIndex];
      if (!msg || msg.role !== "assistant" || !msg.proposal) return;
      const threadId = activeThreadIdRef.current;
      if (!threadId) return;
      const p = msg.proposal;
      setSubmittingProposal(true);
      setProposalError(null);
      try {
        const result = await submitDocumentWrite({
          thread_id: threadId,
          kb_id: p.kb_id,
          document_id: p.document_id,
          operation: p.operation,
          run_id: p.run_id,
        });
        const approval: ApprovalState = {
          approval_id: result.approval_id,
          filename: p.filename,
          kb_name: p.kb_name,
          draft_preview: "",
          citations: [],
          can_adopt: p.can_adopt,
          status: "pending",
          operation: p.operation,
        };
        setMessages((prev) =>
          prev.map((m, i) =>
            i === messageIndex && m.role === "assistant"
              ? { ...m, approval, proposal: undefined }
              : m,
          ),
        );
      } catch (err) {
        setProposalError(
          err instanceof Error ? err.message : "提交审批失败，请稍后重试",
        );
      } finally {
        setSubmittingProposal(false);
      }
    },
    [messagesRef, activeThreadIdRef, setMessages],
  );

  const cancelProposal = useCallback(
    (messageIndex: number) => {
      setMessages((prev) =>
        prev.map((m, i) =>
          i === messageIndex && m.role === "assistant"
            ? { ...m, proposal: undefined }
            : m,
        ),
      );
    },
    [setMessages],
  );

  const clarifyProposal = useCallback(
    async (messageIndex: number, documentId: string, operation: "delete" | "restore") => {
      const threadId = activeThreadIdRef.current;
      if (!threadId) return;
      setClarifying(true);
      setClarifyError(null);
      try {
        const proposal = await clarifyDocumentWrite({
          thread_id: threadId,
          document_id: documentId,
          operation,
        });
        setMessages((prev) =>
          prev.map((m, i) =>
            i === messageIndex && m.role === "assistant"
              ? {
                  ...m,
                  clarify: undefined,
                  proposal: {
                    operation: proposal.operation,
                    document_id: proposal.document_id,
                    kb_id: proposal.kb_id,
                    filename: proposal.filename,
                    kb_name: proposal.kb_name,
                    impact: proposal.impact,
                    conflict: proposal.conflict,
                    run_id: proposal.run_id,
                    can_adopt: proposal.can_adopt,
                    double_confirm: proposal.double_confirm,
                  },
                }
              : m,
          ),
        );
      } catch (err) {
        setClarifyError(
          err instanceof Error ? err.message : "澄清失败，请稍后重试",
        );
      } finally {
        setClarifying(false);
      }
    },
    [activeThreadIdRef, setMessages],
  );

  return {
    historyLoading,
    historyError,
    streaming,
    streamError,
    toolSteps,
    agentBudget,
    submittingProposal,
    proposalError,
    clarifying,
    clarifyError,
    streamAbortRef,
    sendingRef,
    loadMessages,
    sendMessage,
    regenerate,
    submitProposal,
    cancelProposal,
    clarifyProposal,
    abortStreaming,
    abortForModeSwitch,
    toggleCitation,
  };
}
