import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";

import { AgentBudgetChip } from "@/components/chat/AgentBudgetChip";
import { ToolTimeline } from "@/components/chat/ToolTimeline";
import { AgentModeSwitcher } from "@/components/chat/AgentModeSwitcher";
import { ChatInput, type ChatInputDraftRestore } from "@/components/chat/ChatInput";
import { ChatLoadingPanel } from "@/components/chat/ChatLoadingPanel";
import { ChatMessageList } from "@/components/chat/ChatMessageList";
import { ChatPageShellSkeleton } from "@/components/chat/ChatPageShellSkeleton";
import { ChatToolbar } from "@/components/chat/ChatToolbar";
import { ThreadListPanel } from "@/components/chat/ThreadListPanel";
import { AlertBanner } from "@/components/ui/AlertBanner";
import { Button } from "@/components/ui/button";
import { DEFAULT_AGENT_MODE, type AgentMode } from "@/lib/agent-mode";
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
import { useMediaQuery } from "@/lib/use-media-query";
import { cn } from "@/lib/utils";

const CHAT_SHELL =
  "-m-6 flex h-[calc(100vh-3.25rem)] flex-col overflow-hidden";

function DetailSkeleton() {
  return (
    <ChatPageShellSkeleton className="h-[calc(100vh-3.25rem)] overflow-hidden" />
  );
}

export function ChatPage() {
  const { id } = useParams<{ id: string }>();
  const [searchParams, setSearchParams] = useSearchParams();
  const { user } = useAuth();
  const { workspace, isTeamWorkspace, generation, getGeneration } = useWorkspace();
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

  const scrollToBottom = useCallback(() => {
    const node = scrollRef.current;
    if (node) node.scrollTop = node.scrollHeight;
  }, []);

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
      document.title = `知岸 · ${kbData.name}`;
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
      document.title = "知岸";
      abortStreaming();
    };
  }, [loadPage, setOverride, abortStreaming]);

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  useEffect(() => {
    if (threadPanelCollapsed) return;
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") setThreadPanelCollapsed(true);
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [threadPanelCollapsed]);

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

  function handleAgentModeChange(mode: AgentMode) {
    if (mode === agentMode) return;
    const draft = abortForModeSwitch();
    if (draft) {
      setDraftRestore({ nonce: Date.now(), text: draft });
    }
    setAgentMode(mode);
  }

  async function handleCreateThread() {
    abortStreaming();
    setCreatingThread(true);
    try {
      await createNewThread();
      setThreadPanelCollapsed(true);
    } finally {
      setCreatingThread(false);
    }
  }

  function handleNewChat() {
    void handleCreateThread();
  }

  function handleSelectThread(threadId: string) {
    selectThread(threadId);
    setThreadPanelCollapsed(true);
  }

  async function handleArchiveThread(threadId: string) {
    setArchivingThreadId(threadId);
    try {
      await archiveThread(threadId);
    } finally {
      setArchivingThreadId(null);
    }
  }

  function handleSend(message: string) {
    if (!teamBusinessAllowed) return;
    abortStreaming();
    void sendMessage(message, agentMode);
  }

  function handleAdoptApproval(_messageIndex: number, approvalId: string) {
    void resolveApproval(approvalId, "adopt");
  }

  function handleCancelApproval(_messageIndex: number, approvalId: string) {
    void resolveApproval(approvalId, "cancel");
  }

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
    <div className={CHAT_SHELL}>
      <div className="ask-chat-layout">
        <div
          className={cn(
            "thread-list-drawer-backdrop",
            !threadPanelCollapsed && "open",
          )}
          aria-hidden={threadPanelCollapsed}
          onClick={() => setThreadPanelCollapsed(true)}
        />
        <ThreadListPanel
          className={cn(
            "chat-thread-panel",
            threadPanelCollapsed && "thread-list-panel-collapsed",
          )}
          threads={threads}
          activeThreadId={activeThreadId}
          loading={threadsLoading}
          error={threadsError}
          creating={creatingThread}
          archivingThreadId={archivingThreadId}
          onSelectThread={handleSelectThread}
          onCreateThread={handleCreateThread}
          onArchiveThread={handleArchiveThread}
          onRetry={() => void loadThreads()}
          subtitle="本资料库 · 仅自己可见"
        />

        <div className="ask-chat-main">
          <ChatToolbar
            kbId={id}
            kbName={kb.name}
            knowledgeBases={knowledgeBases}
            onNewChat={handleNewChat}
            creatingThread={creatingThread}
            threadPanelCollapsed={threadPanelCollapsed}
            onToggleThreadPanel={() => setThreadPanelCollapsed((c) => !c)}
          />

          <div className="agent-mode-bar">
            <AgentModeSwitcher
              value={agentMode}
              onChange={handleAgentModeChange}
            />
            <AgentBudgetChip mode={agentMode} budget={agentBudget} />
          </div>

          <div ref={scrollRef} className="chat-scroll">
            <div className="chat-inner">
              {historyError && (
                <AlertBanner
                  className="mb-4"
                  action={
                    activeThreadId ? (
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={() => void loadMessages(activeThreadId)}
                      >
                        重试
                      </Button>
                    ) : undefined
                  }
                >
                  {historyError}
                </AlertBanner>
              )}
              {streamError && (
                <AlertBanner className="mb-4">{streamError}</AlertBanner>
              )}
              {historyLoading ? (
                <ChatLoadingPanel
                  label="加载对话历史…"
                  testId="chat-history-loading"
                />
              ) : (
                <>
                  {agentMode === "thorough" && toolSteps.length > 0 ? (
                    <ToolTimeline
                      steps={toolSteps}
                      defaultOpen={streaming}
                      className="mb-4"
                    />
                  ) : null}
                  <ChatMessageList
                    kbId={id}
                    messages={messages}
                    onToggleCitation={toggleCitation}
                    onAdoptApproval={handleAdoptApproval}
                    onCancelApproval={handleCancelApproval}
                    resolvingApprovalId={resolvingApprovalId}
                    approvalError={approvalError}
                    hasThreads={threads.length > 0}
                  />
                </>
              )}
            </div>
          </div>

          <ChatInput
            disabled={streaming || !teamBusinessAllowed}
            placeholder={
              teamBusinessAllowed ? undefined : "分配部门后即可开始对话"
            }
            draftRestore={draftRestore}
            onSend={handleSend}
          />
        </div>
      </div>
    </div>
  );
}
