import type { DocumentStatus } from "@/lib/document-api";
import { cn } from "@/lib/utils";

const STATUS_LABEL: Record<DocumentStatus, string> = {
  queued: "处理中",
  processing: "处理中",
  completed: "完成",
  failed: "失败",
};

const STATUS_CLASS: Record<DocumentStatus, string> = {
  queued: "doc-badge-wait",
  processing: "doc-badge-wait",
  completed: "doc-badge-ok",
  failed: "doc-badge-err",
};

interface DocumentStatusBadgeProps {
  status: DocumentStatus;
}

export function DocumentStatusBadge({ status }: DocumentStatusBadgeProps) {
  return (
    <span className={cn("doc-badge", STATUS_CLASS[status])}>
      {STATUS_LABEL[status]}
    </span>
  );
}
