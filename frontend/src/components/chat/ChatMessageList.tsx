import { Link, useNavigate } from "react-router-dom";

import { ApprovalCard } from "@/components/chat/ApprovalCard";
import { EmptyStateV44, CHAT_SCENE, PATHS } from "@/components/ui/EmptyState";
import { CitationChip } from "@/components/chat/CitationChip";
import { CitationPreview } from "@/components/chat/CitationPreview";
import {
  canLinkToCitationPreview,
  formatCitationLabel,
  previewPathForCitation,
  resolveKbIdForCitation,
  type ApprovalState,
  type Citation,
  type CitationLabelMode,
} from "@/lib/chat-api";
import {
  formatMessageTime,
  groupMessagesByDay,
} from "@/lib/message-list-utils";
import { localizeAssistantText } from "@/lib/localize";

export interface UserChatMessage {
  role: "user";
  content: string;
  createdAt: string;
}

export interface AssistantChatMessage {
  role: "assistant";
  content: string;
  citations: Citation[];
  streaming?: boolean;
  expandedIndex: number | null;
  createdAt: string;
  /** G4-4.2 · 编辑模式审批卡状态 */
  approval?: ApprovalState;
}

export type ChatMessage = UserChatMessage | AssistantChatMessage;

interface ChatMessageListProps {
  kbId: string;
  messages: ChatMessage[];
  citationMode?: CitationLabelMode;
  onToggleCitation: (messageIndex: number, citationIndex: number) => void;
  /** G4-4.2 · 审批卡回调 */
  onAdoptApproval?: (messageIndex: number, approvalId: string) => void;
  onCancelApproval?: (messageIndex: number, approvalId: string) => void;
  resolvingApprovalId?: string | null;
  approvalError?: string | null;
  /** 是否已有历史会话：用于区分「首次对话」与「返回用户开新对话」的空态文案 */
  hasThreads?: boolean;
}

export function ChatMessageList({
  kbId,
  messages,
  citationMode = "kb",
  onToggleCitation,
  onAdoptApproval,
  onCancelApproval,
  resolvingApprovalId,
  approvalError,
  hasThreads = false,
}: ChatMessageListProps) {
  const isWorkspace = citationMode === "workspace";
  const navigate = useNavigate();

  if (messages.length === 0) {
    // 有历史会话的返回用户，不应再看到「第一次对话」；用中性文案区分。
    const returningScene = hasThreads
      ? {
          ...CHAT_SCENE,
          eyebrow: "已有对话 · 选一个继续，或开始新的",
          title: (
            <>
              开始一次<em>新的对话</em>
            </>
          ),
          desc: (
            <>
              从左侧选择一个历史会话继续，或直接提问——答案仍会带出处、留在这里。
            </>
          ),
          ctaPrimary: { label: "开始新对话", iconPath: PATHS.message },
        }
      : CHAT_SCENE;

    return (
      <EmptyStateV44
        scene={{
          ...returningScene,
          ctaSecondary: {
            ...CHAT_SCENE.ctaSecondary,
            onClick: () => navigate("/knowledge-bases"),
          },
        }}
      />
    );
  }

  return (
    <>
      {groupMessagesByDay(messages).map((group) => (
        <section key={group.dayKey} aria-label={group.pillLabel}>
          <div className="chat-day-pill">{group.pillLabel}</div>
          {group.items.map(({ message, index: messageIndex }) => {
            if (message.role === "user") {
              return (
                <div key={`user-${messageIndex}`} className="chat-user-msg">
                  {message.content}
                  <time
                    className="chat-msg-time chat-msg-time-user"
                    dateTime={message.createdAt}
                  >
                    {formatMessageTime(message.createdAt)}
                  </time>
                </div>
              );
            }

            const expandedCitation =
              message.expandedIndex != null
                ? message.citations[message.expandedIndex]
                : null;
            const expandedKbId =
              expandedCitation != null
                ? resolveKbIdForCitation(kbId, expandedCitation)
                : null;

            const localizedContent = localizeAssistantText(message.content);

            return (
              <div
                key={`assistant-${messageIndex}`}
                className="chat-assistant-block"
              >
                {message.streaming &&
                  !message.content &&
                  message.citations.length === 0 && (
                    <p className="chat-retrieving text-sm text-muted">
                      {isWorkspace ? "正在检索资料库…" : "正在检索资料库…"}
                    </p>
                  )}
                <div className="chat-assistant-text whitespace-pre-wrap">
                  {localizedContent}
                  {message.streaming && message.content && (
                    <span className="chat-stream-cursor" aria-hidden="true" />
                  )}
                </div>

                {message.citations.length > 0 && (
                  <div className="cite-row">
                    {message.citations.map((citation, citationIndex) => (
                      <CitationChip
                        key={`${citation.chunk_id}-${citationIndex}`}
                        index={citationIndex + 1}
                        citation={citation}
                        mode={citationMode}
                        active={message.expandedIndex === citationIndex}
                        onClick={() =>
                          onToggleCitation(messageIndex, citationIndex)
                        }
                      />
                    ))}
                  </div>
                )}

                {expandedCitation && expandedKbId && (
                  <CitationPreview
                    kbId={expandedKbId}
                    citation={expandedCitation}
                    scopeMode={citationMode}
                  />
                )}

                {message.approval && (
                  <ApprovalCard
                    approval={message.approval}
                    onAdopt={
                      onAdoptApproval
                        ? () =>
                            onAdoptApproval(
                              messageIndex,
                              message.approval!.approval_id,
                            )
                        : undefined
                    }
                    onCancel={
                      onCancelApproval
                        ? () =>
                            onCancelApproval(
                              messageIndex,
                              message.approval!.approval_id,
                            )
                        : undefined
                    }
                    resolving={
                      resolvingApprovalId != null &&
                      resolvingApprovalId === message.approval.approval_id
                    }
                    error={
                      resolvingApprovalId != null &&
                      resolvingApprovalId === message.approval.approval_id
                        ? approvalError ?? null
                        : null
                    }
                  />
                )}

                {!message.streaming &&
                  message.citations.length === 0 &&
                  localizedContent.includes("未找到") && (
                    <p className="mt-3 text-xs text-muted">
                      {isWorkspace
                        ? "当前可见资料库中未找到相关依据（AC-4）"
                        : "当前资料库中未找到相关依据（AC-4）"}
                    </p>
                  )}

                {!message.streaming &&
                  message.citations.length > 0 &&
                  expandedCitation == null && (
                    <p className="mt-2 text-[0.72rem] text-muted">
                      点击引用 chip 展开片段，或前往{" "}
                      {(() => {
                        const first = message.citations[0];
                        const firstKbId = resolveKbIdForCitation(kbId, first);
                        const label = formatCitationLabel(first, citationMode);
                        if (!firstKbId || !canLinkToCitationPreview(first)) {
                          return label;
                        }
                        return (
                          <Link
                            to={previewPathForCitation(firstKbId, first)}
                            className="text-accent hover:underline"
                          >
                            {label}
                          </Link>
                        );
                      })()}
                    </p>
                  )}

                {!message.streaming && (
                  <time
                    className="chat-msg-time"
                    dateTime={message.createdAt}
                  >
                    {formatMessageTime(message.createdAt)}
                  </time>
                )}
              </div>
            );
          })}
        </section>
      ))}
    </>
  );
}
