import { AlertTriangle, Loader2 } from "lucide-react";

import type { ClarifyPayload } from "@/lib/chat-api";

interface ClarifyCardProps {
  clarify: ClarifyPayload;
  clarifying?: boolean;
  error?: string | null;
  onSelect: (documentId: string, operation: "delete" | "restore") => void;
}

/** G5 · 文档名歧义澄清卡（情景 5）：多篇命中 → 用户点选目标文档。 */
export function ClarifyCard({
  clarify,
  clarifying = false,
  error = null,
  onSelect,
}: ClarifyCardProps) {
  const verb = clarify.operation === "delete" ? "删除" : "恢复";
  return (
    <div className="approval-card mt-3" role="group" aria-label="选择目标文档">
      <div className="approval-card-header">
        <span className="approval-card-title">
          <AlertTriangle
            className="approval-card-title-icon"
            aria-hidden="true"
          />
          请选择要{verb}的文档
        </span>
      </div>
      <p className="approval-card-body">
        检测到多篇名称相近的文档，请确认你要操作的目标：
      </p>
      <ul className="clarify-options">
        {clarify.options.map((opt) => (
          <li key={opt.document_id}>
            <button
              type="button"
              className="clarify-option-btn"
              disabled={clarifying}
              data-testid={`clarify-option-${opt.document_id}`}
              onClick={() => onSelect(opt.document_id, clarify.operation)}
            >
              {opt.filename}
            </button>
          </li>
        ))}
      </ul>
      {clarifying && (
        <p className="mt-2 flex items-center gap-1.5 text-[0.72rem] text-[var(--mut)]">
          <Loader2 className="h-3 w-3 animate-spin" aria-hidden="true" />
          正在生成操作提案…
        </p>
      )}
      {error && (
        <p
          className="mt-2 text-[0.72rem] text-[var(--status-amber-text)]"
          role="alert"
        >
          {error}
        </p>
      )}
    </div>
  );
}
