import { useEffect, useId } from "react";

import { Button } from "@/components/ui/button";
import type { Document } from "@/lib/document-api";

interface DeleteDocumentDialogProps {
  doc: Document | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirm: () => void;
  deleting?: boolean;
}

export function DeleteDocumentDialog({
  doc,
  open,
  onOpenChange,
  onConfirm,
  deleting = false,
}: DeleteDocumentDialogProps) {
  const titleId = useId();

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !deleting) onOpenChange(false);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, deleting, onOpenChange]);

  if (!open || !doc) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      role="presentation"
      onClick={() => {
        if (!deleting) onOpenChange(false);
      }}
    >
      <div className="absolute inset-0 bg-black/30" aria-hidden />
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className="relative z-10 w-full max-w-md rounded-2xl border border-[var(--line2)] bg-[var(--bg)] p-6 shadow-[var(--card-shadow)]"
        onClick={(e) => e.stopPropagation()}
      >
        <h2
          id={titleId}
          className="font-serif text-lg font-semibold text-foreground"
        >
          删除文档
        </h2>
        <p className="mt-2 text-sm text-muted">
          确定删除「{doc.filename}」？文档将移入回收站，30 天内可恢复。
        </p>

        <div className="mt-6 flex justify-end gap-2">
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={deleting}
            onClick={() => onOpenChange(false)}
          >
            取消
          </Button>
          <Button
            type="button"
            size="sm"
            disabled={deleting}
            onClick={onConfirm}
            className="bg-[var(--bad)] text-white hover:bg-[var(--bad)]/80"
          >
            {deleting ? "删除中…" : "确认删除"}
          </Button>
        </div>
      </div>
    </div>
  );
}
