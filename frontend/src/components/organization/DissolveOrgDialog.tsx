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
      return;
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
        className="relative z-10 w-full max-w-md rounded-2xl border border-[var(--line2)] bg-[var(--bg)] p-6 shadow-[var(--card-shadow)]"
        onClick={(e) => e.stopPropagation()}
      >
        <h2
          id={titleId}
          className="font-serif text-lg font-semibold text-foreground"
        >
          解散团队
        </h2>
        <p className="mt-2 text-sm text-muted">
          解散后将永久删除所有资料库、文档和成员记录，<strong>不可恢复</strong>。
        </p>
        <div className="mt-4 rounded-lg border border-[var(--bad)]/30 bg-[var(--bad)]/5 px-4 py-3 text-sm text-[var(--bad)]">
          此操作不可撤销。团队内所有数据将被永久清除。
        </div>
        <div className="mt-4 space-y-2">
          <label
            htmlFor={inputId}
            className="text-sm font-medium text-foreground"
          >
            请输入 <code className="rounded bg-nav-on px-1.5 py-0.5 text-sm">{orgName}</code> 以确认
          </label>
          <input
            id={inputId}
            type="text"
            value={confirmName}
            disabled={dissolving}
            onChange={(e) => setConfirmName(e.target.value)}
            placeholder={orgName}
            className="w-full rounded-lg border border-[var(--line2)] bg-[var(--input-bg)] px-3 py-2 text-sm text-foreground placeholder:text-muted focus:border-[var(--action)] focus:outline-none focus:ring-2 focus:ring-[var(--action)]/20"
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
