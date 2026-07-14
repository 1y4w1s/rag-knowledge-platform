import { CheckCircle2, FileText, Library, MessageSquare } from "lucide-react";

import { StatCard } from "@/components/dashboard/StatCard";
import type { DashboardStats } from "@/lib/dashboard-api";

interface DashboardStatsGridProps {
  stats: DashboardStats;
  recentKbId: string | null;
  dim?: boolean;
  emptyNote?: string | null;
}

function recentKbHref(recentKbId: string | null): string {
  return recentKbId
    ? `/knowledge-bases/${recentKbId}`
    : "/knowledge-bases";
}

function recentKbStatusHref(
  recentKbId: string | null,
  status: "processing" | "failed",
): string | null {
  if (!recentKbId) return null;
  return `/knowledge-bases/${recentKbId}?status=${status}`;
}

export function DashboardStatsGrid({
  stats,
  recentKbId,
  dim,
  emptyNote,
}: DashboardStatsGridProps) {
  const docStatus = stats.documents_by_status;
  const processingCount = docStatus.queued + docStatus.processing;
  const failedCount = docStatus.failed;

  const uploadedFooterLinks = [];
  const processingHref = recentKbStatusHref(recentKbId, "processing");
  const failedHref = recentKbStatusHref(recentKbId, "failed");

  if (processingCount > 0 && processingHref) {
    uploadedFooterLinks.push({
      label: `${processingCount} 篇整理中`,
      href: processingHref,
    });
  }
  if (failedCount > 0 && failedHref) {
    uploadedFooterLinks.push({
      label: `${failedCount} 篇失败`,
      href: failedHref,
    });
  }

  const chatHref = recentKbId
    ? `/knowledge-bases/${recentKbId}/chat`
    : "/knowledge-bases";

  return (
    <section aria-label="使用情况">
      <h3 className="mb-2.5 text-xs font-medium text-muted">使用情况</h3>
      <div className="grid grid-cols-2 gap-2.5 md:grid-cols-4">
        <StatCard
          icon={Library}
          label="资料库"
          hint="文档集合"
          value={stats.knowledge_base_count}
          href="/knowledge-bases"
          iconTone="clay"
          index={0}
          dim={dim}
        />
        <StatCard
          icon={FileText}
          label="已上传文件"
          hint="PDF、Word 等"
          value={stats.document_count}
          href={recentKbHref(recentKbId)}
          iconTone="blue"
          index={1}
          footerLinks={
            uploadedFooterLinks.length > 0 ? uploadedFooterLinks : undefined
          }
          dim={dim}
        />
        <StatCard
          icon={CheckCircle2}
          label="已可提问文件"
          hint="整理完成"
          value={docStatus.completed}
          href={recentKbHref(recentKbId)}
          iconTone="green"
          index={2}
          dim={dim}
        />
        <StatCard
          icon={MessageSquare}
          label="近 7 日提问"
          hint="向 AI 发出的问题"
          value={stats.chat_message_count}
          href={chatHref}
          iconTone="rose"
          index={3}
          dim={dim}
        />
      </div>
      {emptyNote && (
        <p className="mt-2.5 text-[0.72rem] leading-snug text-muted">
          {emptyNote}
        </p>
      )}
    </section>
  );
}
