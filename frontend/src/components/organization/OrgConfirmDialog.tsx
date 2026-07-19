import { useEffect, useId } from "react";

import { Button } from "@/components/ui/button";

interface OrgConfirmDialogProps {
  open: boolean;
  title: string;
  description: string;
  confirmLabel: string;
  confirming?: boolean;
  danger?: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirm: () => void;
}

/** 组织管理共用确认框 · 统一皮肤与危险色 token */
export function OrgConfirmDialog({
  open,
  title,
  description,
  confirmLabel,
  confirming = false,
  danger = true,
  onOpenChange,
  onConfirm,
}: OrgConfirmDialogProps) {
  const titleId = useId();

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !confirming) onOpenChange(false);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, confirming, onOpenChange]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      role="presentation"
      onClick={() => {
        if (!confirming) onOpenChange(false);
      }}
    >
      <div className="absolute inset-0 bg-black/30" aria-hidden />
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className="relative z-10 w-full max-w-md rounded-xl border border-[var(--line2)] bg-white p-6 shadow-md"
        onClick={(e) => e.stopPropagation()}
      >
        <h2
          id={titleId}
          className="font-serif text-lg font-semibold text-foreground"
        >
          {title}
        </h2>
        <p className="mt-2 text-sm text-muted">{description}</p>
        <div className="mt-6 flex justify-end gap-2">
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={confirming}
            onClick={() => onOpenChange(false)}
          >
            取消
          </Button>
          <Button
            type="button"
            size="sm"
            disabled={confirming}
            onClick={onConfirm}
            className={
              danger
                ? "bg-[var(--bad)] text-white hover:bg-[var(--bad)]/80"
                : undefined
            }
          >
            {confirming ? "处理中…" : confirmLabel}
          </Button>
        </div>
      </div>
    </div>
  );
}
