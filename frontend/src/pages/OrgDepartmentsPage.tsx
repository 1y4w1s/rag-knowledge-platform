import { useEffect } from "react";

import { AddUnitMemberDialog } from "@/components/organization/departments/AddUnitMemberDialog";
import { CreateDepartmentDialog } from "@/components/organization/departments/CreateDepartmentDialog";
import { DepartmentDetailPanel } from "@/components/organization/departments/DepartmentDetailPanel";
import { DepartmentTree } from "@/components/organization/departments/DepartmentTree";
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

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="font-serif text-xl font-semibold tracking-[0.02em] text-foreground">
            组织与部门
          </h2>
          <p className="mt-1 text-sm text-muted">
            搭建部门树，并把公司成员分配到各部门。
          </p>
        </div>
        <Button
          type="button"
          size="sm"
          disabled={!state.root || state.creating}
          onClick={state.openCreateTopLevel}
        >
          + 新建一级部门
        </Button>
      </div>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
        <section className="rounded-xl border border-[var(--line2)] bg-white/80 p-3">
          <h3 className="mb-2 px-1 text-xs font-medium uppercase tracking-wide text-muted">
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
            onCreateChild={state.openCreateChild}
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
  );
}
