import { useEffect } from "react";

import { AddUnitMemberDialog } from "@/components/organization/departments/AddUnitMemberDialog";
import { CreateDepartmentDialog } from "@/components/organization/departments/CreateDepartmentDialog";
import { DepartmentDetailPanel } from "@/components/organization/departments/DepartmentDetailPanel";
import { DepartmentTree } from "@/components/organization/departments/DepartmentTree";
import { RequireTeamWorkspace } from "@/components/common/RequireTeamWorkspace";
import { SectionTitle } from "@/components/common/SectionTitle";
import { AlertBanner } from "@/components/ui/AlertBanner";
import { Button } from "@/components/ui/button";
import { useOrgDepartments } from "@/lib/use-org-departments";

export function OrgDepartmentsPage() {
  const state = useOrgDepartments();

  useEffect(() => {
    document.title = "睿阁 · 组织与部门";
    let meta = document.querySelector<HTMLMetaElement>('meta[name="description"]');
    if (!meta) {
      meta = document.createElement("meta");
      meta.name = "description";
      document.head.appendChild(meta);
    }
    meta.setAttribute(
      "content",
      "搭建部门树，将公司成员分配到各部门，管理组织层级与权限。",
    );
  }, []);

  if (state.loading) {
    return (
      <div className="space-y-4">
        <div className="h-8 w-56 animate-pulse rounded bg-border/70" />
        <div className="grid gap-4 lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
          <div className="h-80 animate-pulse rounded-xl border border-[var(--line2)] bg-white/60" />
          <div className="h-80 animate-pulse rounded-xl border border-[var(--line2)] bg-white/60" />
        </div>
      </div>
    );
  }

  if (state.error) {
    return (
      <AlertBanner
        action={
          <Button type="button" variant="outline" size="sm" onClick={() => void state.loadAll()}>
            重试
          </Button>
        }
      >
        {state.error}
      </AlertBanner>
    );
  }

  const isSubSelected = !!state.selectedUnit && !state.isRootSelected;
  const createBtnLabel = isSubSelected ? "+ 新建子部门" : "+ 新建一级部门";
  const createBtnOnClick = isSubSelected ? state.openCreateChild : state.openCreateTopLevel;

  return (
    <RequireTeamWorkspace feature="组织与部门管理">
    <div className="max-w-[1180px] mx-auto px-7 pb-16 pt-7 space-y-4">
      <SectionTitle
        label="组织与部门"
        en="DEPARTMENTS"
        trailing={
          <Button
            type="button"
            size="sm"
            disabled={state.creating}
            onClick={createBtnOnClick}
          >
            {createBtnLabel}
          </Button>
        }
      />

      <div className="grid gap-4 lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
        <section className="rounded-xl border border-[var(--line2)] bg-white/80 p-3">
          <h3 className="mb-2 px-1 text-xs font-medium text-muted">
            部门树
          </h3>
          <DepartmentTree
            root={state.root}
            orgName={state.orgName}
            selectedId={state.selectedId}
            onSelect={state.setSelectedId}
          />
        </section>

        <section className="rounded-xl border border-[var(--line2)] bg-white/80 p-4">
          <DepartmentDetailPanel
            unit={state.selectedUnit}
            isRoot={state.isRootSelected}
            orgName={state.orgName}
            members={state.members}
            membersLoading={state.membersLoading}
            roster={state.roster}
            actionError={state.actionError}
            renaming={state.renaming}
            deleting={state.deleting}
            updatingUserId={state.updatingUserId}
            removingUserId={state.removingUserId}
            onDismissError={() => state.setActionError(null)}
            onAddMember={() => state.setAddMemberOpen(true)}
            onRename={state.handleRename}
            onDelete={state.handleDelete}
            onSetRole={(member, role) => void state.handleSetRole(member, role)}
            onSetPrimary={(member) => void state.handleSetPrimary(member)}
            onRemove={(member) => void state.handleRemoveMember(member)}
          />
        </section>
      </div>

      <CreateDepartmentDialog
        open={state.createDialog.open}
        title={state.createDialog.title}
        description={state.createDialog.description}
        submitting={state.creating}
        onOpenChange={(open) =>
          state.setCreateDialog((prev) => ({ ...prev, open }))
        }
        onSubmit={state.handleCreate}
      />

      <AddUnitMemberDialog
        open={state.addMemberOpen}
        roster={state.roster}
        existingMembers={state.members}
        submitting={state.addingMember}
        onOpenChange={state.setAddMemberOpen}
        onSubmit={state.handleAddMember}
      />
    </div>
    </RequireTeamWorkspace>
  );
}
