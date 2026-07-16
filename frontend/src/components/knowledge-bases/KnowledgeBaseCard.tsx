import { ArrowRight } from "lucide-react";
import { Link } from "react-router-dom";

import { MemberWriteBlockedButton } from "@/components/knowledge-bases/MemberWriteBlockedButton";
import { Button } from "@/components/ui/button";
import type { KnowledgeBase } from "@/lib/knowledge-base-api";
import { cn } from "@/lib/utils";

function formatUpdatedLabel(iso: string): string {
  const updated = new Date(iso);
  const now = new Date();
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const startOfUpdated = new Date(
    updated.getFullYear(),
    updated.getMonth(),
    updated.getDate(),
  );
  const dayDiff = Math.round(
    (startOfToday.getTime() - startOfUpdated.getTime()) / 86_400_000,
  );
  if (dayDiff === 0) return "今天更新";
  if (dayDiff === 1) return "昨天更新";
  if (dayDiff < 7) return `${dayDiff} 天前`;
  if (dayDiff < 28) {
    const weeks = Math.floor(dayDiff / 7);
    return weeks === 1 ? "1 周前" : `${weeks} 周前`;
  }
  return updated.toLocaleDateString("zh-CN", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

/** 绝对日期，用于 0 文档库：空库没有"更新"概念，改为"创建于 YYYY-MM-DD" */
function formatCreatedLabel(iso: string): string {
  return new Date(iso).toLocaleDateString("zh-CN", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

type KbStatusDot = "ok" | "processing" | "failed";

function resolveStatusDot(kb: KnowledgeBase): KbStatusDot {
  if (kb.failed_count > 0) return "failed";
  if (kb.processing_count > 0) return "processing";
  return "ok";
}

const DOT_CLASS: Record<KbStatusDot, string> = {
  ok: "bg-[var(--status-ok)]",
  processing: "bg-[var(--status-amber)]",
  failed: "bg-[var(--status-err)]",
};

const BADGE_BG: Record<KbStatusDot, string> = {
  ok: "bg-[var(--status-ok-bg)]",
  processing: "bg-[var(--status-amber-bg)]",
  failed: "bg-[var(--status-err-bg)]",
};

const BADGE_TEXT: Record<KbStatusDot, string> = {
  ok: "text-[var(--status-ok-text)]",
  processing: "text-[var(--status-amber-text)]",
  failed: "text-[var(--status-err-text)]",
};

const BADGE_LABEL: Record<KbStatusDot, string> = {
  ok: "可问答",
  processing: "索引中",
  failed: "有失败",
};

function KbStatusBadge({ kb }: { kb: KnowledgeBase }) {
  const status = resolveStatusDot(kb);
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-[6px] px-2 py-1 text-[0.68rem] font-medium",
        BADGE_BG[status],
        BADGE_TEXT[status],
      )}
    >
      <span className={cn("h-1.5 w-1.5 rounded-full", DOT_CLASS[status])} aria-hidden />
      {BADGE_LABEL[status]}
    </span>
  );
}

interface KnowledgeBaseCardProps {
  kb: KnowledgeBase;
  onDelete: (kb: KnowledgeBase) => void;
  onEdit?: (kb: KnowledgeBase) => void;
  canDelete?: boolean;
  canEdit?: boolean;
  deleting?: boolean;
  onMemberWriteBlocked?: () => void;
}

export function KnowledgeBaseCard({
  kb,
  onDelete,
  onEdit,
  canDelete = true,
  canEdit = false,
  deleting = false,
  onMemberWriteBlocked,
}: KnowledgeBaseCardProps) {
  const updatedAt = kb.updated_at ?? kb.created_at;
  const isEmpty = (kb.document_count ?? 0) === 0;

  return (
    <article className="card-lift relative rounded-2xl border border-[var(--line2)] bg-[var(--surf)] p-4 shadow-[var(--card-shadow)] hover:border-[var(--line)]">
      <span className="card-top-accent" aria-hidden />
      <div className="flex items-start justify-between gap-3">
        <h3
          className="min-w-0 flex-1 truncate font-serif text-[0.95rem] font-semibold text-foreground"
          title={kb.name}
        >
          {kb.name}
        </h3>
        <KbStatusBadge kb={kb} />
      </div>
      <p className="mt-1.5 text-[0.72rem] text-[var(--mut)]">
        {isEmpty
          ? `空库 · 创建于 ${formatCreatedLabel(kb.created_at)}`
          : `${kb.document_count ?? 0} 篇文档 · ${formatUpdatedLabel(updatedAt)}`}
      </p>
      {kb.description && (
        <p className="mt-2 line-clamp-2 text-xs text-[var(--mut)]">
          {kb.description}
        </p>
      )}
      <div className="mt-3.5 flex flex-wrap items-center gap-2">
        <Button asChild size="sm" variant="brand" className="rounded-[8px]">
          <Link to={`/knowledge-bases/${kb.id}`}>
            <ArrowRight className="h-3.5 w-3.5" aria-hidden />
            进入
          </Link>
        </Button>
        {canEdit && onEdit ? (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => onEdit(kb)}
            className="rounded-[8px] text-[0.75rem] text-[var(--mut)] hover:bg-[var(--surf2)] hover:text-foreground"
          >
            编辑
          </Button>
        ) : onMemberWriteBlocked ? (
          <MemberWriteBlockedButton
            size="sm"
            onBlocked={onMemberWriteBlocked}
            className="rounded-[8px] text-[0.75rem] text-[var(--mut)] hover:bg-[var(--surf2)] hover:text-foreground"
          >
            编辑
          </MemberWriteBlockedButton>
        ) : null}
        {canDelete ? (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            disabled={deleting}
            onClick={() => onDelete(kb)}
            className="rounded-[8px] text-[0.75rem] text-[var(--mut)] hover:bg-[var(--bad)]/10 hover:text-[var(--bad)]"
          >
            {deleting ? "删除中…" : "删除"}
          </Button>
        ) : onMemberWriteBlocked ? (
          <MemberWriteBlockedButton
            size="sm"
            onBlocked={onMemberWriteBlocked}
            className="rounded-[8px] text-[0.75rem] text-[var(--mut)] hover:bg-[var(--surf2)] hover:text-foreground"
          >
            删除
          </MemberWriteBlockedButton>
        ) : null}
      </div>
    </article>
  );
}
