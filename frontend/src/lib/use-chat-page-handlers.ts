import { useCallback, useEffect, useRef, useState } from "react";

import type { AgentMode } from "@/lib/agent-mode";
import { DEFAULT_AGENT_MODE } from "@/lib/agent-mode";
import type { ChatInputDraftRestore } from "@/components/chat/ChatInput";
import type { ChatThread } from "@/lib/thread-api";
import { useMediaQuery } from "@/lib/use-media-query";

interface UseChatPageHandlersProps {
  abortStreaming: () => string | null;
  abortForModeSwitch: () => string | null;
  createNewThread: () => Promise<ChatThread>;
  selectThread: (id: string) => void;
  archiveThread: (id: string) => Promise<void>;
  sendMessage: (msg: string, mode: AgentMode) => Promise<void>;
  regenerate: (messageIndex: number) => Promise<void>;
  resolveApproval: (id: string, action: "adopt" | "cancel") => Promise<void>;
  /** Page-specific guard: AskPage checks teamBusinessAllowed && hasVisibleKbs; ChatPage checks teamBusinessAllowed. */
  canSend?: boolean;
}

/**
 * G2-2.0 · 共享 hook：封装 AskPage / ChatPage 中 7 个完全相同的 handler
 * + threadPanelCollapsed / scrollRef / agentMode 等共享状态。
 */
export function useChatPageHandlers(props: UseChatPageHandlersProps) {
  const {
    abortStreaming,
    abortForModeSwitch,
    createNewThread,
    selectThread,
    archiveThread,
    sendMessage,
    regenerate,
    resolveApproval,
    canSend = true,
  } = props;

  const isMobile = useMediaQuery("(max-width: 768px)");
  const [threadPanelCollapsed, setThreadPanelCollapsed] = useState(isMobile);
  const [creatingThread, setCreatingThread] = useState(false);
  const [archivingThreadId, setArchivingThreadId] = useState<string | null>(
    null,
  );
  const [agentMode, setAgentMode] = useState<AgentMode>(DEFAULT_AGENT_MODE);
  const [draftRestore, setDraftRestore] = useState<
    ChatInputDraftRestore | undefined
  >();
  const scrollRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = useCallback(() => {
    const node = scrollRef.current;
    if (node) node.scrollTop = node.scrollHeight;
  }, []);

  /* Escape key → collapse thread panel */
  useEffect(() => {
    if (threadPanelCollapsed) return;
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") setThreadPanelCollapsed(true);
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [threadPanelCollapsed]);

  const handleAgentModeChange = useCallback(
    (mode: AgentMode) => {
      if (mode === agentMode) return;
      const draft = abortForModeSwitch();
      if (draft) {
        setDraftRestore({ nonce: Date.now(), text: draft });
      }
      setAgentMode(mode);
    },
    [agentMode, abortForModeSwitch],
  );

  const handleCreateThread = useCallback(async () => {
    abortStreaming();
    setCreatingThread(true);
    try {
      await createNewThread();
      setThreadPanelCollapsed(true);
    } finally {
      setCreatingThread(false);
    }
  }, [abortStreaming, createNewThread]);

  const handleNewChat = useCallback(() => {
    void handleCreateThread();
  }, [handleCreateThread]);

  const handleSelectThread = useCallback(
    (threadId: string) => {
      selectThread(threadId);
      setThreadPanelCollapsed(true);
    },
    [selectThread],
  );

  const handleArchiveThread = useCallback(
    async (threadId: string) => {
      setArchivingThreadId(threadId);
      try {
        await archiveThread(threadId);
      } finally {
        setArchivingThreadId(null);
      }
    },
    [archiveThread],
  );

  const handleSend = useCallback(
    (message: string) => {
      if (!canSend) return;
      abortStreaming();
      void sendMessage(message, agentMode);
    },
    [canSend, abortStreaming, sendMessage, agentMode],
  );

  const handleAdoptApproval = useCallback(
    (_messageIndex: number, approvalId: string) => {
      void resolveApproval(approvalId, "adopt");
    },
    [resolveApproval],
  );

  const handleCancelApproval = useCallback(
    (_messageIndex: number, approvalId: string) => {
      void resolveApproval(approvalId, "cancel");
    },
    [resolveApproval],
  );

  const handleRegenerate = useCallback(
    (messageIndex: number) => {
      void regenerate(messageIndex);
    },
    [regenerate],
  );

  const handleDismissThreadPanel = useCallback(() => {
    setThreadPanelCollapsed(true);
  }, []);

  return {
    /* states */
    threadPanelCollapsed,
    setThreadPanelCollapsed,
    creatingThread,
    archivingThreadId,
    agentMode,
    setAgentMode,
    draftRestore,
    /* refs */
    scrollRef,
    /* callbacks */
    scrollToBottom,
    /* handlers */
    handleAgentModeChange,
    handleCreateThread,
    handleNewChat,
    handleSelectThread,
    handleArchiveThread,
    handleSend,
    handleAdoptApproval,
    handleCancelApproval,
    handleRegenerate,
    handleDismissThreadPanel,
  };
}
