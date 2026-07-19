import { useEffect, useId, useState } from "react";

import { Button } from "@/components/ui/button";

interface DissolveOrgDialogProps {
  orgName: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirm: (confirmName: string) => void;
  dissolving?: boolean;
}

export function DissolveOrgDialog({
  orgName,
  open,
  onOpenChange,
  onConfirm,
  dissolving = false,
}: DissolveOrgDialogProps) {
  const titleId = useId();
  const inputId = useId();
  const [confirmName, setConfirmName] = useState("");

  useEffect(() => {
    if (!open) {
      setConfirmName("");
    }
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !dissolving) onOpenChange(false);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, dissolving, onOpenChange]);

  if (!open) return null;

  const nameMatched = confirmName.trim() === orgName;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      role="presentation"
      onClick={() => {
        if (!dissolving) onOpenChange(false);
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
          解散团队
        </h2>
        <p className="mt-2 text-sm text-muted">
          将永久删除资料库、文档与成员记录，不可恢复。
        </p>
        <div className="mt-4 space-y-2">
          <label htmlFor={inputId} className="settings-field-label">
            请输入 <code className="rounded bg-[var(--surf2)] px-1.5 py-0.5 text-sm">{orgName}</code> 确认
          </label>
          <input
            id={inputId}
            type="text"
            value={confirmName}
            disabled={dissolving}
            onChange={(e) => setConfirmName(e.target.value)}
            placeholder={orgName}
            className="settings-field-input"
          />
        </div>

        <div className="mt-6 flex justify-end gap-2">
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={dissolving}
            onClick={() => onOpenChange(false)}
          >
            取消
          </Button>
          <Button
            type="button"
            size="sm"
            disabled={dissolving || !nameMatched}
            onClick={() => onConfirm(confirmName)}
            className="bg-[var(--bad)] text-white hover:bg-[var(--bad)]/80"
          >
            {dissolving ? "解散中…" : "确认解散"}
          </Button>
        </div>
      </div>
    </div>
  );
}
