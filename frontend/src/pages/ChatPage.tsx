import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";

import { ChatPageShell } from "@/components/chat/ChatPageShell";
import { ChatPageShellSkeleton } from "@/components/chat/ChatPageShellSkeleton";
import { ChatToolbar } from "@/components/chat/ChatToolbar";
import { AlertBanner } from "@/components/ui/AlertBanner";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/auth-context";
import {
  fetchKnowledgeBase,
  fetchKnowledgeBases,
  withCurrentKnowledgeBase,
  type KnowledgeBase,
} from "@/lib/knowledge-base-api";
import { buildChatBreadcrumb } from "@/lib/breadcrumb-links";
import { canUseTeamBusiness } from "@/lib/org-permissions";
import { persistRecentKbId } from "@/lib/use-sidebar-chat-kb-id";
import { useDepartment } from "@/lib/department-context";
import { useWorkspace } from "@/lib/workspace-context";
import { useShellBreadcrumb } from "@/lib/shell-breadcrumb";
import type { ThreadContext } from "@/lib/thread-api";
import { useThreadSession } from "@/lib/use-thread-session";
import { useChatPageHandlers } from "@/lib/use-chat-page-handlers";

function DetailSkeleton() {
  return (
    <ChatPageShellSkeleton className="h-[calc(100vh-3.25rem)] overflow-hidden" />
  );
}

export function ChatPage() {
  const { id } = useParams<{ id: string }>();
  const [searchParams, setSearchParams] = useSearchParams();
  const { user } = useAuth();
  const { workspace, isTeamWorkspace, generation, getGeneration } =
    useWorkspace();
  const {
    departmentId,
    generation: departmentGeneration,
    getGeneration: getDepartmentGeneration,
  } = useDepartment();
  const { setOverride } = useShellBreadcrumb();
  const teamBusinessAllowed = canUseTeamBusiness(user, workspace);

  const chatScope = useMemo(
    () => ({
      workspace,
      departmentId: isTeamWorkspace ? departmentId : null,
    }),
    [workspace, departmentId, isTeamWorkspace],
  );

  const kbListScope = useMemo(
    () => ({
      workspace,
      departmentId: isTeamWorkspace ? departmentId : null,
      expectedGen: generation,
      getCurrentGeneration: getGeneration,
      expectedDepartmentGen: departmentGeneration,
      getCurrentDepartmentGeneration: getDepartmentGeneration,
    }),
    [
      workspace,
      departmentId,
      isTeamWorkspace,
      generation,
      getGeneration,
      departmentGeneration,
      getDepartmentGeneration,
    ],
  );

  const threadContext = useMemo<ThreadContext>(
    () => ({
      kind: "knowledge_base",
      kbId: id ?? "",
      scope: chatScope,
    }),
    [id, chatScope],
  );

  const [kb, setKb] = useState<KnowledgeBase | null>(null);
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBase[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const consumedQuickQRef = useRef<string | null>(null);
  const loadIdRef = useRef(0);

  const {
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
    createNewThread,
    archiveThread,
    toggleCitation,
    resolveApproval,
    sendMessage,
    abortStreaming,
    abortForModeSwitch,
  } = useThreadSession(threadContext);

  const {
    threadPanelCollapsed,
    setThreadPanelCollapsed,
    creatingThread,
    archivingThreadId,
    agentMode,
    draftRestore,
    scrollRef,
    scrollToBottom,
    handleAgentModeChange,
    handleCreateThread,
    handleNewChat,
    handleSelectThread,
    handleArchiveThread,
    handleSend,
    handleAdoptApproval,
    handleCancelApproval,
    handleDismissThreadPanel,
  } = useChatPageHandlers({
    abortStreaming,
    abortForModeSwitch,
    createNewThread,
    selectThread,
    archiveThread,
    sendMessage,
    resolveApproval,
    canSend: teamBusinessAllowed,
  });

  const loadPage = useCallback(async () => {
    if (!id) return;
    const loadId = ++loadIdRef.current;
    setLoading(true);
    setError(null);
    try {
      const [kbData, kbList] = await Promise.all([
        fetchKnowledgeBase(id),
        fetchKnowledgeBases(kbListScope),
      ]);
      if (loadId !== loadIdRef.current) return;
      if (kbList === null) return;
      setKb(kbData);
      setKnowledgeBases(withCurrentKnowledgeBase(kbList, kbData));
      persistRecentKbId(id, workspace);
      document.title = `睿阁 · ${kbData.name}`;
      setOverride(buildChatBreadcrumb(id, kbData.name));
    } catch (err) {
      if (loadId !== loadIdRef.current) return;
      setKb(null);
      setError(err instanceof Error ? err.message : "加载失败");
    } finally {
      if (loadId === loadIdRef.current) {
        setLoading(false);
      }
    }
  }, [id, workspace, kbListScope, setOverride]);

  useEffect(() => {
    void loadPage();
    consumedQuickQRef.current = null;
    return () => {
      loadIdRef.current += 1;
      setOverride(null);
      document.title = "睿阁";
      abortStreaming();
    };
  }, [loadPage, setOverride, abortStreaming]);

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  useEffect(() => {
    if (loading || !kb || !id || !teamBusinessAllowed) return;

    const q = searchParams.get("q")?.trim();
    if (!q) return;

    const consumeKey = `${id}:${q}`;
    if (consumedQuickQRef.current === consumeKey) return;
    consumedQuickQRef.current = consumeKey;

    const nextParams = new URLSearchParams(searchParams);
    nextParams.delete("q");
    setSearchParams(nextParams, { replace: true });

    abortStreaming();
    void sendMessage(q, agentMode);
  }, [
    loading,
    kb,
    id,
    searchParams,
    setSearchParams,
    sendMessage,
    abortStreaming,
    agentMode,
    teamBusinessAllowed,
  ]);

  if (!id) {
    return (
      <AlertBanner className="rounded-lg">无效的资料库地址</AlertBanner>
    );
  }

  if (loading) {
    return <DetailSkeleton />;
  }

  if (error || !kb) {
    return (
      <AlertBanner
        action={
          <Button type="button" variant="outline" size="sm" onClick={loadPage}>
            重试
          </Button>
        }
      >
        {error ?? "资料库不存在"}
      </AlertBanner>
    );
  }

  return (
    <ChatPageShell
      threadPanel={{
        collapsed: threadPanelCollapsed,
        className: "chat-thread-panel",
        subtitle: "本资料库 · 仅自己可见",
        onDismiss: handleDismissThreadPanel,
        threads,
        activeThreadId,
        threadsLoading,
        threadsError,
        creatingThread,
        archivingThreadId,
        onSelectThread: handleSelectThread,
        onCreateThread: handleCreateThread,
        onArchiveThread: handleArchiveThread,
        onRetryThreads: () => void loadThreads(),
      }}
      toolbar={
        <ChatToolbar
          kbId={id}
          kbName={kb.name}
          knowledgeBases={knowledgeBases}
          onNewChat={handleNewChat}
          creatingThread={creatingThread}
          threadPanelCollapsed={threadPanelCollapsed}
          onToggleThreadPanel={() => setThreadPanelCollapsed((c) => !c)}
        />
      }
      agentConfig={{
        mode: agentMode,
        budget: agentBudget,
        onChange: handleAgentModeChange,
      }}
      chatState={{
        messages,
        historyLoading,
        historyError,
        streamError,
        streaming,
        toolSteps,
        loadMessages,
      }}
      messageListConfig={{
        kbId: id,
        onToggleCitation: toggleCitation,
        onAdoptApproval: handleAdoptApproval,
        onCancelApproval: handleCancelApproval,
        resolvingApprovalId,
        approvalError,
      }}
      inputConfig={{
        disabled: streaming || !teamBusinessAllowed,
        placeholder: teamBusinessAllowed ? undefined : "分配部门后即可开始对话",
        draftRestore,
        onSend: handleSend,
      }}
      scrollRef={scrollRef}
    />
  );
}
