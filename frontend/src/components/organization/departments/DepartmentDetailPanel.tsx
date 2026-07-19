import { useEffect, useState } from "react";

import { OrgConfirmDialog } from "@/components/organization/OrgConfirmDialog";
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
  onAddMember,
  onRename,
  onDelete,
  onSetRole,
  onSetPrimary,
  onRemove,
}: DepartmentDetailPanelProps) {
  const [nameDraft, setNameDraft] = useState("");
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [removeTarget, setRemoveTarget] = useState<OrgUnitMember | null>(null);

  useEffect(() => {
    setNameDraft(unit?.name ?? "");
    setDeleteOpen(false);
    setRemoveTarget(null);
  }, [unit?.id, unit?.name]);

  if (!unit) {
    return (
      <p className="py-6 text-sm text-muted">在左侧选择部门</p>
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
          <h3 className="font-serif text-lg font-semibold text-foreground">
            {displayName}
          </h3>
          <p className="mt-1 text-sm text-muted">
            {unit.member_count} 名成员 · {unit.child_count} 个子部门
            {unit.kb_count > 0 ? ` · ${unit.kb_count} 个资料库` : ""}
          </p>
          {isRoot ? (
            <p className="mt-1 text-xs text-muted">
              根节点名称请在「团队设置」修改
            </p>
          ) : null}
        </div>
        <Button type="button" size="sm" variant="outline" onClick={onAddMember}>
          + 添加成员
        </Button>
      </div>

      {actionError ? (
        <AlertBanner onDismiss={onDismissError}>{actionError}</AlertBanner>
      ) : null}

      {!isRoot ? (
        <form
          className="org-dept-rename flex flex-wrap items-end gap-2"
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
              className="text-[var(--bad)] hover:bg-[color:var(--status-err-bg)] hover:text-[var(--bad)]"
              onClick={() => setDeleteOpen(true)}
            >
              删除部门
            </Button>
          ) : null}
        </form>
      ) : null}

      {!isRoot || unit.child_count > 0 || members.length > 0 ? (
        <div>
          <h4 className="mb-2 text-sm font-medium text-foreground">部门成员</h4>
          {membersLoading ? (
            <div className="h-32 animate-pulse rounded border border-[var(--line2)] bg-white/60" />
          ) : (
            <UnitMembersTable
              members={members}
              updatingUserId={updatingUserId}
              removingUserId={removingUserId}
              onSetRole={onSetRole}
              onSetPrimary={onSetPrimary}
              onRemove={setRemoveTarget}
            />
          )}
        </div>
      ) : (
        <p className="text-sm text-muted">
          暂无子部门。
          {roster.length === 0 ? " 可先在「成员管理」邀请同事。" : " 点右上角新建一级部门。"}
        </p>
      )}

      <OrgConfirmDialog
        open={deleteOpen}
        title="删除部门"
        description={`确定删除「${displayName}」？`}
        confirmLabel="确认删除"
        confirming={deleting}
        onOpenChange={setDeleteOpen}
        onConfirm={() => {
          void onDelete().then(() => setDeleteOpen(false));
        }}
      />

      <OrgConfirmDialog
        open={removeTarget !== null}
        title="移出部门"
        description={
          removeTarget
            ? `确定将「${removeTarget.email}」移出此部门？`
            : ""
        }
        confirmLabel="确认移出"
        confirming={removingUserId !== null}
        onOpenChange={(open) => {
          if (!open) setRemoveTarget(null);
        }}
        onConfirm={() => {
          if (!removeTarget) return;
          onRemove(removeTarget);
          setRemoveTarget(null);
        }}
      />
    </div>
  );
}
