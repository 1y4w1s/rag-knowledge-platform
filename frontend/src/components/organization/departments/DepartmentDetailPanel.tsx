import { useEffect, useState } from "react";

import { UnitMembersTable } from "@/components/organization/departments/UnitMembersTable";
import { AlertBanner } from "@/components/ui/AlertBanner";
import { Button } from "@/components/ui/button";
import type { OrganizationMember } from "@/lib/organization-api";
import {
  canDeleteUnit,
  type OrgUnit,
  type OrgUnitMember,
  type UnitRole,
} from "@/lib/org-units-api";

interface DepartmentDetailPanelProps {
  unit: OrgUnit | null;
  isRoot: boolean;
  orgName: string;
  members: OrgUnitMember[];
  membersLoading: boolean;
  roster: OrganizationMember[];
  actionError: string | null;
  renaming: boolean;
  deleting: boolean;
  updatingUserId: string | null;
  removingUserId: string | null;
  onDismissError: () => void;
  onCreateChild: () => void;
  onAddMember: () => void;
  onRename: (name: string) => Promise<void>;
  onDelete: () => Promise<void>;
  onSetRole: (member: OrgUnitMember, role: UnitRole) => void;
  onSetPrimary: (member: OrgUnitMember) => void;
  onRemove: (member: OrgUnitMember) => void;
}

export function DepartmentDetailPanel({
  unit,
  isRoot,
  orgName,
  members,
  membersLoading,
  roster,
  actionError,
  renaming,
  deleting,
  updatingUserId,
  removingUserId,
  onDismissError,
  onCreateChild,
  onAddMember,
  onRename,
  onDelete,
  onSetRole,
  onSetPrimary,
  onRemove,
}: DepartmentDetailPanelProps) {
  const [nameDraft, setNameDraft] = useState("");

  useEffect(() => {
    setNameDraft(unit?.name ?? "");
  }, [unit?.id, unit?.name]);

  if (!unit) {
    return (
      <div className="flex h-full min-h-[320px] flex-col items-center justify-center rounded-xl border border-dashed border-[var(--line2)] bg-[rgba(245,242,237,0.35)] px-6 text-center">
        <p className="font-serif text-base font-medium text-foreground">
          选择左侧部门节点
        </p>
        <p className="mt-2 max-w-sm text-sm text-muted">
          在左侧树中点选部门，可查看成员、新建子部门或重命名。
        </p>
      </div>
    );
  }

  const displayName = isRoot ? orgName : unit.name;
  const deletable = canDeleteUnit(unit) && !isRoot;

  async function handleRenameSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!unit) return;
    const trimmed = nameDraft.trim();
    if (!trimmed || trimmed === unit.name) return;
    await onRename(trimmed);
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="font-serif text-lg font-semibold tracking-[0.02em] text-foreground">
            {displayName}
          </h3>
          <p className="mt-1 text-sm text-muted">
            {unit.member_count} 名成员 · {unit.child_count} 个子部门
            {unit.kb_count > 0 ? ` · ${unit.kb_count} 个资料库` : ""}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button type="button" size="sm" variant="outline" onClick={onCreateChild}>
            新建子部门
          </Button>
          <Button type="button" size="sm" onClick={onAddMember}>
            + 添加成员
          </Button>
        </div>
      </div>

      {actionError ? (
        <AlertBanner onDismiss={onDismissError}>{actionError}</AlertBanner>
      ) : null}

      <form
        className="flex flex-wrap items-end gap-2 rounded-[10px] border border-[var(--line2)] bg-white/70 p-3"
        onSubmit={(e) => void handleRenameSubmit(e)}
      >
        <div className="min-w-[200px] flex-1">
          <label htmlFor="dept-rename" className="settings-field-label">
            部门名称
          </label>
          <input
            id="dept-rename"
            type="text"
            maxLength={64}
            value={nameDraft}
            disabled={renaming}
            onChange={(e) => setNameDraft(e.target.value)}
            className="settings-field-input mt-1"
          />
        </div>
        <Button
          type="submit"
          size="sm"
          variant="outline"
          disabled={renaming || !nameDraft.trim() || nameDraft.trim() === unit.name}
        >
          {renaming ? "保存中…" : "重命名"}
        </Button>
        {deletable ? (
          <Button
            type="button"
            size="sm"
            variant="outline"
            disabled={deleting}
            className="text-[#B85A2E] hover:bg-[#FDF4EF] hover:text-[#9A4A2E]"
            onClick={() => void onDelete()}
          >
            {deleting ? "删除中…" : "删除部门"}
          </Button>
        ) : null}
      </form>

      {!isRoot || unit.child_count > 0 || members.length > 0 ? (
        <div>
          <h4 className="mb-2 text-sm font-medium text-foreground">部门成员</h4>
          {membersLoading ? (
            <div className="h-32 animate-pulse rounded-xl border border-[var(--line2)] bg-white/60" />
          ) : (
            <UnitMembersTable
              members={members}
              updatingUserId={updatingUserId}
              removingUserId={removingUserId}
              onSetRole={onSetRole}
              onSetPrimary={onSetPrimary}
              onRemove={onRemove}
            />
          )}
        </div>
      ) : (
        <div className="rounded-[10px] border border-dashed border-[var(--line2)] bg-[rgba(245,242,237,0.45)] px-4 py-10 text-center">
          <p className="text-sm text-muted">
            当前仅有公司根节点。点击右上角「新建一级部门」或在上方「新建子部门」开始搭建组织树。
          </p>
          {roster.length === 0 ? (
            <p className="mt-2 text-sm text-muted">
              添加成员前请先在「成员管理」邀请公司成员。
            </p>
          ) : null}
        </div>
      )}
    </div>
  );
}
