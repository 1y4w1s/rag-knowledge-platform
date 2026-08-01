import { useState } from "react";
import { AlertTriangle, FileText, Trash2, Undo2 } from "lucide-react";

import type { ProposalState } from "@/lib/chat-api";
import { cn } from "@/lib/utils";

interface ProposalPreviewCardProps {
  proposal: ProposalState;
  onSubmit?: () => void;
  onCancel?: () => void;
  submitting?: boolean;
  error?: string | null;
  className?: string;
}

const OPERATION_META: Record<
  ProposalState["operation"],
  { label: string; icon: typeof Trash2; tone: string }
> = {
  delete: {
    label: "删除文档",
    icon: Trash2,
    tone: "text-[var(--status-err-text)]",
  },
  restore: {
    label: "恢复文档",
    icon: Undo2,
    tone: "text-[var(--status-ok-text)]",
  },
};

/**
 * G5 · 文档操作提案预览卡（先提案后确认提交 · 比 FAQ 多一轮确认）。
 *
 * - 展示操作（删除/恢复）、目标文档、影响说明与冲突预警；
 * - 写权限（can_adopt）不足时仅提示，不显示提交按钮（须管理员操作）；
 * - 用户确认 → onSubmit → POST /agent/document-write/submit 建 pending；
 *   取消 → onCancel 清除提案。
 */
export function ProposalPreviewCard({
  proposal,
  onSubmit,
  onCancel,
  submitting = false,
  error = null,
  className,
}: ProposalPreviewCardProps) {
  const meta = OPERATION_META[proposal.operation];
  const Icon = meta.icon;
  const isTerminal = !proposal.can_adopt;
  // B 路径（fast 模式自动识别）需两次点击确认（情景 4 · 多重确认用户轮）
  const doubleConfirm = proposal.double_confirm === true;
  const [armed, setArmed] = useState(false);

  return (
    <div
      className={cn("approval-card", className)}
      data-testid="proposal-preview-card"
    >
      <div className="approval-card-header">
        <div className="flex items-center gap-2 min-w-0">
          <Icon className={cn("h-4 w-4 shrink-0", meta.tone)} />
          <span className="approval-card-filename truncate">
            {proposal.filename}
          </span>
          <span
            className={cn(
              "shrink-0 rounded-full bg-[color-mix(in_srgb,var(--surf)_70%,transparent)] px-2 py-0.5 text-[0.68rem] font-medium",
              meta.tone,
            )}
          >
            {meta.label}
          </span>
        </div>
        <span className="shrink-0 text-[0.68rem] text-[var(--mut)]">
          {proposal.kb_name}
        </span>
      </div>

      {proposal.impact && (
        <p className="mt-3 text-[0.78rem] leading-relaxed text-[var(--text)]">
          {proposal.impact}
        </p>
      )}

      {proposal.conflict && (
        <p
          className="mt-2 flex items-start gap-1.5 rounded-lg border border-[var(--status-amber)] bg-[var(--status-amber-bg)] px-3 py-2 text-[0.72rem] leading-relaxed text-[var(--status-amber-text)]"
          role="alert"
        >
          <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          <span>{proposal.conflict}</span>
        </p>
      )}

      {isTerminal ? (
        <p className="approval-card-no-permission mt-3">
          你对该知识库无写入权限，无法提交审批，需管理员操作
        </p>
      ) : (
        <div className="approval-card-actions">
          {doubleConfirm && armed ? (
            <>
              <p className="approval-card-confirm-warning">
                再次确认：此操作将进入管理员审批，且
                {proposal.operation === "delete"
                  ? "删除后保留 30 天可恢复"
                  : "恢复后将重新参与检索"}
                。确认仍要{proposal.operation === "delete" ? "删除" : "恢复"}吗？
              </p>
              <button
                type="button"
                className="approval-card-btn approval-card-btn-adopt"
                disabled={submitting}
                onClick={onSubmit}
                data-testid="proposal-btn-submit"
              >
                {submitting ? "提交中…" : "再次确认，提交审批"}
              </button>
              <button
                type="button"
                className="approval-card-btn approval-card-btn-cancel"
                disabled={submitting}
                onClick={() => setArmed(false)}
                data-testid="proposal-btn-rethink"
              >
                再想想
              </button>
            </>
          ) : (
            <>
              <button
                type="button"
                className="approval-card-btn approval-card-btn-adopt"
                disabled={submitting}
                onClick={() => (doubleConfirm ? setArmed(true) : onSubmit?.())}
                data-testid="proposal-btn-submit"
              >
                {submitting
                  ? "提交中…"
                  : doubleConfirm
                    ? "确认"
                    : "确认提交审批"}
              </button>
              <button
                type="button"
                className="approval-card-btn approval-card-btn-cancel"
                disabled={submitting}
                onClick={onCancel}
                data-testid="proposal-btn-cancel"
              >
                <FileText className="h-3.5 w-3.5" />
                取消
              </button>
            </>
          )}
        </div>
      )}

      {error && (
        <p className="approval-card-error" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
