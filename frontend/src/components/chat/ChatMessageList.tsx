import { Link, useNavigate } from "react-router-dom";
import { useState } from "react";
import { Check, Copy, RefreshCw } from "lucide-react";

import { ApprovalCard } from "@/components/chat/ApprovalCard";
import { EmptyStateV44, CHAT_SCENE } from "@/components/ui/EmptyState";
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
  id?: string;
}

export interface AssistantChatMessage {
  role: "assistant";
  content: string;
  citations: Citation[];
  streaming?: boolean;
  expandedIndex: number | null;
  createdAt: string;
  id?: string;
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
  /** 重新生成回答 */
  onRegenerate?: (messageIndex: number) => void;
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
  onRegenerate,
}: ChatMessageListProps) {
  const isWorkspace = citationMode === "workspace";
  const navigate = useNavigate();
  const [copiedIdx, setCopiedIdx] = useState<number | null>(null);

  async function copyText(text: string, idx: number) {
    try { await navigator.clipboard.writeText(text); } catch { /* noop */ }
    setCopiedIdx(idx);
    setTimeout(() => setCopiedIdx(null), 1800);
  }

  if (messages.length === 0) {
    // 有历史会话的返回用户：简洁空态，不显示插画
    if (hasThreads) {
      return (
        <div className="absolute inset-x-0 bottom-0 top-0 flex items-center justify-center px-7">
          <div className="text-center">
            <p className="font-[var(--serif)] text-[1.125rem] font-semibold text-[var(--text)]">
              选择一个会话继续
            </p>
            <p className="mt-2 max-w-sm text-[0.875rem] leading-relaxed text-[var(--mut)]">
              从左侧选择一个历史会话，或直接输入问题开始新的对话
            </p>
          </div>
        </div>
      );
    }

    // 第一次使用的用户（无历史会话）：保留插画引导
    return (
      <EmptyStateV44
        scene={{
          ...CHAT_SCENE,
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
                <div key={`user-${messageIndex}`} className="chat-user-msg group relative">
                  {message.content}
                  <button
                    className="msg-action-btn absolute right-2 top-2 opacity-0 group-hover:opacity-100 transition-opacity"
                    onClick={(e) => { e.stopPropagation(); void copyText(message.content, messageIndex); }}
                    title="复制"
                    aria-label="复制消息"
                  >
                    {copiedIdx === messageIndex ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
                  </button>
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
                    <p className="chat-retrieving">
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

                {!message.streaming && (
                  <div className="flex items-center justify-end gap-1 mt-2">
                    <button
                      className="msg-action-btn"
                      onClick={() => void copyText(message.content, messageIndex)}
                      title="复制"
                      aria-label="复制回复"
                    >
                      {copiedIdx === messageIndex ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
                    </button>
                    {onRegenerate && (
                      <button
                        className="msg-action-btn"
                        onClick={() => onRegenerate(messageIndex)}
                        title="重新生成"
                        aria-label="重新生成回答"
                      >
                        <RefreshCw className="h-3.5 w-3.5" />
                      </button>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </section>
      ))}
    </>
  );
}
