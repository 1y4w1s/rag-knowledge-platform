import { useState } from "react";
import { Link } from "react-router-dom";

import { isDocumentProcessing, type Document } from "@/lib/document-api";

interface DocumentRowActionsProps {
  kbId: string;
  doc: Document;
  canManage: boolean;
  deleting?: boolean;
  onRequestDelete: (doc: Document) => void;
  onRetry: (docId: string) => Promise<void>;
}

export function DocumentRowActions({
  kbId,
  doc,
  canManage,
  deleting = false,
  onRequestDelete,
  onRetry,
}: DocumentRowActionsProps) {
  const [busy, setBusy] = useState<"retry" | null>(null);
  const previewPath = `/knowledge-bases/${kbId}/documents/${doc.id}`;

  if (isDocumentProcessing(doc.status)) {
    return <span className="text-muted">—</span>;
  }

  if (doc.status === "failed") {
    if (!canManage) {
      return <span className="text-muted">—</span>;
    }

    return (
      <span className="inline-flex items-center gap-1 text-[0.78rem] text-muted">
        <Link
          to={previewPath}
          className="font-semibold text-[var(--action)] hover:underline"
        >
          预览
        </Link>
        <span aria-hidden>·</span>
        <button
          type="button"
          disabled={busy === "retry"}
          className="text-[var(--action)] hover:underline disabled:opacity-60"
          onClick={() => {
            void (async () => {
              setBusy("retry");
              try {
                await onRetry(doc.id);
              } finally {
                setBusy(null);
              }
            })();
          }}
        >
          {busy === "retry" ? "重试中…" : "重试"}
        </button>
        <span aria-hidden>·</span>
        <button
          type="button"
          disabled={deleting}
          className="hover:text-[var(--bad)] hover:underline disabled:opacity-60"
          onClick={() => onRequestDelete(doc)}
        >
          {deleting ? "删除中…" : "删除"}
        </button>
      </span>
    );
  }

  if (doc.status === "completed") {
    if (!canManage) {
      return (
        <Link
          to={previewPath}
          className="text-[0.78rem] font-semibold text-[var(--action)] hover:underline"
        >
          预览
        </Link>
      );
    }

    return (
      <span className="inline-flex items-center gap-1 text-[0.78rem] text-muted">
        <Link
          to={previewPath}
          className="font-semibold text-[var(--action)] hover:underline"
        >
          预览
        </Link>
        <span aria-hidden>·</span>
        <button
          type="button"
          disabled={deleting}
          className="hover:text-[var(--bad)] hover:underline disabled:opacity-60"
          onClick={() => onRequestDelete(doc)}
        >
          {deleting ? "删除中…" : "删除"}
        </button>
      </span>
    );
  }

  return <span className="text-muted">—</span>;
}
