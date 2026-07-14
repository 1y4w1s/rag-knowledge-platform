import { useEffect, useId, useMemo } from "react";

import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import type { OrganizationMember } from "@/lib/organization-api";
import type { OrgUnitMember, UnitRole } from "@/lib/org-units-api";

interface AddUnitMemberDialogProps {
  open: boolean;
  roster: OrganizationMember[];
  existingMembers: OrgUnitMember[];
  onOpenChange: (open: boolean) => void;
  onSubmit: (payload: {
    user_id: string;
    role: UnitRole;
    is_primary: boolean;
  }) => Promise<void>;
  submitting?: boolean;
}

export function AddUnitMemberDialog({
  open,
  roster,
  existingMembers,
  onOpenChange,
  onSubmit,
  submitting = false,
}: AddUnitMemberDialogProps) {
  const titleId = useId();
  const userId = useId();
  const roleId = useId();
  const primaryId = useId();

  const available = useMemo(() => {
    const inUnit = new Set(existingMembers.map((m) => m.user_id));
    return roster.filter((m) => !inUnit.has(m.user_id));
  }, [existingMembers, roster]);

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !submitting) onOpenChange(false);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, submitting, onOpenChange]);

  if (!open) return null;

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const selectedUserId = (form.elements.namedItem("user_id") as HTMLSelectElement)
      .value;
    const role = (form.elements.namedItem("role") as HTMLSelectElement)
      .value as UnitRole;
    const isPrimary = (form.elements.namedItem("is_primary") as HTMLInputElement)
      .checked;
    if (!selectedUserId) return;
    await onSubmit({ user_id: selectedUserId, role, is_primary: isPrimary });
    form.reset();
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      role="presentation"
      onClick={() => {
        if (!submitting) onOpenChange(false);
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
          添加部门成员
        </h2>
        <p className="mt-2 text-sm text-muted">
          从公司花名册选择成员，加入当前部门。
        </p>

        <form className="mt-4 space-y-4" onSubmit={(e) => void handleSubmit(e)}>
          <div>
            <Label htmlFor={userId} className="settings-field-label">
              成员
            </Label>
            <select
              id={userId}
              name="user_id"
              required
              disabled={submitting || available.length === 0}
              className="settings-field-input h-10 w-full"
            >
              <option value="">
                {available.length === 0 ? "花名册成员已全部加入" : "请选择成员"}
              </option>
              {available.map((member) => (
                <option key={member.user_id} value={member.user_id}>
                  {member.email}
                </option>
              ))}
            </select>
          </div>

          <div>
            <Label htmlFor={roleId} className="settings-field-label">
              部门角色
            </Label>
            <select
              id={roleId}
              name="role"
              defaultValue="unit_member"
              disabled={submitting}
              className="settings-field-input h-10 w-full"
            >
              <option value="unit_member">部门成员</option>
              <option value="unit_admin">部门管理员</option>
            </select>
          </div>

          <div className="flex items-center gap-2">
            <input
              id={primaryId}
              name="is_primary"
              type="checkbox"
              disabled={submitting}
              className="h-4 w-4 rounded border-[var(--line2)] accent-[var(--action)]"
            />
            <Label htmlFor={primaryId} className="text-sm text-foreground">
              设为主部门
            </Label>
          </div>

          <div className="flex justify-end gap-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={submitting}
              onClick={() => onOpenChange(false)}
            >
              取消
            </Button>
            <Button
              type="submit"
              size="sm"
              disabled={submitting || available.length === 0}
            >
              {submitting ? "添加中…" : "添加"}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
