import { useState } from "react";
import { Check, ChevronDown, ChevronUp, FileText, X } from "lucide-react";

import { CitationChip } from "@/components/chat/CitationChip";
import type { ApprovalState } from "@/lib/chat-api";
import { cn } from "@/lib/utils";

interface ApprovalCardProps {
  approval: ApprovalState;
  onAdopt?: () => void;
  onCancel?: () => void;
  resolving?: boolean;
  error?: string | null;
  className?: string;
}

export function ApprovalCard({
  approval,
  onAdopt,
  onCancel,
  resolving = false,
  error = null,
  className,
}: ApprovalCardProps) {
  const [previewOpen, setPreviewOpen] = useState(false);
  const isTerminal = approval.status !== "pending";

  return (
    <div
      className={cn(
        "approval-card",
        isTerminal && "approval-card-terminal",
        className,
      )}
      data-testid="approval-card"
    >
      {/* Header */}
      <div className="approval-card-header">
        <div className="flex items-center gap-2 min-w-0">
          <FileText className="h-4 w-4 shrink-0 text-muted" />
          <span className="approval-card-filename truncate">
            {approval.filename}
          </span>
        </div>
        {isTerminal && (
          <span
            className={cn(
              "approval-card-status",
              approval.status === "adopted" && "approval-card-status-adopted",
              approval.status === "cancelled" && "approval-card-status-cancelled",
            )}
          >
            {approval.status === "adopted" ? "已采纳" : "已取消"}
          </span>
        )}
      </div>

      {/* Draft preview (collapsible) */}
      {approval.draft_preview && (
        <div className="approval-card-preview">
          <button
            type="button"
            className="approval-card-preview-toggle"
            onClick={() => setPreviewOpen((v) => !v)}
          >
            <span>草稿预览</span>
            {previewOpen ? (
              <ChevronUp className="h-3.5 w-3.5" />
            ) : (
              <ChevronDown className="h-3.5 w-3.5" />
            )}
          </button>
          {previewOpen && (
            <pre className="approval-card-preview-body">
              {approval.draft_preview}
            </pre>
          )}
        </div>
      )}

      {/* Citation chips */}
      {approval.citations.length > 0 && (
        <div className="approval-card-citations">
          {approval.citations.map((citation, index) => (
            <CitationChip
              key={`${citation.chunk_id}-${index}`}
              index={index + 1}
              citation={citation}
              mode="kb"
              active={false}
              onClick={() => {}}
            />
          ))}
        </div>
      )}

      {/* Actions */}
      {!isTerminal && (
        <div className="approval-card-actions">
          {approval.can_adopt ? (
            <>
              <button
                type="button"
                className="approval-card-btn approval-card-btn-adopt"
                disabled={resolving}
                onClick={onAdopt}
                data-testid="approval-btn-adopt"
              >
                <Check className="h-3.5 w-3.5" />
                采纳
              </button>
              <button
                type="button"
                className="approval-card-btn approval-card-btn-cancel"
                disabled={resolving}
                onClick={onCancel}
                data-testid="approval-btn-cancel"
              >
                <X className="h-3.5 w-3.5" />
                取消
              </button>
            </>
          ) : (
            <p className="approval-card-no-permission">
              你对该知识库无写入权限，需管理员采纳
            </p>
          )}
          {resolving && (
            <span className="approval-card-resolving">处理中…</span>
          )}
        </div>
      )}

      {/* Error */}
      {error && (
        <p className="approval-card-error" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
