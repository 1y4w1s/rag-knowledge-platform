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
    meta.setAttribute("content", "管理组织部门树与部门成员。");
  }, []);

  if (state.loading) {
    return (
      <div className="mx-auto max-w-[1180px] space-y-4 px-7 pb-16 pt-7">
        <div className="h-8 w-56 animate-pulse rounded bg-border/70" />
        <div className="grid gap-4 lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
          <div className="h-80 animate-pulse rounded border border-[var(--line2)] bg-white/60" />
          <div className="h-80 animate-pulse rounded border border-[var(--line2)] bg-white/60" />
        </div>
      </div>
    );
  }

  if (state.error) {
    return (
      <div className="mx-auto max-w-[1180px] px-7 pb-16 pt-7">
        <AlertBanner
          action={
            <Button type="button" variant="outline" size="sm" onClick={() => void state.loadAll()}>
              重试
            </Button>
          }
        >
          {state.error}
        </AlertBanner>
      </div>
    );
  }

  const isSubSelected = !!state.selectedUnit && !state.isRootSelected;
  const createBtnLabel = isSubSelected ? "+ 新建子部门" : "+ 新建一级部门";
  const createBtnOnClick = isSubSelected ? state.openCreateChild : state.openCreateTopLevel;

  return (
    <RequireTeamWorkspace feature="组织与部门管理">
      <div className="org-page-quiet mx-auto max-w-[1180px] space-y-4 px-7 pb-16 pt-7">
        <SectionTitle
          label="组织与部门"
          en="DEPARTMENTS"
          tone="quiet"
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

        <div className="org-dept-split grid gap-0 lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
          <section className="org-dept-pane org-dept-pane-tree">
            <h3 className="org-dept-pane-label">部门树</h3>
            <DepartmentTree
              root={state.root}
              orgName={state.orgName}
              selectedId={state.selectedId}
              onSelect={state.setSelectedId}
            />
          </section>

          <section className="org-dept-pane org-dept-pane-detail">
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
