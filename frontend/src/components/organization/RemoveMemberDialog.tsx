import { useEffect, useId } from "react";

import { Button } from "@/components/ui/button";
import type { OrganizationMember } from "@/lib/organization-api";

interface RemoveMemberDialogProps {
  member: OrganizationMember | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirm: () => void;
  removing?: boolean;
}

export function RemoveMemberDialog({
  member,
  open,
  onOpenChange,
  onConfirm,
  removing = false,
}: RemoveMemberDialogProps) {
  const titleId = useId();

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !removing) onOpenChange(false);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, removing, onOpenChange]);

  if (!open || !member) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      role="presentation"
      onClick={() => {
        if (!removing) onOpenChange(false);
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
          className="font-serif text-lg font-semibold tracking-[0.02em] text-foreground"
        >
          移除成员
        </h2>
        <p className="mt-2 text-sm text-muted">
          确定将「{member.email}」移出团队？移除后将无法访问团队资料库。
        </p>

        <div className="mt-6 flex justify-end gap-2">
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={removing}
            onClick={() => onOpenChange(false)}
          >
            取消
          </Button>
          <Button
            type="button"
            size="sm"
            disabled={removing}
            onClick={onConfirm}
            className="bg-[#B85A2E] text-white hover:bg-[#9A4A2E]"
          >
            {removing ? "移除中…" : "确认移除"}
          </Button>
        </div>
      </div>
    </div>
  );
}
