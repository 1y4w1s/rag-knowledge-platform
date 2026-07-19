import { useCallback, useEffect, useState } from "react";

import { AddMemberDialog } from "@/components/organization/AddMemberDialog";
import { InviteCodePanel } from "@/components/organization/InviteCodePanel";
import { MembersTable } from "@/components/organization/MembersTable";
import { RemoveMemberDialog } from "@/components/organization/RemoveMemberDialog";
import { TransferOwnershipDialog } from "@/components/organization/TransferOwnershipDialog";
import { RequireTeamWorkspace } from "@/components/common/RequireTeamWorkspace";
import { SectionTitle } from "@/components/common/SectionTitle";
import { AlertBanner } from "@/components/ui/AlertBanner";
import { Button } from "@/components/ui/button";
import { fetchCurrentUser } from "@/lib/auth-api";
import { useAuth } from "@/lib/auth-context";
import { getAccessToken, saveAuthSession } from "@/lib/auth-storage";
import {
  addOrganizationMember,
  fetchOrganizationMembers,
  removeOrganizationMember,
  transferOrganizationOwnership,
  updateOrganizationMemberRole,
  type OrganizationMember,
} from "@/lib/organization-api";

export function MembersPage() {
  const { isOrgAdmin, user, syncFromStorage } = useAuth();
  const isOwner = Boolean(user?.is_owner);
  const [members, setMembers] = useState<OrganizationMember[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [addOpen, setAddOpen] = useState(false);
  const [adding, setAdding] = useState(false);
  const [removeTarget, setRemoveTarget] = useState<OrganizationMember | null>(null);
  const [removingUserId, setRemovingUserId] = useState<string | null>(null);
  const [changingRoleUserId, setChangingRoleUserId] = useState<string | null>(null);
  const [transferOpen, setTransferOpen] = useState(false);
  const [transferring, setTransferring] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  const loadData = useCallback(async (options?: { silent?: boolean }) => {
    const silent = options?.silent ?? false;
    if (silent) {
      setRefreshing(true);
    } else {
      setLoading(true);
      setError(null);
    }
    try {
      const items = await fetchOrganizationMembers();
      setMembers(items);
      if (!silent) setError(null);
    } catch (err) {
      if (!silent) {
        setMembers([]);
        setError(err instanceof Error ? err.message : "加载失败");
      }
    } finally {
      if (silent) setRefreshing(false);
      else setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  useEffect(() => {
    const onVisible = () => {
      if (document.visibilityState === "visible") {
        void loadData({ silent: true });
      }
    };
    document.addEventListener("visibilitychange", onVisible);
    return () => document.removeEventListener("visibilitychange", onVisible);
  }, [loadData]);

  useEffect(() => {
    document.title = isOrgAdmin ? "睿阁 · 成员管理" : "睿阁 · 团队成员";
    let meta = document.querySelector<HTMLMetaElement>('meta[name="description"]');
    if (!meta) {
      meta = document.createElement("meta");
      meta.name = "description";
      document.head.appendChild(meta);
    }
    meta.setAttribute("content", "查看与管理团队成员。");
  }, [isOrgAdmin]);

  async function handleAdd(email: string) {
    setAdding(true);
    setActionError(null);
    try {
      await addOrganizationMember(email);
      setAddOpen(false);
      await loadData({ silent: true });
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "添加失败");
    } finally {
      setAdding(false);
    }
  }

  async function handleRemoveConfirm() {
    if (!removeTarget) return;
    setRemovingUserId(removeTarget.user_id);
    setActionError(null);
    try {
      await removeOrganizationMember(removeTarget.user_id);
      setRemoveTarget(null);
      await loadData({ silent: true });
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "移除失败");
    } finally {
      setRemovingUserId(null);
    }
  }

  async function handleRoleChange(
    member: OrganizationMember,
    role: "admin" | "member",
  ) {
    setChangingRoleUserId(member.user_id);
    setActionError(null);
    try {
      await updateOrganizationMemberRole(member.user_id, role);
      await loadData({ silent: true });
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "角色更新失败");
    } finally {
      setChangingRoleUserId(null);
    }
  }

  async function refreshCurrentUser() {
    const token = getAccessToken();
    if (!token) return;
    const freshUser = await fetchCurrentUser();
    saveAuthSession(token, freshUser);
    syncFromStorage();
  }

  async function handleTransferConfirm(targetUserId: string) {
    setTransferring(true);
    setActionError(null);
    try {
      await transferOrganizationOwnership(targetUserId);
      setTransferOpen(false);
      await loadData({ silent: true });
      await refreshCurrentUser();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "转让失败");
    } finally {
      setTransferring(false);
    }
  }

  const pageTitle = isOrgAdmin ? "成员管理" : "团队成员";

  if (loading) {
    return (
      <div className="mx-auto max-w-[1180px] space-y-4 px-7 pb-16 pt-7">
        <div className="h-8 w-48 animate-pulse rounded bg-border/70" />
        <div className="h-40 animate-pulse rounded-xl border border-[var(--line2)] bg-white/60" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="mx-auto max-w-[1180px] px-7 pb-16 pt-7">
        <AlertBanner
          action={
            <Button type="button" variant="outline" size="sm" onClick={() => void loadData()}>
              重试
            </Button>
          }
        >
          {error}
        </AlertBanner>
      </div>
    );
  }

  return (
    <RequireTeamWorkspace feature="成员管理">
      <div className="org-page-quiet mx-auto max-w-[1180px] px-7 pb-16 pt-7">
        <SectionTitle
          label={pageTitle}
          en="MEMBERS"
          tone="quiet"
          count={members.length}
          trailing={
            <div className="flex items-center gap-2">
              <Button
                type="button"
                variant="outline"
                size="sm"
                disabled={refreshing}
                onClick={() => void loadData({ silent: true })}
              >
                {refreshing ? "刷新中…" : "刷新"}
              </Button>
              {isOrgAdmin ? (
                <Button type="button" size="sm" onClick={() => setAddOpen(true)}>
                  + 添加成员
                </Button>
              ) : null}
            </div>
          }
        />

        {actionError ? (
          <AlertBanner onDismiss={() => setActionError(null)}>{actionError}</AlertBanner>
        ) : null}

        {isOrgAdmin ? (
          <InviteCodePanel onAddByEmail={() => setAddOpen(true)} />
        ) : null}

        <MembersTable
          members={members}
          readOnly={!isOrgAdmin}
          isOwner={isOwner}
          currentUserId={user?.id}
          removingUserId={removingUserId}
          changingRoleUserId={changingRoleUserId}
          onRequestRemove={setRemoveTarget}
          onPromote={(member) => void handleRoleChange(member, "admin")}
          onDemote={(member) => void handleRoleChange(member, "member")}
          onRequestTransfer={() => setTransferOpen(true)}
        />

        {isOwner ? (
          <TransferOwnershipDialog
            members={members}
            currentUserId={user?.id ?? ""}
            open={transferOpen}
            onOpenChange={setTransferOpen}
            onConfirm={(targetUserId) => void handleTransferConfirm(targetUserId)}
            transferring={transferring}
          />
        ) : null}

        {isOrgAdmin ? (
          <>
            <AddMemberDialog
              open={addOpen}
              onOpenChange={setAddOpen}
              onSubmit={handleAdd}
              submitting={adding}
            />
            <RemoveMemberDialog
              member={removeTarget}
              open={removeTarget !== null}
              onOpenChange={(open) => {
                if (!open) setRemoveTarget(null);
              }}
              onConfirm={() => void handleRemoveConfirm()}
              removing={removingUserId !== null}
            />
          </>
        ) : null}
      </div>
    </RequireTeamWorkspace>
  );
}
