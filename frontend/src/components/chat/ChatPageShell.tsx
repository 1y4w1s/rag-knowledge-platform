import { type ReactNode, type RefObject } from "react";

import { AgentBudgetChip } from "@/components/chat/AgentBudgetChip";
import { AgentModeSwitcher } from "@/components/chat/AgentModeSwitcher";
import { ChatInput, type ChatInputDraftRestore } from "@/components/chat/ChatInput";
import { ChatLoadingPanel } from "@/components/chat/ChatLoadingPanel";
import { ChatMessageList, type ChatMessage } from "@/components/chat/ChatMessageList";
import { ThreadListPanel } from "@/components/chat/ThreadListPanel";
import { ToolTimeline } from "@/components/chat/ToolTimeline";
import { AlertBanner } from "@/components/ui/AlertBanner";
import { Button } from "@/components/ui/button";
import type { CitationLabelMode } from "@/lib/chat-api";
import type { AgentBudgetState, ToolTimelineStep } from "@/lib/agent-stream";
import type { AgentMode } from "@/lib/agent-mode";
import { FEEDBACK_EVAL_MODE_HINT } from "@/lib/message-feedback";
import type { ChatThread } from "@/lib/thread-api";
import { cn } from "@/lib/utils";
import { suggestThoroughMode } from "@/lib/agent-suggestion";

/* ── Grouped config types (Task J: 28-prop drilling → object) ── */

export interface ThreadPanelConfig {
  collapsed: boolean;
  className: string;
  subtitle?: string;
  onDismiss: () => void;
  threads: ChatThread[];
  activeThreadId: string | null;
  threadsLoading: boolean;
  threadsError: string | null;
  creatingThread: boolean;
  archivingThreadId: string | null;
  onSelectThread: (id: string) => void;
  onCreateThread: () => void;
  onArchiveThread: (id: string) => void;
  onRetryThreads: () => void;
}

export interface AgentConfig {
  mode: AgentMode;
  budget: AgentBudgetState | null;
  onChange: (mode: AgentMode) => void;
  /** G5 · 文档操作模式按钮可见性（仅 Admin/Owner） */
  canUseDocumentWrite?: boolean;
}

export interface ChatStateConfig {
  messages: ChatMessage[];
  historyLoading: boolean;
  historyError: string | null;
  streamError: string | null;
  streaming: boolean;
  toolSteps: ToolTimelineStep[];
  loadMessages: (threadId: string | null) => Promise<void>;
}

export interface MessageListConfig {
  kbId: string;
  citationMode?: CitationLabelMode;
  onRegenerate?: (msgIdx: number) => void;
  onToggleCitation: (msgIdx: number, citIdx: number) => void;
  onAdoptApproval?: (msgIdx: number, approvalId: string) => void;
  onCancelApproval?: (msgIdx: number, approvalId: string) => void;
  resolvingApprovalId: string | null;
  approvalError: string | null;
  /** G5 · 文档操作提案回调 */
  onSubmitProposal?: (messageIndex: number) => void;
  onCancelProposal?: (messageIndex: number) => void;
  submittingProposal?: boolean;
  proposalError?: string | null;
  /** G5 · 文档名歧义澄清回调 */
  onClarify?: (messageIndex: number, documentId: string, operation: "delete" | "restore") => void;
  clarifying?: boolean;
  clarifyError?: string | null;
  /** NW-10 I-2 */
  evalMode?: boolean;
}

export interface InputConfig {
  disabled: boolean;
  placeholder?: string;
  draftRestore: ChatInputDraftRestore | undefined;
  onSend: (msg: string) => void;
}

interface ChatPageShellProps {
  /** Thread list panel state & handlers. */
  threadPanel: ThreadPanelConfig;
  /** Toolbar slot (AskPage inline vs ChatToolbar component). */
  toolbar: ReactNode;
  /** Agent mode selector + budget display. */
  agentConfig: AgentConfig;
  /** Chat messages & streaming state. */
  chatState: ChatStateConfig;
  /** ChatMessageList config (kbId, citation, approval). */
  messageListConfig: MessageListConfig;
  /** ChatInput config. */
  inputConfig: InputConfig;
  /** Scroll ref (owned by caller). */
  scrollRef: RefObject<HTMLDivElement | null>;
  /** Extra content below agent-mode-bar, e.g. AskPage banners. */
  children?: ReactNode;
  /**
   * Override the entire chat-inner content.
   * AskPage uses this to show EmptyStateV44 when hasVisibleKbs is false.
   */
  chatInnerOverride?: ReactNode;
}

/**
 * G2-2.1 · AskPage / ChatPage 共享布局壳。
 *
 * 组装 ThreadListPanel + AgentModeBar + ChatMessageList + ChatInput，
 * 通过 `toolbar` slot 和 `children` slot 承载两页不同的内容。
 */
export function ChatPageShell({
  threadPanel: {
    collapsed: threadPanelCollapsed,
    className: threadPanelClassName,
    subtitle: threadPanelSubtitle,
    onDismiss: onDismissThreadPanel,
    threads,
    activeThreadId,
    threadsLoading,
    threadsError,
    creatingThread,
    archivingThreadId,
    onSelectThread,
    onCreateThread,
    onArchiveThread,
    onRetryThreads,
  },
  toolbar,
  agentConfig: {
    mode: agentMode,
    budget: agentBudget,
    onChange: onAgentModeChange,
    canUseDocumentWrite,
  },
  chatState: {
    messages,
    historyLoading,
    historyError,
    streamError,
    streaming,
    toolSteps,
    loadMessages,
  },
  messageListConfig: {
    kbId: chatMessageListKbId,
    citationMode,
    onToggleCitation,
    onAdoptApproval,
    onCancelApproval,
    onRegenerate,
    resolvingApprovalId,
    approvalError,
    onSubmitProposal,
    onCancelProposal,
    submittingProposal,
    proposalError,
    onClarify,
    clarifying,
    clarifyError,
    evalMode = false,
  },
  inputConfig: {
    disabled: chatInputDisabled,
    placeholder: chatInputPlaceholder,
    draftRestore,
    onSend: onSendMessage,
  },
  scrollRef,
  children,
  chatInnerOverride,
}: ChatPageShellProps) {
  return (
    // Full-width container — uses full-bleed utility (DESIGN.md §2, S2 fix)
    <div className="full-bleed">
      <div className="ask-chat-layout">
        <div
          className={cn(
            "thread-list-drawer-backdrop",
            !threadPanelCollapsed && "open",
          )}
          aria-hidden={threadPanelCollapsed}
          onClick={onDismissThreadPanel}
        />
        <ThreadListPanel
          className={cn(
            threadPanelClassName,
            threadPanelCollapsed && "thread-list-panel-collapsed",
          )}
          threads={threads}
          activeThreadId={activeThreadId}
          loading={threadsLoading}
          error={threadsError}
          creating={creatingThread}
          archivingThreadId={archivingThreadId}
          onSelectThread={onSelectThread}
          onCreateThread={onCreateThread}
          onArchiveThread={onArchiveThread}
          onRetry={onRetryThreads}
          subtitle={threadPanelSubtitle}
        />

        <div className="ask-chat-main">
          {toolbar}

          <div className="agent-mode-bar">
            <AgentModeSwitcher
              value={agentMode}
              onChange={onAgentModeChange}
              showDocumentWrite={canUseDocumentWrite}
            />
            <AgentBudgetChip mode={agentMode} budget={agentBudget} />
            {agentMode === "fast" && messages.length > 0 && (() => {
              const lastUserMsg = [...messages].reverse().find(m => m.role === "user");
              if (lastUserMsg && suggestThoroughMode(lastUserMsg.content)) {
                return (
                  <button
                    type="button"
                    className="ml-2 rounded-full border border-[var(--accent)]/30 bg-[var(--accent)]/5 px-2.5 py-0.5 text-[0.68rem] text-[var(--accent)] transition-colors hover:bg-[var(--accent)]/15"
                    onClick={() => onAgentModeChange("thorough")}
                    data-testid="suggest-thorough-chip"
                  >
                    ✦ 推荐精准
                  </button>
                );
              }
              return null;
            })()}
          </div>

          {evalMode ? (
            <p
              className="px-4 pb-1 text-[0.72rem] text-[var(--mut)]"
              data-testid="feedback-eval-mode-hint"
            >
              {FEEDBACK_EVAL_MODE_HINT}
            </p>
          ) : null}

          {children}

          <div ref={scrollRef} className="chat-scroll">
            <div className="chat-inner">
              {chatInnerOverride ?? (
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
                        kbId={chatMessageListKbId}
                        messages={messages}
                        citationMode={citationMode}
                        onToggleCitation={onToggleCitation}
                        onAdoptApproval={onAdoptApproval}
                        onCancelApproval={onCancelApproval}
                        onRegenerate={onRegenerate}
                        resolvingApprovalId={resolvingApprovalId}
                        approvalError={approvalError}
                        onSubmitProposal={onSubmitProposal}
                        onCancelProposal={onCancelProposal}
                        submittingProposal={submittingProposal}
                        proposalError={proposalError}
                        onClarify={onClarify}
                        clarifying={clarifying}
                        clarifyError={clarifyError}
                        hasThreads={threads.length > 0}
                        evalMode={evalMode}
                      />
                    </>
                  )}
                </>
              )}
            </div>
          </div>

          <ChatInput
            disabled={chatInputDisabled}
            placeholder={chatInputPlaceholder}
            draftRestore={draftRestore}
            onSend={onSendMessage}
          />
        </div>
      </div>
    </div>
  );
}
