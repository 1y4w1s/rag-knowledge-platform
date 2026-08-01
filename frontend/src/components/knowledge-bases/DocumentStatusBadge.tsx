import type { DocumentStatus } from "@/lib/document-api";
import { cn } from "@/lib/utils";

const STAGE_LABEL: Record<string, string> = {
  parsing: "正在解析…",
  chunking: "正在切片…",
  embedding: "正在向量化…",
};

function processingLabel(
  processingStage?: string | null,
  progressDetail?: string | null,
): string {
  if (progressDetail) return "正在识别…";
  if (processingStage && STAGE_LABEL[processingStage]) {
    return STAGE_LABEL[processingStage];
  }
  return "处理中";
}

interface DocumentStatusBadgeProps {
  status: DocumentStatus;
  processingStage?: string | null;
  progressDetail?: string | null;
}

export function DocumentStatusBadge({
  status,
  processingStage = null,
  progressDetail = null,
}: DocumentStatusBadgeProps) {
  let text: string;
  let cls: string;
  if (status === "queued") {
    text = "排队等待处理";
    cls = "doc-badge-wait";
  } else if (status === "processing") {
    text = processingLabel(processingStage, progressDetail);
    cls = "doc-badge-wait";
  } else if (status === "completed") {
    text = "完成";
    cls = "doc-badge-ok";
  } else {
    text = "失败";
    cls = "doc-badge-err";
  }

  return (
    <span className={cn("doc-badge", cls)}>
      {text}
    </span>
  );
}
