import { History, MessageSquarePlus } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import { AgentBudgetChip } from "@/components/chat/AgentBudgetChip";
import { ToolTimeline } from "@/components/chat/ToolTimeline";
import { AgentModeSwitcher } from "@/components/chat/AgentModeSwitcher";
import { EmptyStateV44, ASK_SCENE } from "@/components/ui/EmptyState";
import { ChatInput, type ChatInputDraftRestore } from "@/components/chat/ChatInput";
import { ChatLoadingPanel } from "@/components/chat/ChatLoadingPanel";
import { ChatMessageList } from "@/components/chat/ChatMessageList";
import { ChatPageShellSkeleton } from "@/components/chat/ChatPageShellSkeleton";
import { ThreadListPanel } from "@/components/chat/ThreadListPanel";
import { UnassignedDepartmentBanner } from "@/components/organization/UnassignedDepartmentBanner";
import { AlertBanner } from "@/components/ui/AlertBanner";
import { Button } from "@/components/ui/button";
import { DEFAULT_AGENT_MODE, type AgentMode } from "@/lib/agent-mode";
import { useAuth } from "@/lib/auth-context";
import { useDepartment } from "@/lib/department-context";
import { formatOrgLabel } from "@/lib/format-org-label";
import { fetchKnowledgeBases } from "@/lib/knowledge-base-api";
import { canUseTeamBusiness } from "@/lib/org-permissions";
import { useShellBreadcrumb } from "@/lib/shell-breadcrumb";
import type { ThreadContext } from "@/lib/thread-api";
import { useThreadSession } from "@/lib/use-thread-session";
import { cn } from "@/lib/utils";
import { useMediaQuery } from "@/lib/use-media-query";
import { useOrganizationName } from "@/lib/use-organization-name";
import { useWorkspace } from "@/lib/workspace-context";

function AskPageSkeleton() {
  return <ChatPageShellSkeleton />;
}

export function AskPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const { workspace, generation, getGeneration, isTeamWorkspace } =
    useWorkspace();
  const {
    departmentId,
    generation: departmentGeneration,
    getGeneration: getDepartmentGeneration,
  } = useDepartment();
  const { setOverride } = useShellBreadcrumb();
  const { name: orgName, loading: orgNameLoading } = useOrganizationName();

  const teamBusinessAllowed = canUseTeamBusiness(user, workspace);
  const [kbLoading, setKbLoading] = useState(true);
  const [hasVisibleKbs, setHasVisibleKbs] = useState(true);
  const [kbCheckError, setKbCheckError] = useState<string | null>(null);
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

  const scope = useMemo(
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
    () => ({ kind: "workspace", scope }),
    [scope],
  );

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

  const spaceLabel = isTeamWorkspace
    ? orgNameLoading
      ? "…"
      : formatOrgLabel(orgName || "团队")
    : "我的空间";

  const scrollToBottom = useCallback(() => {
    const node = scrollRef.current;
    if (node) node.scrollTop = node.scrollHeight;
  }, []);

  const checkVisibleKbs = useCallback(async () => {
    setKbLoading(true);
    setKbCheckError(null);
    try {
      const list = await fetchKnowledgeBases(scope);
      if (list === null) return;
      setHasVisibleKbs(list.length > 0);
    } catch (err) {
      setHasVisibleKbs(false);
      setKbCheckError(
        err instanceof Error ? err.message : "无法加载资料库列表",
      );
    } finally {
      setKbLoading(false);
    }
  }, [scope]);

  useEffect(() => {
    document.title = "知岸 · 对话";
    setOverride(<>对话</>);
    return () => {
      setOverride(null);
      document.title = "知岸";
      abortStreaming();
    };
  }, [setOverride, abortStreaming]);

  useEffect(() => {
    void checkVisibleKbs();
  }, [checkVisibleKbs]);

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
    if (kbLoading || !teamBusinessAllowed || !hasVisibleKbs) return;

    const q = searchParams.get("q")?.trim();
    if (!q) return;

    const consumeKey = `${workspace}:${departmentId ?? ""}:${q}`;
    if (consumedQuickQRef.current === consumeKey) return;
    consumedQuickQRef.current = consumeKey;

    const nextParams = new URLSearchParams(searchParams);
    nextParams.delete("q");
    setSearchParams(nextParams, { replace: true });

    abortStreaming();
    void sendMessage(q, agentMode);
  }, [
    kbLoading,
    teamBusinessAllowed,
    hasVisibleKbs,
    searchParams,
    setSearchParams,
    sendMessage,
    abortStreaming,
    agentMode,
    workspace,
    departmentId,
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
    if (!teamBusinessAllowed || !hasVisibleKbs) return;
    abortStreaming();
    void sendMessage(message, agentMode);
  }

  function handleAdoptApproval(_messageIndex: number, approvalId: string) {
    void resolveApproval(approvalId, "adopt");
  }

  function handleCancelApproval(_messageIndex: number, approvalId: string) {
    void resolveApproval(approvalId, "cancel");
  }

  if (kbLoading) {
    return <AskPageSkeleton />;
  }

  return (
    <div className="-m-6 flex h-[calc(100vh-3.25rem)] flex-col overflow-hidden">
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
            "ask-thread-panel",
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
        />

        <div className="ask-chat-main">
          <div className="chat-toolbar">
            <button
              type="button"
              className={cn(
                "thread-history-toggle",
                !threadPanelCollapsed && "thread-history-toggle-on",
              )}
              aria-expanded={!threadPanelCollapsed}
              aria-controls="thread-list-panel"
              onClick={() => setThreadPanelCollapsed((c) => !c)}
              data-testid="thread-history-toggle"
            >
              <History className="h-3.5 w-3.5" aria-hidden />
              历史
            </button>
            <span className="chat-toolbar-pill">引用溯源</span>
            <span className="min-w-0 truncate font-serif text-[0.875rem] font-semibold text-foreground">
              对话
            </span>
            <span className="hidden text-[0.75rem] text-muted sm:inline">
              · 当前空间：{spaceLabel}
            </span>
            <span className="flex-1" />
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={handleNewChat}
              disabled={creatingThread}
              data-testid="toolbar-new-chat-btn"
              className="gap-1 px-2 sm:px-3"
            >
              <MessageSquarePlus className="h-4 w-4 sm:hidden" aria-hidden />
              <span className="hidden sm:inline">
                {creatingThread ? "创建中…" : "+ 新建对话"}
              </span>
              <span className="sm:hidden">
                {creatingThread ? "…" : "新建"}
              </span>
            </Button>
          </div>

          <div className="agent-mode-bar">
            <AgentModeSwitcher
              value={agentMode}
              onChange={handleAgentModeChange}
            />
            <AgentBudgetChip mode={agentMode} budget={agentBudget} />
          </div>

          {!teamBusinessAllowed && (
            <div className="px-6 pt-4">
              <UnassignedDepartmentBanner />
            </div>
          )}

          {kbCheckError && (
            <div className="px-6 pt-4">
              <AlertBanner
                action={
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={checkVisibleKbs}
                  >
                    重试
                  </Button>
                }
              >
                {kbCheckError}
              </AlertBanner>
            </div>
          )}

          <div ref={scrollRef} className="chat-scroll">
            <div className="chat-inner">
              {!hasVisibleKbs && !kbCheckError ? (
                <EmptyStateV44
                  scene={{
                    ...ASK_SCENE,
                    ctaPrimary: {
                      ...ASK_SCENE.ctaPrimary,
                      onClick: () => navigate("/knowledge-bases"),
                    },
                    ctaSecondary: {
                      ...ASK_SCENE.ctaSecondary,
                      onClick: () => navigate("/knowledge-bases"),
                    },
                  }}
                />
              ) : (
                <>
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
                        kbId=""
                        messages={messages}
                        citationMode="workspace"
                        onToggleCitation={toggleCitation}
                        onAdoptApproval={handleAdoptApproval}
                        onCancelApproval={handleCancelApproval}
                        resolvingApprovalId={resolvingApprovalId}
                        approvalError={approvalError}
                        hasThreads={threads.length > 0}
                      />
                    </>
                  )}
                </>
              )}
            </div>
          </div>

          <ChatInput
            disabled={streaming || !teamBusinessAllowed || !hasVisibleKbs}
            placeholder={
              !teamBusinessAllowed
                ? "分配部门后即可开始对话"
                : !hasVisibleKbs
                  ? "请先创建资料库并上传文档"
                  : "输入问题，在全部资料库中检索…"
            }
            draftRestore={draftRestore}
            onSend={handleSend}
          />
        </div>
      </div>
    </div>
  );
}
