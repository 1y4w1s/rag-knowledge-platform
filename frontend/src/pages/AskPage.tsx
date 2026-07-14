import { History, MessageSquarePlus } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import { ChatPageShell } from "@/components/chat/ChatPageShell";
import { ChatPageShellSkeleton } from "@/components/chat/ChatPageShellSkeleton";
import { UnassignedDepartmentBanner } from "@/components/organization/UnassignedDepartmentBanner";
import { AlertBanner } from "@/components/ui/AlertBanner";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/auth-context";
import { useDepartment } from "@/lib/department-context";
import { formatOrgLabel } from "@/lib/format-org-label";
import { fetchKnowledgeBases } from "@/lib/knowledge-base-api";
import { canUseTeamBusiness } from "@/lib/org-permissions";
import { useShellBreadcrumb } from "@/lib/shell-breadcrumb";
import type { ThreadContext } from "@/lib/thread-api";
import { useThreadSession } from "@/lib/use-thread-session";
import { useOrganizationName } from "@/lib/use-organization-name";
import { useWorkspace } from "@/lib/workspace-context";
import { useChatPageHandlers } from "@/lib/use-chat-page-handlers";
import { EmptyStateV44, ASK_SCENE } from "@/components/ui/EmptyState";
import { cn } from "@/lib/utils";

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
    canSend: teamBusinessAllowed && hasVisibleKbs,
  });

  const spaceLabel = isTeamWorkspace
    ? orgNameLoading
      ? "…"
      : formatOrgLabel(orgName || "团队")
    : "我的空间";

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

  if (kbLoading) {
    return <AskPageSkeleton />;
  }

  const showEmptyState = !hasVisibleKbs && !kbCheckError;

  return (
    <ChatPageShell
      threadPanel={{
        collapsed: threadPanelCollapsed,
        className: "ask-thread-panel",
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
        kbId: "",
        citationMode: "workspace",
        onToggleCitation: toggleCitation,
        onAdoptApproval: handleAdoptApproval,
        onCancelApproval: handleCancelApproval,
        resolvingApprovalId,
        approvalError,
      }}
      inputConfig={{
        disabled: streaming || !teamBusinessAllowed || !hasVisibleKbs,
        placeholder: !teamBusinessAllowed
          ? "分配部门后即可开始对话"
          : !hasVisibleKbs
            ? "请先创建资料库并上传文档"
            : "输入问题，在全部资料库中检索…",
        draftRestore,
        onSend: handleSend,
      }}
      scrollRef={scrollRef}
      chatInnerOverride={
        showEmptyState ? (
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
        ) : undefined
      }
    >
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
    </ChatPageShell>
  );
}
