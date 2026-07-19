import { useEffect, useRef, useState } from "react";

import type {
  ChatMessage,
} from "@/components/chat/ChatMessageList";
import type {
  ChatThread,
  ThreadContext,
} from "@/lib/thread-api";
import { useApprovalResolver } from "@/lib/use-approval-resolver";
import { useMessageStream } from "@/lib/use-message-stream";
import { useThreadList } from "@/lib/use-thread-list";

export function useThreadSession(context: ThreadContext) {
  // Shared state owned by the facade
  const [activeThreadId, setActiveThreadId] = useState<string | null>(null);
  const [threads, setThreads] = useState<ChatThread[]>([]);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const messagesRef = useRef<ChatMessage[]>([]);
  const activeThreadIdRef = useRef<string | null>(null);

  useEffect(() => {
    messagesRef.current = messages;
  }, [messages]);

  useEffect(() => {
    activeThreadIdRef.current = activeThreadId;
  }, [activeThreadId]);

  // Sub-hooks with stable individual parameters
  // Order: messageStream first (threadList needs abortStreaming)
  const ms = useMessageStream(
    context,
    setActiveThreadId,
    activeThreadIdRef,
    setMessages,
    messagesRef,
    setThreads,
  );

  const tl = useThreadList(
    context,
    setActiveThreadId,
    setThreads,
    setMessages,
    ms.abortStreaming,
  );

  const ar = useApprovalResolver(setMessages);

  // Lifecycle effects (mirroring original order)

  useEffect(() => {
    ms.abortStreaming();
    void tl.loadThreads();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tl.loadThreads, ms.abortStreaming]);

  useEffect(() => {
    if (ms.sendingRef.current) {
      // Sending: sendMessage has already populated messages with
      // user + assistant placeholder; stream callbacks handle updates.
      // Don't call loadMessages — it fetches from the API which is
      // still empty mid-stream, overwriting the in-progress messages.
      return;
    }
    ms.abortStreaming();
    void ms.loadMessages(activeThreadId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeThreadId, ms.abortStreaming, ms.loadMessages]);

  useEffect(() => {
    return () => {
      ms.streamAbortRef.current?.abort();
      ms.streamAbortRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return {
    threads,
    threadsLoading: tl.threadsLoading,
    threadsError: tl.threadsError,
    activeThreadId,
    messages,
    historyLoading: ms.historyLoading,
    historyError: ms.historyError,
    streaming: ms.streaming,
    streamError: ms.streamError,
    toolSteps: ms.toolSteps,
    agentBudget: ms.agentBudget,
    resolvingApprovalId: ar.resolvingApprovalId,
    approvalError: ar.approvalError,
    loadThreads: tl.loadThreads,
    loadMessages: ms.loadMessages,
    selectThread: tl.selectThread,
    resetActiveChat: tl.resetActiveChat,
    createNewThread: tl.createNewThread,
    renameThread: tl.renameThread,
    archiveThread: tl.archiveThread,
    toggleCitation: ms.toggleCitation,
    resolveApproval: ar.resolveApproval,
    sendMessage: ms.sendMessage,
    regenerate: ms.regenerate,
    abortStreaming: ms.abortStreaming,
    abortForModeSwitch: ms.abortForModeSwitch,
  };
}
