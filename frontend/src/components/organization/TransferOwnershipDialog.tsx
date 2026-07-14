import { useEffect, useId, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  formatOrgRoleLabel,
  type OrganizationMember,
} from "@/lib/organization-api";

interface TransferOwnershipDialogProps {
  members: OrganizationMember[];
  currentUserId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirm: (targetUserId: string) => void;
  transferring?: boolean;
}

export function TransferOwnershipDialog({
  members,
  currentUserId,
  open,
  onOpenChange,
  onConfirm,
  transferring = false,
}: TransferOwnershipDialogProps) {
  const titleId = useId();
  const selectId = useId();
  const [targetUserId, setTargetUserId] = useState("");

  const eligible = useMemo(
    () =>
      members.filter(
        (member) => !member.is_owner && member.user_id !== currentUserId,
      ),
    [members, currentUserId],
  );

  useEffect(() => {
    if (!open) {
      setTargetUserId("");
      return;
    }
    if (eligible.length === 1) {
      setTargetUserId(eligible[0].user_id);
    }
  }, [open, eligible]);

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !transferring) onOpenChange(false);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, transferring, onOpenChange]);

  if (!open) return null;

  const selected = eligible.find((member) => member.user_id === targetUserId);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      role="presentation"
      onClick={() => {
        if (!transferring) onOpenChange(false);
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
          转让所有权
        </h2>
        <p className="mt-2 text-sm text-muted">
          转让后你将变为管理员，对方成为新的团队所有者。此操作不可撤销，请谨慎选择。
        </p>

        {eligible.length === 0 ? (
          <p className="mt-4 text-sm text-[var(--action)]">
            团队中暂无其他成员可接收所有权，请先添加成员。
          </p>
        ) : (
          <div className="mt-4 space-y-2">
            <label htmlFor={selectId} className="text-sm font-medium text-foreground">
              转让给
            </label>
            <select
              id={selectId}
              value={targetUserId}
              disabled={transferring}
              onChange={(e) => setTargetUserId(e.target.value)}
              className="w-full rounded-lg border border-[var(--line2)] bg-white px-3 py-2 text-sm text-foreground focus:border-[var(--action)] focus:outline-none focus:ring-2 focus:ring-[var(--action)]/20"
            >
              <option value="">请选择成员</option>
              {eligible.map((member) => (
                <option key={member.user_id} value={member.user_id}>
                  {member.email}（{formatOrgRoleLabel(member.role, member.is_owner)}）
                </option>
              ))}
            </select>
            {selected ? (
              <p className="text-xs text-muted">
                确认后「{selected.email}」将成为所有者，你保留管理员权限。
              </p>
            ) : null}
          </div>
        )}

        <div className="mt-6 flex justify-end gap-2">
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={transferring}
            onClick={() => onOpenChange(false)}
          >
            取消
          </Button>
          <Button
            type="button"
            size="sm"
            disabled={transferring || !targetUserId || eligible.length === 0}
            onClick={() => onConfirm(targetUserId)}
            className="bg-[#B85A2E] text-white hover:bg-[#9A4A2E]"
          >
            {transferring ? "转让中…" : "确认转让"}
          </Button>
        </div>
      </div>
    </div>
  );
}
