import { useEffect, useState } from "react";

import { AddUnitMemberDialog } from "@/components/organization/departments/AddUnitMemberDialog";
import { UnitMembersTable } from "@/components/organization/departments/UnitMembersTable";
import { OrgConfirmDialog } from "@/components/organization/OrgConfirmDialog";
import { SectionTitle } from "@/components/common/SectionTitle";
import { AlertBanner } from "@/components/ui/AlertBanner";
import { Button } from "@/components/ui/button";
import type { OrgUnitMember } from "@/lib/org-units-api";
import { useMyUnitMembers } from "@/lib/use-my-unit-members";

/** NW-24 U1：部门 Admin 管本节点成员（无树 CRUD）。 */
export function MyUnitMembersPage() {
  const state = useMyUnitMembers();
  const [removeTarget, setRemoveTarget] = useState<OrgUnitMember | null>(null);

  useEffect(() => {
    document.title = "睿阁 · 我的部门成员";
    let meta = document.querySelector<HTMLMetaElement>('meta[name="description"]');
    if (!meta) {
      meta = document.createElement("meta");
      meta.name = "description";
      document.head.appendChild(meta);
    }
    meta.setAttribute("content", "管理本人担任部门管理员的节点成员。");
  }, []);

  useEffect(() => {
    setRemoveTarget(null);
  }, [state.selectedId]);

  if (state.loading) {
    return (
      <div className="mx-auto max-w-[960px] space-y-4 px-7 pb-16 pt-7">
        <div className="h-8 w-56 animate-pulse rounded bg-border/70" />
        <div className="h-64 animate-pulse rounded border border-[var(--line2)] bg-white/60" />
      </div>
    );
  }

  if (state.error && state.managedUnits.length === 0) {
    return (
      <div className="mx-auto max-w-[960px] px-7 pb-16 pt-7">
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

  return (
    <div className="org-page-quiet mx-auto max-w-[960px] space-y-4 px-7 pb-16 pt-7">
      <SectionTitle
        label="我的部门成员"
        en="MY UNIT"
        tone="quiet"
        trailing={
          <Button
            type="button"
            size="sm"
            variant="outline"
            disabled={!state.selectedId}
            onClick={() => state.setAddMemberOpen(true)}
          >
            + 添加成员
          </Button>
        }
      />

      <p className="text-sm text-muted">
        仅可管理您担任部门管理员的节点；不能改部门树或邀请进公司。
      </p>

      {state.managedUnits.length > 1 ? (
        <div className="max-w-sm">
          <label htmlFor="my-unit-select" className="settings-field-label">
            部门
          </label>
          <select
            id="my-unit-select"
            className="settings-field-input mt-1 h-10 w-full"
            value={state.selectedId ?? ""}
            onChange={(e) => state.setSelectedId(e.target.value || null)}
          >
            {state.managedUnits.map((unit) => (
              <option key={unit.id} value={unit.id}>
                {unit.name}
              </option>
            ))}
          </select>
        </div>
      ) : state.selectedUnit ? (
        <p className="text-sm text-foreground">
          当前部门：<span className="font-medium">{state.selectedUnit.name}</span>
        </p>
      ) : null}

      {state.actionError ? (
        <AlertBanner onDismiss={() => state.setActionError(null)}>
          {state.actionError}
        </AlertBanner>
      ) : null}

      {state.membersLoading ? (
        <div className="h-40 animate-pulse rounded border border-[var(--line2)] bg-white/60" />
      ) : (
        <UnitMembersTable
          members={state.members}
          updatingUserId={state.updatingUserId}
          removingUserId={state.removingUserId}
          onSetRole={(member, role) => void state.handleSetRole(member, role)}
          onSetPrimary={(member) => void state.handleSetPrimary(member)}
          onRemove={setRemoveTarget}
        />
      )}

      <AddUnitMemberDialog
        open={state.addMemberOpen}
        roster={state.roster}
        existingMembers={state.members}
        submitting={state.addingMember}
        onOpenChange={state.setAddMemberOpen}
        onSubmit={state.handleAddMember}
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
        confirming={state.removingUserId !== null}
        onOpenChange={(open) => {
          if (!open) setRemoveTarget(null);
        }}
        onConfirm={() => {
          if (!removeTarget) return;
          void state.handleRemoveMember(removeTarget);
          setRemoveTarget(null);
        }}
      />
    </div>
  );
}
